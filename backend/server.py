"""FastAPI server for DM Game Master web interface."""

import asyncio
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from fastapi import Request, Form
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_config, validate_server_security
from backend.game_state import get_character_status
from lib.campaign_context import (
    InvalidCampaignName,
    resolve_campaign_dir,
)
from backend.claude_dm import load_system_prompt
from backend.auth import is_authenticated, login_page, handle_login
from backend.campaign_api import (
    list_campaigns,
    create_campaign,
    activate_campaign,
    delete_campaign,
)
from backend.event_log import read_events
from backend.game_session import get_or_create_session, peek_session
from backend.live_broker import broker
from backend.providers.claude_sdk import ClaudeSDKProvider
from backend.wizard_prompt import load_wizard_system_prompt
from backend.wizard_mcp import WizardEvents, build_wizard_mcp

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate exposure and report the effective runtime configuration."""
    config = get_config()
    validate_server_security(config)
    print("DM Game Master backend starting...")
    print(f"Server: {config.backend_host}:{config.backend_port}")
    print(f"Model: {config.model_name}")
    print("Claude SDK: working via subscription")
    if config.campaign_name:
        print(f"Active campaign: {config.campaign_name}")
    else:
        print("No active campaign loaded")
    yield


app = FastAPI(
    title="DM Game Master API",
    description="Backend server for AI Dungeon Master web interface",
    version="1.0.0",
    lifespan=lifespan,
)

# Vanilla frontend lives in <project>/frontend — same origin, no CORS needed.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ─────────────────────────── Auth middleware ──────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    """Redirect unauthenticated requests to login page.
    Skips /auth/* and /static/* paths. Disabled when DND_AUTH_PASSWORD unset."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/auth") or path.startswith("/static/css") or path.startswith("/static/js"):
            return await call_next(request)
        if not is_authenticated(request):
            return login_page()
        return await call_next(request)


app.add_middleware(AuthMiddleware)


@app.post("/auth/login")
async def auth_login(password: str = Form(...)):
    """Handle login form submission."""
    return handle_login(password)


@app.get("/auth/login")
async def auth_login_page():
    """Show login page."""
    return login_page()

# Campaign name becomes a directory component (campaigns/<name>/) and a bash env
# var fed to the rules compiler. Reject only what lets it escape the campaigns dir
# (path separators + traversal) — mirror campaign_api.create_campaign's forbidden
# set so every legally-created campaign (spaces/dots/Unicode allowed) stays playable.
_FORBIDDEN_CAMPAIGN_CHARS = set('/\\:*?"<>|')


def _valid_campaign_name(name: str) -> bool:
    return (
        bool(name)
        and not (_FORBIDDEN_CAMPAIGN_CHARS & set(name))
        and ".." not in name
        and not name.startswith(".")
    )


# Models the client may pick in the header select. Order = display order.
ALLOWED_MODELS = ["claude-sonnet-5", "claude-opus-4-8"]


def _model_options() -> tuple[list[str], str]:
    """(selectable models, default). Default is the configured model so game
    sessions honour config.model_name; the configured model is included even if
    it isn't in the static list, so it's never silently swapped."""
    configured = get_config().model_name or ALLOWED_MODELS[0]
    models = list(ALLOWED_MODELS)
    if configured not in models:
        models.insert(0, configured)
    return models, configured


@app.get("/api/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Status message indicating server is healthy
    """
    return {"status": "healthy"}


@app.get("/api/status")
async def get_status(campaign: Optional[str] = None):
    """Get current character status for sidebar.

    Returns character stats, inventory, and location from world.json via WorldGraph.
    Uses game_state cache to minimize disk operations.

    Args:
        campaign: Campaign name (optional). If given, reads that campaign's
            world.json instead of the global active campaign.

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
    campaign_dir = None
    if campaign:
        config = get_config()
        try:
            campaign_dir = resolve_campaign_dir(
                config.campaigns_dir, campaign, must_exist=True
            )
        except (InvalidCampaignName, FileNotFoundError):
            return {"error": "Campaign not found"}
    status = get_character_status(campaign_dir=campaign_dir)
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


@app.post("/api/campaigns/{name}/reset-session")
async def api_reset_session(name: str):
    """Start a fresh Claude conversation for the campaign — clears the DM's working
    context (session_id) but keeps the event log / chat history. No-op if the
    campaign has no live session. 409 if a turn is currently running."""
    if not _valid_campaign_name(name):
        raise HTTPException(status_code=400, detail="Invalid campaign name")
    session = peek_session(name)
    if session is None:
        return {"success": True, "reset": False}  # nothing live to reset
    if not await session.reset_session():
        raise HTTPException(status_code=409, detail="A turn is in progress")
    return {"success": True, "reset": True}


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


@app.get("/api/models")
async def api_models():
    """Selectable models + the default (the configured model)."""
    models, default = _model_options()
    return {"models": models, "default": default}


@app.get("/")
async def root():
    """Serve the single-page vanilla frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.websocket("/ws/wizard")
async def wizard_websocket(websocket: WebSocket):
    """Ephemeral campaign-creation wizard — streams like the game handler.

    Fresh provider per connection (no session_id / no event log / no resume).
    Tool calls go through an IN-PROCESS MCP (backend/wizard_mcp.py), so the DM's
    text streams token-by-token (`stream`) while tool invocations surface as
    `activity` blocks and their side effects (choices / completion) drain from
    WizardEvents into show_choices / clear_choices / wizard_complete events.
    """
    await websocket.accept()

    try:
        config = get_config()
        wizard_prompt = load_wizard_system_prompt()
    except ValueError as e:
        await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
        await websocket.close()
        return

    # In-process MCP: tools push structured events here (no subprocess, no files).
    events = WizardEvents()
    wizard_mcp = {"wizard": build_wizard_mcp(events)}

    provider = ClaudeSDKProvider(project_root=config.project_root, model_name=config.model_name)

    async def send(event: dict) -> None:
        await websocket.send_text(json.dumps(event, ensure_ascii=False))

    try:
        while True:
            user_message = await websocket.receive_text()
            print(f"🧙 Wizard message: {user_message[:50]}...")
            events.drain()  # clear any leftovers from a previous turn

            try:
                async for event in provider.process_message(
                    user_message=user_message,
                    system_prompt=wizard_prompt,
                    model_name=config.model_name,
                    mcp_servers=wizard_mcp,
                ):
                    et = event["type"]
                    if et == "text_delta":
                        await send({"type": "stream", "content": event["content"]})
                    elif et in ("text", "activity", "error"):
                        await send({"type": et, "content": event["content"]})

                # Drain tool side effects collected in-process during the turn.
                for ev in events.drain():
                    if ev["type"] == "show_choices":
                        await send({"type": "show_choices", "data": ev["data"]})
                    elif ev["type"] == "clear_choices":
                        await send({"type": "clear_choices"})
                    elif ev["type"] == "create_campaign":
                        if ev.get("success"):
                            await send({"type": "wizard_complete", "campaign_name": ev.get("campaign_name")})
                        else:
                            await send({"type": "error", "content": ev.get("error", "Creation failed")})

            except Exception as e:
                print(f"❌ Wizard error: {e}")
                await send({"type": "error", "content": str(e)})

            await send({"type": "done"})

    except WebSocketDisconnect:
        print("Wizard disconnected")


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

    Campaign-addressed: `/ws/game?campaign=<name>&after_id=<n>` — mirrors
    Orchestra's per-session sockets so multiple campaigns can stream
    independently instead of sharing one global active campaign.

    Gets/creates the campaign's GameSession, subscribes to its broker channel,
    and replays the event log after `after_id`. Turns run independently of
    this connection — disconnecting does NOT stop an in-flight turn;
    reconnecting resumes seeing live output plus anything missed.

    `receive_text()` is ALWAYS a player turn — there is no client→server
    control message. Replay is driven entirely by the `after_id` query param
    on (re)connect, never by an in-band message.
    """
    await websocket.accept()

    campaign = websocket.query_params.get("campaign")
    if not campaign or not _valid_campaign_name(campaign):
        await websocket.send_text(json.dumps({"type": "error", "content": "Missing or invalid ?campaign= query param"}))
        await websocket.close()
        return
    after_id = int(websocket.query_params.get("after_id", "0"))

    config = get_config()
    system_prompt = load_system_prompt(campaign)  # scope rules/narrator to THIS campaign
    # Optional model override from the client's model-select. Unknown/absent → config default.
    allowed, default_model = _model_options()
    requested_model = websocket.query_params.get("model")
    model_name = requested_model if requested_model in allowed else default_model
    session = get_or_create_session(campaign, config.project_root, model_name)

    # Replay only what the client missed, driven by the after_id cursor it sent
    history = read_events(session.campaign_dir, after_id=after_id)
    if history:
        await websocket.send_text(json.dumps({"type": "history", "messages": history}, ensure_ascii=False))

    queue = broker.subscribe(campaign)
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
                print(f"📩 [{campaign}] Received message: {user_message[:50]}...")
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
        print(f"🔌 [{campaign}] WebSocket disconnected (turn keeps running if active)")
    finally:
        broker.unsubscribe(campaign, queue)


# Static assets (css/js) — mounted last so it never shadows /api or /ws routes.
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
