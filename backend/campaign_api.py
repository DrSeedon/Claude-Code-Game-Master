"""API управления кампаниями для веб-клиента DM Game Master.

Предоставляет функции для листинга, создания, удаления и активации кампаний.
Все данные хранятся в world-state/campaigns/ на диске.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import get_project_root


# ─────────────────────────── вспомогательные функции ───────────────────────────

def _get_campaigns_dir() -> Path:
    """Вернуть путь к директории всех кампаний."""
    return get_project_root() / "world-state" / "campaigns"


def _get_active_campaign_file() -> Path:
    """Вернуть путь к файлу с именем активной кампании."""
    return get_project_root() / "world-state" / "active-campaign.txt"


def _read_campaign_overview(campaign_dir: Path) -> Dict:
    """Прочитать campaign-overview.json для кампании.

    Args:
        campaign_dir: Путь к директории кампании

    Returns:
        Dict с метаданными или пустой dict при отсутствии файла
    """
    overview_file = campaign_dir / "campaign-overview.json"
    if overview_file.exists():
        try:
            return json.loads(overview_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _campaign_to_info(campaign_name: str, campaigns_dir: Path, active_name: Optional[str]) -> Dict:
    """Собрать информационный dict для одной кампании.

    Args:
        campaign_name: Имя кампании (имя поддиректории)
        campaigns_dir: Путь к корневой директории кампаний
        active_name: Имя текущей активной кампании (или None)

    Returns:
        Dict с полями: name, active, created_at, genre, tone, description
    """
    campaign_dir = campaigns_dir / campaign_name
    overview = _read_campaign_overview(campaign_dir)

    return {
        "name": campaign_name,
        "active": campaign_name == active_name,
        "created_at": overview.get("created_at", ""),
        "genre": overview.get("genre", ""),
        "tone": overview.get("tone", ""),
        "description": overview.get("description", ""),
    }


# ─────────────────────────── публичные функции ─────────────────────────────────

def list_campaigns() -> List[Dict]:
    """Получить список всех доступных кампаний.

    Returns:
        Список словарей с информацией о каждой кампании:
            - name (str): Имя кампании
            - active (bool): Является ли кампания активной
            - created_at (str): Дата создания (из campaign-overview.json)
            - genre (str): Жанр кампании
            - tone (str): Тон/атмосфера кампании
            - description (str): Описание кампании
    """
    campaigns_dir = _get_campaigns_dir()
    campaigns_dir.mkdir(parents=True, exist_ok=True)

    # Определяем активную кампанию
    active_name = _get_active_campaign_name()

    campaigns = []
    for entry in sorted(campaigns_dir.iterdir()):
        if entry.is_dir():
            campaigns.append(_campaign_to_info(entry.name, campaigns_dir, active_name))

    return campaigns


def _get_active_campaign_name() -> Optional[str]:
    """Вернуть имя текущей активной кампании или None."""
    active_file = _get_active_campaign_file()
    if active_file.exists():
        name = active_file.read_text(encoding="utf-8").strip()
        campaign_dir = _get_campaigns_dir() / name
        if name and campaign_dir.exists():
            return name
    return None


def create_campaign(
    name: str,
    genre: str = "",
    tone: str = "",
    description: str = "",
    modules: Optional[List[str]] = None,
    narrator_style: str = "",
) -> Dict:
    """Создать новую кампанию.

    Создаёт директорию кампании и базовый campaign-overview.json.

    Args:
        name: Имя кампании (используется как имя директории)
        genre: Жанр кампании (например, "fantasy", "sci-fi")
        tone: Тон кампании (например, "dark", "heroic")
        description: Краткое описание кампании
        modules: Список активных модулей
        narrator_style: Стиль нарратора

    Returns:
        Dict с информацией о созданной кампании или ошибкой:
            - success (bool): Успех операции
            - name (str): Имя кампании (при успехе)
            - error (str): Сообщение об ошибке (при неудаче)

    Raises:
        ValueError: Если имя кампании содержит недопустимые символы
    """
    # Валидация имени
    if not name or not name.strip():
        return {"success": False, "error": "Имя кампании не может быть пустым"}

    # Разрешаем только безопасные символы для имени директории
    safe_name = name.strip()
    forbidden = set('/\\:*?"<>|')
    if any(c in forbidden for c in safe_name):
        return {
            "success": False,
            "error": f"Имя кампании содержит недопустимые символы: {forbidden & set(safe_name)}",
        }

    campaigns_dir = _get_campaigns_dir()
    campaigns_dir.mkdir(parents=True, exist_ok=True)

    campaign_dir = campaigns_dir / safe_name
    if campaign_dir.exists():
        return {"success": False, "error": f"Кампания '{safe_name}' уже существует"}

    # Создаём структуру директорий
    campaign_dir.mkdir(parents=True)

    # Формируем campaign-overview.json
    overview = {
        "name": safe_name,
        "genre": genre,
        "tone": tone,
        "description": description,
        "modules": modules or [],
        "narrator_style": narrator_style,
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "calendar": {},
        "currency": {},
    }

    overview_file = campaign_dir / "campaign-overview.json"
    overview_file.write_text(
        json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Создаём пустой world.json
    world_file = campaign_dir / "world.json"
    world_file.write_text(
        json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Создаём пустой session-log.md
    session_log = campaign_dir / "session-log.md"
    session_log.write_text(f"# Session Log: {safe_name}\n", encoding="utf-8")

    return {
        "success": True,
        "name": safe_name,
        "genre": genre,
        "tone": tone,
        "description": description,
        "created_at": overview["created_at"],
        "active": False,
    }


def delete_campaign(name: str) -> Dict:
    """Удалить кампанию и все её данные.

    Args:
        name: Имя кампании для удаления

    Returns:
        Dict с результатом:
            - success (bool): Успех операции
            - error (str): Сообщение об ошибке (при неудаче)
    """
    campaigns_dir = _get_campaigns_dir()
    campaign_dir = campaigns_dir / name

    if not campaign_dir.exists():
        return {"success": False, "error": f"Кампания '{name}' не найдена"}

    # Запрещаем удаление активной кампании
    active_name = _get_active_campaign_name()
    if active_name == name:
        return {
            "success": False,
            "error": f"Нельзя удалить активную кампанию '{name}'. Сначала активируйте другую.",
        }

    try:
        shutil.rmtree(campaign_dir)
    except OSError as e:
        return {"success": False, "error": f"Ошибка удаления: {str(e)}"}

    return {"success": True}


def activate_campaign(name: str) -> Dict:
    """Установить активную кампанию.

    Записывает имя в world-state/active-campaign.txt.

    Args:
        name: Имя кампании для активации

    Returns:
        Dict с результатом:
            - success (bool): Успех операции
            - name (str): Имя активированной кампании (при успехе)
            - error (str): Сообщение об ошибке (при неудаче)
    """
    campaigns_dir = _get_campaigns_dir()
    campaign_dir = campaigns_dir / name

    if not campaign_dir.exists():
        return {"success": False, "error": f"Кампания '{name}' не найдена"}

    active_file = _get_active_campaign_file()
    active_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        active_file.write_text(name, encoding="utf-8")
    except OSError as e:
        return {"success": False, "error": f"Ошибка записи активной кампании: {str(e)}"}

    return {"success": True, "name": name}


def get_campaign(name: str) -> Dict:
    """Получить информацию об одной кампании.

    Args:
        name: Имя кампании

    Returns:
        Dict с информацией о кампании или ошибкой
    """
    campaigns_dir = _get_campaigns_dir()
    campaign_dir = campaigns_dir / name

    if not campaign_dir.exists():
        return {"error": f"Кампания '{name}' не найдена"}

    active_name = _get_active_campaign_name()
    return _campaign_to_info(name, campaigns_dir, active_name)
