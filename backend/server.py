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

    # Load configuration (теперь не требует API key для SDK провайдера)
    try:
        config = get_config()
        print(f"📍 Server: {config.backend_host}:{config.backend_port}")
        print(f"🤖 Model: {config.model_name}")
        print(f"🔌 AI Provider: {config.ai_provider}")

        # Показываем информацию о выбранном провайдере
        if config.ai_provider == "api":
            if config.anthropic_api_key:
                print(f"✅ Anthropic API: ключ настроен")
            else:
                print(f"⚠️  Anthropic API: ключ отсутствует")
        elif config.ai_provider == "sdk":
            print(f"🎫 Claude SDK: работа через подписку")
        else:  # auto
            if config.anthropic_api_key:
                print(f"🔑 Автовыбор: Anthropic API (найден ключ)")
            else:
                print(f"🎫 Автовыбор: Claude SDK (ключ не найден)")

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


# ─────────────────────────── Pydantic схемы ────────────────────────────────────

class CreateCampaignRequest(BaseModel):
    """Тело запроса для создания кампании."""

    name: str
    genre: Optional[str] = ""
    tone: Optional[str] = ""
    description: Optional[str] = ""
    modules: Optional[List[str]] = None
    narrator_style: Optional[str] = ""


# ─────────────────────────── Campaign API ──────────────────────────────────────

@app.get("/api/campaigns")
async def api_list_campaigns():
    """Получить список всех кампаний.

    Returns:
        list: Список кампаний с полями name, active, created_at, genre, tone, description
    """
    return list_campaigns()


@app.post("/api/campaigns", status_code=201)
async def api_create_campaign(body: CreateCampaignRequest):
    """Создать новую кампанию.

    Args:
        body: Данные новой кампании (name обязательно)

    Returns:
        dict: Информация о созданной кампании или ошибка 400/409
    """
    result = create_campaign(
        name=body.name,
        genre=body.genre or "",
        tone=body.tone or "",
        description=body.description or "",
        modules=body.modules,
        narrator_style=body.narrator_style or "",
    )

    if not result.get("success"):
        error_msg = result.get("error", "Ошибка создания кампании")
        # Кампания уже существует → 409 Conflict, иначе 400 Bad Request
        status_code = 409 if "уже существует" in error_msg else 400
        raise HTTPException(status_code=status_code, detail=error_msg)

    return result


@app.post("/api/campaigns/{name}/activate")
async def api_activate_campaign(name: str):
    """Активировать кампанию по имени.

    Args:
        name: Имя кампании для активации

    Returns:
        dict: {"success": true, "name": "..."}  или ошибка 404
    """
    result = activate_campaign(name)

    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", f"Кампания '{name}' не найдена"),
        )

    return result


@app.delete("/api/campaigns/{name}", status_code=200)
async def api_delete_campaign(name: str):
    """Удалить кампанию и все её данные.

    Args:
        name: Имя кампании для удаления

    Returns:
        dict: {"success": true}  или ошибка 404/409
    """
    result = delete_campaign(name)

    if not result.get("success"):
        error_msg = result.get("error", "Ошибка удаления")
        status_code = 409 if "активную кампанию" in error_msg else 404
        raise HTTPException(status_code=status_code, detail=error_msg)

    return result


# ─────────────────────────── Вспомогательные функции для шаблонов ─────────────

def _parse_md_frontmatter(path: Path) -> dict:
    """Извлечь поля id/name/description/genres из markdown-файла стилей.

    Формат файла:
        ## id
        some-id
        ## name
        Some Name
        ## description
        Some description text...

    Args:
        path: Путь к .md файлу

    Returns:
        dict: Словарь с полями id, name, description и genres (list)
    """
    text = path.read_text(encoding="utf-8")
    result: dict = {"id": path.stem, "name": path.stem, "description": "", "genres": []}

    # Разбиваем на секции вида "## key\nvalue"
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
    """Получить путь к директории модулей относительно корня проекта."""
    config = get_config()
    return Path(config.project_root) / ".claude" / "additional" / "modules"


def _get_narrator_styles_dir() -> Path:
    """Получить путь к директории нарраторских стилей."""
    config = get_config()
    return Path(config.project_root) / ".claude" / "additional" / "narrator-styles"


def _get_campaign_rules_templates_dir() -> Path:
    """Получить путь к директории шаблонов правил кампании."""
    config = get_config()
    return Path(config.project_root) / ".claude" / "additional" / "campaign-rules-templates"


# ─────────────────────────── Template API ──────────────────────────────────────

@app.get("/api/templates/modules")
async def api_get_template_modules():
    """Получить список доступных игровых модулей.

    Читает module.json из каждой поддиректории modules/ и возвращает
    метаданные: id, name, description, category, genre_tags, tags,
    enabled_by_default, features.

    Returns:
        list: Список модулей с полями из module.json
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
            # Пропускаем некорректные модули
            continue

    return result


@app.get("/api/templates/narrators")
async def api_get_template_narrators():
    """Получить список доступных стилей нарратора.

    Читает .md файлы из narrator-styles/ и извлекает секции
    id, name, description, genres.

    Returns:
        list: Список стилей нарратора с полями id, name, description, genres
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
    """Получить список шаблонов правил кампании.

    Читает .md файлы из campaign-rules-templates/ и извлекает секции
    id, name, description, genres.

    Returns:
        list: Список шаблонов правил с полями id, name, description, genres
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


# ─────────────────────────── Функции истории чата ─────────────────────────────

def _get_chat_history_path(campaign_dir: Path) -> Path:
    """Получить путь к файлу истории чата кампании.

    Args:
        campaign_dir: Директория кампании

    Returns:
        Path: Путь к chat-history.json
    """
    return campaign_dir / "chat-history.json"


def load_chat_history(campaign_dir: Path) -> List[dict]:
    """Загрузить историю чата из файла.

    Читает chat-history.json из директории кампании.
    Возвращает пустой список если файл отсутствует или повреждён.

    Args:
        campaign_dir: Директория активной кампании

    Returns:
        List[dict]: Список сообщений с полями role, content, timestamp
    """
    history_file = _get_chat_history_path(campaign_dir)
    if not history_file.exists():
        return []
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_chat_history(campaign_dir: Path, messages: List[dict]) -> None:
    """Сохранить историю чата в файл.

    Записывает chat-history.json в директорию кампании.
    Ошибки записи логируются, но не прерывают работу.

    Args:
        campaign_dir: Директория активной кампании
        messages: Список сообщений с полями role, content, timestamp
    """
    history_file = _get_chat_history_path(campaign_dir)
    try:
        campaign_dir.mkdir(parents=True, exist_ok=True)
        history_file.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"⚠️  Ошибка сохранения истории чата: {e}")


def _now_iso() -> str:
    """Получить текущее время в формате ISO 8601 UTC."""
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

    # Загружаем историю чата из файла при подключении
    campaign_dir: Optional[Path] = config.campaign_dir if config else None
    if campaign_dir:
        saved_messages = load_chat_history(campaign_dir)
        if saved_messages:
            # Восстанавливаем историю разговора для Claude
            for msg in saved_messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    conversation_history.append({"role": role, "content": content})

            # Отправляем историю клиенту как JSON-пакет
            history_packet = json.dumps({"type": "history", "messages": saved_messages})
            await websocket.send_text(history_packet)
            print(f"📜 История чата загружена: {len(saved_messages)} сообщений")
        else:
            print(f"📜 История чата пуста — начинаем новый разговор")
    else:
        print(f"⚠️  Активная кампания не задана — история чата не будет сохраняться")

    try:
        while True:
            # Receive message from player
            user_message = await websocket.receive_text()
            print(f"📩 Received message: {user_message[:50]}...")

            # Собираем полный ответ ассистента для сохранения в историю
            full_response_parts: List[str] = []

            # Process message through DM agent with streaming
            try:
                async for text_chunk in process_message(
                    user_message=user_message,
                    conversation_history=conversation_history,
                    provider_type=config.ai_provider,
                    api_key=config.anthropic_api_key,
                    model_name=config.model_name,
                    system_prompt=system_prompt,
                    project_root=config.project_root
                ):
                    # Stream each text chunk to frontend
                    await websocket.send_text(text_chunk)
                    full_response_parts.append(text_chunk)

                print(f"✅ Completed message processing")

                # Сохраняем ход в историю чата
                if campaign_dir and full_response_parts:
                    full_response = "".join(full_response_parts)
                    timestamp = _now_iso()

                    # Добавляем в conversation_history для следующего хода
                    conversation_history.append({"role": "user", "content": user_message})
                    conversation_history.append({"role": "assistant", "content": full_response})

                    # Персистируем историю на диск
                    all_saved = load_chat_history(campaign_dir)
                    all_saved.append({"role": "user", "content": user_message, "timestamp": timestamp})
                    all_saved.append({"role": "assistant", "content": full_response, "timestamp": timestamp})
                    save_chat_history(campaign_dir, all_saved)
                    print(f"💾 История чата сохранена ({len(all_saved)} сообщений)")

            except Exception as e:
                # Send error to client and log
                error_message = f"Error: {str(e)}"
                print(f"❌ DM Agent error: {error_message}")
                await websocket.send_text(f"\n\n{error_message}")

    except WebSocketDisconnect:
        # Client disconnected, cleanup connection
        print(f"🔌 WebSocket disconnected")
        pass
