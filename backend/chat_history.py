"""Модуль для хранения и загрузки истории чата по кампаниям.

История сохраняется в файл chat-history.json внутри директории кампании.
Каждое сообщение содержит роль, содержимое и временную метку.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


# Имя файла истории чата внутри директории кампании
CHAT_HISTORY_FILENAME = "chat-history.json"


def _get_history_path(campaign_dir: Path) -> Path:
    """Получить путь к файлу истории чата для кампании.

    Args:
        campaign_dir: Директория кампании

    Returns:
        Path: Путь к файлу chat-history.json
    """
    return campaign_dir / CHAT_HISTORY_FILENAME


def load_chat_history(campaign_dir: Path) -> List[Dict]:
    """Загрузить историю чата для кампании.

    Args:
        campaign_dir: Директория кампании (где хранится chat-history.json)

    Returns:
        List[Dict]: Список сообщений, каждое содержит:
            - role (str): Роль отправителя ("user", "assistant", "system")
            - content (str): Текст сообщения
            - timestamp (str): ISO 8601 временная метка

        Возвращает пустой список если файл не существует или повреждён.
    """
    history_path = _get_history_path(campaign_dir)

    if not history_path.exists():
        return []

    try:
        raw = history_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        if not isinstance(data, list):
            return []

        # Фильтруем только валидные записи
        messages = []
        for entry in data:
            if (
                isinstance(entry, dict)
                and "role" in entry
                and "content" in entry
                and "timestamp" in entry
            ):
                messages.append(entry)

        return messages

    except (json.JSONDecodeError, OSError):
        return []


def save_chat_history(campaign_dir: Path, messages: List[Dict]) -> None:
    """Сохранить историю чата для кампании.

    Args:
        campaign_dir: Директория кампании (где будет сохранён chat-history.json)
        messages: Список сообщений, каждое должно содержать:
            - role (str): Роль отправителя
            - content (str): Текст сообщения
            - timestamp (str): ISO 8601 временная метка

    Raises:
        OSError: Если не удаётся записать файл
    """
    campaign_dir.mkdir(parents=True, exist_ok=True)
    history_path = _get_history_path(campaign_dir)
    history_path.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_message(
    campaign_dir: Path,
    role: str,
    content: str,
    timestamp: Optional[str] = None,
) -> List[Dict]:
    """Добавить одно сообщение в историю чата.

    Args:
        campaign_dir: Директория кампании
        role: Роль отправителя ("user", "assistant", "system")
        content: Текст сообщения
        timestamp: ISO 8601 временная метка (по умолчанию — текущее время UTC)

    Returns:
        List[Dict]: Обновлённый список сообщений
    """
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + "Z"

    messages = load_chat_history(campaign_dir)
    messages.append({"role": role, "content": content, "timestamp": timestamp})
    save_chat_history(campaign_dir, messages)
    return messages


def clear_chat_history(campaign_dir: Path) -> None:
    """Очистить историю чата для кампании (сохраняет пустой список).

    Args:
        campaign_dir: Директория кампании
    """
    save_chat_history(campaign_dir, [])
