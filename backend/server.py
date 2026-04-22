"""FastAPI server for DM Game Master web interface."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from backend.config import get_config
from backend.game_state import get_character_status
from backend.claude_dm import process_message, load_system_prompt
from backend.campaign_api import (
    list_campaigns,
    create_campaign,
    activate_campaign,
    delete_campaign,
)
from backend.chat_history import load_chat_history, save_chat_history
from backend.wizard_prompt import load_wizard_system_prompt

# Initialize FastAPI app
app = FastAPI(
    title="DM Game Master API",
    description="Backend server for AI Dungeon Master web interface",
    version="1.0.0",
)

# CRITICAL: Add CORS middleware BEFORE route definitions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for localhost development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    print(f"🚀 DM Game Master backend starting...")

    # Load configuration (no API key required for SDK provider)
    try:
        config = get_config()
        print(f"📍 Server: {config.backend_host}:{config.backend_port}")
        print(f"🤖 Model: {config.model_name}")
        print(f"🔌 AI Provider: {config.ai_provider}")

        # Show selected provider information
        if config.ai_provider == "api":
            if config.anthropic_api_key:
                print(f"✅ Anthropic API: key configured")
            else:
                print(f"⚠️  Anthropic API: key missing")
        elif config.ai_provider == "sdk":
            print(f"🎫 Claude SDK: working via subscription")
        else:  # auto
            if config.anthropic_api_key:
                print(f"🔑 Auto-select: Anthropic API (key found)")
            else:
                print(f"🎫 Auto-select: Claude SDK (key not found)")

        if config.campaign_name:
            print(f"🎲 Active campaign: {config.campaign_name}")
        else:
            print(f"⚠️  No active campaign loaded")
    except ValueError as e:
        print(f"⚠️  Configuration error: {e}")
        print(f"⚠️  Server will start but AI features may be unavailable")


@app.get("/api/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Status message indicating server is healthy
    """
    return {"status": "healthy"}


@app.get("/api/status")
async def get_status():
    """Get current character status for sidebar.

    Returns character stats, inventory, and location from world.json via WorldGraph.
    Uses game_state cache to minimize disk operations.

    Returns:
        dict: Character status with keys:
            - name (str): Character name
            - hp (int): Current health
            - max_hp (int): Maximum health
            - xp (int): Experience points
            - gold (int): Gold in base units (copper)
            - inventory (List[Dict]): Items [{name, quantity}]
            - location (str, optional): Current location
            Or error dict if failed:
            - error (str): Error message
    """
    status = get_character_status()
    return status


# ─────────────────────────── Pydantic Schemas ──────────────────────────────────

class CreateCampaignRequest(BaseModel):
    """Request body for campaign creation."""

    name: str
    genre: Optional[str] = ""
    tone: Optional[str] = ""
    description: Optional[str] = ""
    modules: Optional[List[str]] = None
    narrator_style: Optional[str] = ""
    rules: Optional[str] = ""
    character: Optional[dict] = None


# ─────────────────────────── Campaign API ──────────────────────────────────────

@app.get("/api/campaigns")
async def api_list_campaigns():
    """Get list of all campaigns.

    Returns:
        list: Campaign list with fields name, active, created_at, genre, tone, description
    """
    return list_campaigns()


@app.post("/api/campaigns", status_code=201)
async def api_create_campaign(body: CreateCampaignRequest):
    """Create new campaign.

    Args:
        body: New campaign data (name is required)

    Returns:
        dict: Created campaign info or error 400/409
    """
    result = create_campaign(
        name=body.name,
        genre=body.genre or "",
        tone=body.tone or "",
        description=body.description or "",
        modules=body.modules,
        narrator_style=body.narrator_style or "",
        rules=body.rules or "",
        character=body.character,
    )

    if not result.get("success"):
        error_msg = result.get("error", "Campaign creation error")
        # Campaign already exists → 409 Conflict, otherwise 400 Bad Request
        status_code = 409 if "already exists" in error_msg else 400
        raise HTTPException(status_code=status_code, detail=error_msg)

    return result


@app.post("/api/campaigns/{name}/activate")
async def api_activate_campaign(name: str):
    """Activate campaign by name.

    Args:
        name: Campaign name to activate

    Returns:
        dict: {"success": true, "name": "..."} or error 404
    """
    result = activate_campaign(name)

    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", f"Campaign '{name}' not found"),
        )

    return result


@app.delete("/api/campaigns/{name}", status_code=200)
async def api_delete_campaign(name: str):
    """Delete campaign and all its data.

    Args:
        name: Campaign name to delete

    Returns:
        dict: {"success": true} or error 404/409
    """
    result = delete_campaign(name)

    if not result.get("success"):
        error_msg = result.get("error", "Deletion error")
        status_code = 409 if "active campaign" in error_msg else 404
        raise HTTPException(status_code=status_code, detail=error_msg)

    return result


@app.get("/api/campaigns/active")
async def get_active_campaign_endpoint():
    """Get currently active campaign.

    Returns:
        dict: {"name": "campaign-name"} or {"name": null} if none active
    """
    from backend.config import get_active_campaign

    active = get_active_campaign()
    return {"name": active}


# ─────────────────────────── Template Helper Functions ────────────────────────

def _parse_md_frontmatter(path: Path) -> dict:
    """Extract id/name/description/genres fields from markdown style file.

    File format:
        ## id
        some-id
        ## name
        Some Name
        ## description
        Some description text...

    Args:
        path: Path to .md file

    Returns:
        dict: Dictionary with id, name, description and genres (list) fields
    """
    text = path.read_text(encoding="utf-8")
    result: dict = {"id": path.stem, "name": path.stem, "description": "", "genres": []}

    # Split into sections of format "## key\nvalue"
    sections = re.split(r'^## ', text, flags=re.MULTILINE)
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        key = lines[0].strip().lower()
        value = "\n".join(lines[1:]).strip()
        if key == "id":
            result["id"] = value
        elif key == "name":
            result["name"] = value
        elif key == "description":
            result["description"] = value
        elif key == "genres":
            result["genres"] = [g.strip() for g in value.replace(",", " ").split() if g.strip()]

    return result


def _get_modules_dir() -> Path:
    """Get path to modules directory relative to project root."""
    config = get_config()
    return Path(config.project_root) / ".claude" / "additional" / "modules"


def _get_narrator_styles_dir() -> Path:
    """Get path to narrator styles directory."""
    config = get_config()
    return Path(config.project_root) / ".claude" / "additional" / "narrator-styles"


def _get_campaign_rules_templates_dir() -> Path:
    """Get path to campaign rules templates directory."""
    config = get_config()
    return Path(config.project_root) / ".claude" / "additional" / "campaign-rules-templates"


# ─────────────────────────── Template API ──────────────────────────────────────

@app.get("/api/templates/modules")
async def api_get_template_modules():
    """Get list of available game modules.

    Reads module.json from each modules/ subdirectory and returns
    metadata: id, name, description, category, genre_tags, tags,
    enabled_by_default, features.

    Returns:
        list: Module list with fields from module.json
    """
    modules_dir = _get_modules_dir()
    result = []

    if not modules_dir.exists():
        return result

    for module_path in sorted(modules_dir.iterdir()):
        if not module_path.is_dir():
            continue
        manifest = module_path / "module.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            result.append({
                "id": data.get("id", module_path.name),
                "name": data.get("name", module_path.name),
                "description": data.get("description", ""),
                "category": data.get("category", ""),
                "genre_tags": data.get("genre_tags", []),
                "tags": data.get("tags", []),
                "enabled_by_default": data.get("enabled_by_default", False),
                "features": data.get("features", []),
            })
        except (json.JSONDecodeError, OSError):
            # Skip invalid modules
            continue

    return result


@app.get("/api/templates/narrators")
async def api_get_template_narrators():
    """Get list of available narrator styles.

    Reads .md files from narrator-styles/ and extracts
    id, name, description, genres sections.

    Returns:
        list: Narrator styles list with id, name, description, genres fields
    """
    styles_dir = _get_narrator_styles_dir()
    result = []

    if not styles_dir.exists():
        return result

    for style_path in sorted(styles_dir.glob("*.md")):
        try:
            result.append(_parse_md_frontmatter(style_path))
        except OSError:
            continue

    return result


@app.get("/api/templates/rules")
async def api_get_template_rules():
    """Get list of campaign rules templates.

    Reads .md files from campaign-rules-templates/ and extracts
    id, name, description, genres sections.

    Returns:
        list: Rules templates list with id, name, description, genres fields
    """
    rules_dir = _get_campaign_rules_templates_dir()
    result = []

    if not rules_dir.exists():
        return result

    for rule_path in sorted(rules_dir.glob("*.md")):
        try:
            result.append(_parse_md_frontmatter(rule_path))
        except OSError:
            continue

    return result


def _now_iso() -> str:
    """Get current time in ISO 8601 UTC format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/")
async def root():
    """Root endpoint with basic server info.

    Returns:
        dict: Welcome message and API documentation link
    """
    return {
        "message": "DM Game Master API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.websocket("/ws/wizard")
async def wizard_websocket(websocket: WebSocket):
    """WebSocket for campaign creation wizard. Uses MCP tools via SDK."""
    await websocket.accept()

    conversation_history: List = []
    config = None

    try:
        config = get_config()
        wizard_prompt = load_wizard_system_prompt()
        print(f"🧙 Wizard WebSocket connected ({len(wizard_prompt)} chars prompt)")
    except ValueError as e:
        await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
        await websocket.close()
        return

    # Unique output file per connection
    import uuid
    output_file = f"/tmp/wizard-{uuid.uuid4().hex[:8]}.jsonl"

    # MCP server config for wizard tools
    wizard_mcp = {
        "wizard": {
            "command": "uv",
            "args": ["run", "python", str(Path(config.project_root) / "backend" / "wizard_mcp.py")],
            "env": {"WIZARD_OUTPUT_FILE": output_file},
        }
    }

    try:
        while True:
            user_message = await websocket.receive_text()
            print(f"🧙 Wizard message: {user_message[:50]}...")

            conversation_history.append({"role": "user", "content": user_message})

            # Clear output file before each turn
            Path(output_file).write_text("", encoding="utf-8")

            full_response_parts: List[str] = []

            try:
                async for chunk in process_message(
                    user_message=user_message,
                    conversation_history=conversation_history,
                    provider_type=config.ai_provider,
                    api_key=config.anthropic_api_key,
                    model_name=config.model_name,
                    system_prompt=wizard_prompt,
                    project_root=config.project_root,
                    mcp_servers=wizard_mcp,
                ):
                    # SDK provider sends structured JSON events
                    try:
                        event = json.loads(chunk)
                        await websocket.send_text(chunk)
                        if event.get("type") == "text":
                            full_response_parts.append(event["content"])
                    except json.JSONDecodeError:
                        # Fallback for raw text
                        await websocket.send_text(json.dumps(
                            {"type": "text", "content": chunk}, ensure_ascii=False
                        ))
                        full_response_parts.append(chunk)

                # Read MCP tool outputs
                if Path(output_file).exists():
                    for line in Path(output_file).read_text(encoding="utf-8").strip().splitlines():
                        if not line.strip():
                            continue
                        try:
                            tool_output = json.loads(line)
                            if tool_output.get("tool") == "show_choices":
                                await websocket.send_text(json.dumps({
                                    "type": "show_choices",
                                    "data": tool_output["data"],
                                }, ensure_ascii=False))
                            elif tool_output.get("tool") == "clear_choices":
                                await websocket.send_text(json.dumps({
                                    "type": "clear_choices",
                                }))
                            elif tool_output.get("tool") == "create_campaign":
                                if tool_output.get("success"):
                                    await websocket.send_text(json.dumps({
                                        "type": "wizard_complete",
                                        "campaign_name": tool_output.get("campaign_name"),
                                    }))
                                else:
                                    await websocket.send_text(json.dumps({
                                        "type": "error",
                                        "content": tool_output.get("error", "Creation failed"),
                                    }))
                        except json.JSONDecodeError:
                            pass

                full_response = "".join(full_response_parts)
                conversation_history.append({"role": "assistant", "content": full_response})

            except Exception as e:
                print(f"❌ Wizard error: {e}")
                await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))

            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        print(f"🧙 Wizard WebSocket disconnected")
        # Cleanup temp file
        Path(output_file).unlink(missing_ok=True)


def _fetch_modules_list():
    modules_dir = _get_modules_dir()
    result = []
    if not modules_dir.exists():
        return result
    for module_path in sorted(modules_dir.iterdir()):
        if not module_path.is_dir():
            continue
        manifest = module_path / "module.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            result.append({
                "id": data.get("id", module_path.name),
                "name": data.get("name", module_path.name),
                "description": data.get("description", ""),
                "genre_tags": data.get("genre_tags", []),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return result


def _fetch_narrators_list():
    styles_dir = _get_narrator_styles_dir()
    result = []
    if not styles_dir.exists():
        return result
    for path in sorted(styles_dir.glob("*.md")):
        result.append(_parse_md_frontmatter(path))
    return result


def _fetch_rules_list():
    rules_dir = _get_campaign_rules_templates_dir()
    result = []
    if not rules_dir.exists():
        return result
    for path in sorted(rules_dir.glob("*.md")):
        result.append(_parse_md_frontmatter(path))
    return result


@app.get("/ws/game")
async def game_websocket_info():
    """HTTP GET handler for WebSocket endpoint.

    Returns 426 Upgrade Required to indicate this is a WebSocket endpoint.

    Returns:
        Response: 426 status code with Upgrade header
    """
    return Response(
        content="This endpoint requires WebSocket connection",
        status_code=426,
        headers={"Upgrade": "websocket"}
    )


@app.websocket("/ws/game")
async def game_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time game communication.

    Handles bi-directional communication between player and DM agent.
    Streams responses from Claude API and executes game tools.
    Loads chat history on connect and saves after each turn.

    Args:
        websocket: WebSocket connection instance
    """
    await websocket.accept()

    # Initialize conversation state
    conversation_history = []
    system_prompt = None
    config = None

    # Load configuration and system prompt
    try:
        config = get_config()
        system_prompt = load_system_prompt()
        print(f"✅ WebSocket connected - system prompt loaded ({len(system_prompt)} chars)")
        print(f"🔌 AI Provider: {config.ai_provider}")
    except ValueError as e:
        # Configuration error - send error message and close connection
        await websocket.send_text(f"❌ Configuration error: {str(e)}")
        await websocket.close()
        return

    # Load chat history from file on connection
    campaign_dir: Optional[Path] = config.campaign_dir if config else None
    if campaign_dir:
        saved_messages = load_chat_history(campaign_dir)
        if saved_messages:
            # Restore conversation history for Claude
            for msg in saved_messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    conversation_history.append({"role": role, "content": content})

            # Send history to client as JSON packet
            history_packet = json.dumps({"type": "history", "messages": saved_messages})
            await websocket.send_text(history_packet)
            print(f"📜 Chat history loaded: {len(saved_messages)} messages")
        else:
            print(f"📜 Chat history empty — starting new conversation")
    else:
        print(f"⚠️  Active campaign not set — chat history will not be saved")

    try:
        while True:
            # Receive message from player
            user_message = await websocket.receive_text()
            print(f"📩 Received message: {user_message[:50]}...")

            conversation_history.append({"role": "user", "content": user_message})
            full_response_parts: List[str] = []

            # Process message through DM agent with streaming
            try:
                async for chunk in process_message(
                    user_message=user_message,
                    conversation_history=conversation_history,
                    provider_type=config.ai_provider,
                    api_key=config.anthropic_api_key,
                    model_name=config.model_name,
                    system_prompt=system_prompt,
                    project_root=config.project_root
                ):
                    try:
                        event = json.loads(chunk)
                        await websocket.send_text(chunk)
                        if event.get("type") == "text":
                            full_response_parts.append(event["content"])
                    except json.JSONDecodeError:
                        await websocket.send_text(json.dumps(
                            {"type": "text", "content": chunk}, ensure_ascii=False
                        ))
                        full_response_parts.append(chunk)

                # Send end-of-message marker
                await websocket.send_text(json.dumps({"type": "done"}))
                print(f"✅ Completed message processing")

                # Save turn to chat history
                if campaign_dir and full_response_parts:
                    full_response = "".join(full_response_parts)
                    timestamp = _now_iso()

                    # Add assistant response to conversation_history
                    # (user message is already added by the provider)
                    conversation_history.append({"role": "assistant", "content": full_response})

                    # Persist history to disk
                    all_saved = load_chat_history(campaign_dir)
                    all_saved.append({"role": "user", "content": user_message, "timestamp": timestamp})
                    all_saved.append({"role": "assistant", "content": full_response, "timestamp": timestamp})
                    save_chat_history(campaign_dir, all_saved)
                    print(f"💾 Chat history saved ({len(all_saved)} messages)")

            except Exception as e:
                # Send error to client and log
                error_message = f"Error: {str(e)}"
                print(f"❌ DM Agent error: {error_message}")
                await websocket.send_text(f"\n\n{error_message}")

    except WebSocketDisconnect:
        # Client disconnected, cleanup connection
        print(f"🔌 WebSocket disconnected")
        pass
