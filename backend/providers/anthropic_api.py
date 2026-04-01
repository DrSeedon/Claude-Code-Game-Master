"""Provider for Anthropic API (requires ANTHROPIC_API_KEY)."""

import json
from typing import AsyncGenerator, List, Dict, Any
from anthropic import AsyncAnthropic
from backend.providers.base import BaseProvider
from backend.tools_registry import execute_tool


class AnthropicAPIProvider(BaseProvider):
    """AI provider via Anthropic REST API.

    Requirements:
    - ANTHROPIC_API_KEY in environment variables
    - Uses AsyncAnthropic client for streaming
    - Supports tool calling via API

    This provider is suitable for users with Anthropic API keys.
    """

    def __init__(self, api_key: str):
        """Initialize provider.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key
        self.client = AsyncAnthropic(api_key=api_key)

    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Process message via Anthropic API with tool calling loop.

        Algorithm:
        1. Add user_message to history
        2. Stream response from Claude
        3. If stop_reason == "tool_use" — execute tools
        4. Add results to history and repeat from step 2
        5. Otherwise — complete

        Args:
            user_message: Message from player
            conversation_history: Conversation history (modified in-place)
            system_prompt: DM system prompt
            model_name: Claude model name
            tools: Tool schemas in Anthropic format

        Yields:
            Text chunks from streaming response
        """
        # Add user message to history
        conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Tool calling loop: continue until final text response
        max_iterations = 10  # Protection against infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Stream response from Claude
            async with self.client.messages.stream(
                model=model_name,
                max_tokens=4096,
                system=system_prompt,
                messages=conversation_history,
                tools=tools
            ) as stream:
                # Yield streaming text to caller
                async for text in stream.text_stream:
                    yield text

                # Get final message to check for tool calls
                final_message = await stream.get_final_message()

                # Add assistant response to history
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

                                # Convert result to string for Claude
                                if isinstance(result, dict):
                                    if "error" in result:
                                        # Tool returned error
                                        tool_results.append({
                                            "type": "tool_result",
                                            "tool_use_id": block.id,
                                            "content": result["error"],
                                            "is_error": True
                                        })
                                    else:
                                        # Tool executed successfully
                                        result_str = (
                                            json.dumps(result["result"])
                                            if isinstance(result.get("result"), dict)
                                            else str(result.get("result", ""))
                                        )
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

                    # Add tool results to history
                    conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Continue loop — Claude will process results in next iteration
                    # Don't return text here, just continue to next API call

                else:
                    # No tool use — final response received, exit loop
                    break

        # If reached max iterations, issue warning
        if iteration >= max_iterations:
            yield "\n\n[Warning: Reached tool calling iteration limit]"

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "Anthropic API"
