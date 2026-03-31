"""DM Agent - System prompt builder and tool calling loop."""

import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
from anthropic import AsyncAnthropic
from backend.tools_registry import get_tool_schemas, execute_tool


def load_system_prompt() -> str:
    """Load DM rules and narrator styles from .claude/additional/.

    Loads pre-compiled DM rules from /tmp/dm-rules.md (if exists) or compiles
    them from .claude/additional/dm-slots/. Appends narrator style from active
    campaign's campaign-overview.json or falls back to default style.

    Returns:
        str: Complete system prompt combining DM rules and narrator style
    """
    project_root = Path(__file__).parent.parent

    # Step 1: Load DM rules
    dm_rules_path = Path("/tmp/dm-rules.md")

    if dm_rules_path.exists():
        # Pre-compiled rules exist (created by infrastructure hooks)
        dm_rules = dm_rules_path.read_text()
    else:
        # Fallback: compile rules from slots
        rules_compiler = project_root / ".claude" / "additional" / "infrastructure" / "dm-active-modules-rules.sh"

        if rules_compiler.exists():
            try:
                dm_rules = subprocess.check_output(
                    ["bash", str(rules_compiler)],
                    cwd=str(project_root),
                    text=True,
                    stderr=subprocess.DEVNULL
                )
            except subprocess.CalledProcessError:
                dm_rules = ""
        else:
            dm_rules = ""

    # Step 2: Load narrator style from campaign-overview.json or use default
    narrator_style = ""

    # Try to load from active campaign
    active_campaign_file = project_root / "world-state" / "active-campaign.txt"
    if active_campaign_file.exists():
        campaign_name = active_campaign_file.read_text().strip()
        if campaign_name:
            overview_path = project_root / "world-state" / "campaigns" / campaign_name / "campaign-overview.json"
            if overview_path.exists():
                try:
                    with open(overview_path) as f:
                        overview = json.load(f)

                    # Extract narrator style rules from overview
                    narrator_data = overview.get("narrator_style", {})
                    if narrator_data:
                        style_rules = narrator_data.get("rules_raw", "")
                        style_name = narrator_data.get("name", "")
                        style_desc = narrator_data.get("description", "")

                        narrator_style = f"\n---\n# Narrator Style: {style_name}\n\n{style_desc}\n\n{style_rules}\n"
                except (json.JSONDecodeError, IOError):
                    pass

    # Fallback to default narrator style if none found
    if not narrator_style:
        default_style_path = project_root / ".claude" / "additional" / "narrator-styles" / "epic-heroic.md"
        if default_style_path.exists():
            narrator_style = f"\n---\n{default_style_path.read_text()}\n"

    # Combine prompts
    system_prompt = f"{dm_rules}\n{narrator_style}"

    # Ensure we return something meaningful
    if len(system_prompt.strip()) < 100:
        # Fallback minimal prompt
        system_prompt = """# DM System - AI Dungeon Master

You are an AI Dungeon Master for D&D 5e campaigns. Guide players through their adventure, narrate scenes, manage combat, and call appropriate tools to track game state.

Use the available tools to:
- Roll dice for checks, saves, and attacks
- Manage inventory, HP, XP, and gold
- Track NPCs, locations, and plot threads
- Advance game time

Be descriptive, engaging, and fair. Follow D&D 5e rules. Make the game fun!
"""

    return system_prompt


async def process_message(
    user_message: str,
    conversation_history: List[Dict[str, Any]],
    api_key: str,
    model_name: str = "claude-3-5-sonnet-20241022",
    system_prompt: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Process user message through DM agent with tool calling loop.

    This function handles the conversation loop with Claude, including:
    - Streaming text responses word-by-word
    - Detecting tool_use blocks via stop_reason == 'tool_use'
    - Executing requested tools via execute_tool()
    - Appending tool results to conversation with correct tool_use_id
    - Continuing conversation loop until final text response

    Args:
        user_message: Player's input message
        conversation_history: List of conversation messages (modified in-place)
        api_key: Anthropic API key
        model_name: Claude model name to use
        system_prompt: System prompt (loaded from load_system_prompt if None)

    Yields:
        Text chunks from Claude's streaming response
    """
    # Load system prompt if not provided
    if system_prompt is None:
        system_prompt = load_system_prompt()

    # Initialize Anthropic client
    client = AsyncAnthropic(api_key=api_key)

    # Add user message to conversation history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    # Tool calling loop: continue until we get a plain text response
    max_iterations = 10  # Prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Stream response from Claude
        async with client.messages.stream(
            model=model_name,
            max_tokens=4096,
            system=system_prompt,
            messages=conversation_history,
            tools=get_tool_schemas()
        ) as stream:
            # Yield streaming text chunks to caller
            async for text in stream.text_stream:
                yield text

            # Get final message to check for tool calls
            final_message = await stream.get_final_message()

            # Add assistant's response to conversation history
            conversation_history.append({
                "role": "assistant",
                "content": final_message.content
            })

            # Check if Claude requested tool execution
            if final_message.stop_reason == "tool_use":
                # Execute all requested tools
                tool_results = []

                for block in final_message.content:
                    if block.type == "tool_use":
                        try:
                            # Execute tool via tools_registry
                            result = execute_tool(block.name, block.input)

                            # Convert result dict to string for Claude
                            if isinstance(result, dict):
                                if "error" in result:
                                    # Tool execution failed
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": block.id,
                                        "content": result["error"],
                                        "is_error": True
                                    })
                                else:
                                    # Tool execution succeeded
                                    result_str = json.dumps(result["result"]) if isinstance(result.get("result"), dict) else str(result.get("result", ""))
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": block.id,
                                        "content": result_str
                                    })
                            else:
                                # Fallback for non-dict results
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": str(result)
                                })

                        except Exception as e:
                            # Return error to Claude so it can explain to player
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error executing tool: {str(e)}",
                                "is_error": True
                            })

                # Append tool results to conversation history
                conversation_history.append({
                    "role": "user",
                    "content": tool_results
                })

                # Continue loop - Claude will incorporate tool results in next iteration
                # Don't yield anything here, just continue to next API call

            else:
                # No tool use - we have final response, exit loop
                break

    # If we hit max iterations, yield warning
    if iteration >= max_iterations:
        yield "\n\n[Warning: Maximum tool calling iterations reached]"
