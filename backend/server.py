"""FastAPI server for DM Game Master web interface."""

import asyncio
import json
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from backend.config import get_config
from backend.game_state import get_character_status
from backend.claude_dm import load_system_prompt
from backend.campaign_api import (
    list_campaigns,
    create_campaign,
    activate_campaign,
    delete_campaign,
)
from backend.event_log import read_events
from backend.game_session import get_or_create_session
from backend.live_broker import broker
from backend.providers.claude_sdk import ClaudeSDKProvider
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

    config = get_config()
    print(f"📍 Server: {config.backend_host}:{config.backend_port}")
    print(f"🤖 Model: {config.model_name}")
    print(f"🎫 Claude SDK: working via subscription")

    if config.campaign_name:
        print(f"🎲 Active campaign: {config.campaign_name}")
    else:
        print(f"⚠️  No active campaign loaded")


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
    """WebSocket for campaign creation wizard. Uses MCP tools via SDK.

    One-shot setup flow (no persistent campaign yet) — provider lives for the
    connection's lifetime, no GameSession/broker needed.
    """
    await websocket.accept()

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

    provider = ClaudeSDKProvider(project_root=config.project_root, model_name=config.model_name)

    try:
        while True:
            user_message = await websocket.receive_text()
            print(f"🧙 Wizard message: {user_message[:50]}...")

            # Clear output file before each turn
            Path(output_file).write_text("", encoding="utf-8")

            try:
                async for event in provider.process_message(
                    user_message=user_message,
                    system_prompt=wizard_prompt,
                    model_name=config.model_name,
                    mcp_servers=wizard_mcp,
                ):
                    if event["type"] == "text_delta":
                        continue
                    if event["type"] == "text":
                        await websocket.send_text(json.dumps(
                            {"type": "text", "content": event["content"]}, ensure_ascii=False
                        ))
                    elif event["type"] == "error":
                        await websocket.send_text(json.dumps(
                            {"type": "error", "content": event["content"]}, ensure_ascii=False
                        ))

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

            except Exception as e:
                print(f"❌ Wizard error: {e}")
                await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))

            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        print(f"🧙 Wizard WebSocket disconnected")
        Path(output_file).unlink(missing_ok=True)


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

    Gets/creates the campaign's GameSession, subscribes to its broker channel,
    and replays the event log. Turns run independently of this connection —
    disconnecting does NOT stop an in-flight turn; reconnecting resumes seeing
    live output plus anything missed (via after_id replay).
    """
    await websocket.accept()

    config = get_config()
    if not config.campaign_name or not config.campaign_dir:
        await websocket.send_text(json.dumps({"type": "error", "content": "No active campaign"}))
        await websocket.close()
        return

    system_prompt = load_system_prompt()
    session = get_or_create_session(config.campaign_name, config.project_root, config.model_name)

    # Replay persisted history so a reconnecting client sees what it missed
    history = read_events(session.campaign_dir)
    if history:
        await websocket.send_text(json.dumps({"type": "history", "messages": history}, ensure_ascii=False))

    queue = broker.subscribe(config.campaign_name)
    try:
        while True:
            receive_task = asyncio.ensure_future(websocket.receive_text())
            queue_task = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait(
                {receive_task, queue_task}, return_when=asyncio.FIRST_COMPLETED
            )

            if receive_task in done:
                queue_task.cancel()
                user_message = receive_task.result()
                print(f"📩 Received message: {user_message[:50]}...")
                if not session.send(user_message, system_prompt):
                    await websocket.send_text(json.dumps(
                        {"type": "error", "content": "A turn is already in progress"}, ensure_ascii=False
                    ))
                continue

            if queue_task in done:
                receive_task.cancel()
                event = queue_task.result()
                await websocket.send_text(json.dumps(event, ensure_ascii=False))

    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected (turn keeps running if active)")
    finally:
        broker.unsubscribe(config.campaign_name, queue)
