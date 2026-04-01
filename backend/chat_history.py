"""Module for storing and loading chat history per campaign.

History is saved to chat-history.json file inside campaign directory.
Each message contains role, content and timestamp.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


# Chat history filename inside campaign directory
CHAT_HISTORY_FILENAME = "chat-history.json"


def _get_history_path(campaign_dir: Path) -> Path:
    """Get path to chat history file for campaign.

    Args:
        campaign_dir: Campaign directory

    Returns:
        Path: Path to chat-history.json file
    """
    return campaign_dir / CHAT_HISTORY_FILENAME


def load_chat_history(campaign_dir: Path) -> List[Dict]:
    """Load chat history for campaign.

    Args:
        campaign_dir: Campaign directory (where chat-history.json is stored)

    Returns:
        List[Dict]: List of messages, each containing:
            - role (str): Sender role ("user", "assistant", "system")
            - content (str): Message text
            - timestamp (str): ISO 8601 timestamp

        Returns empty list if file doesn't exist or is corrupted.
    """
    history_path = _get_history_path(campaign_dir)

    if not history_path.exists():
        return []

    try:
        raw = history_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        if not isinstance(data, list):
            return []

        # Filter only valid entries
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
    """Save chat history for campaign.

    Args:
        campaign_dir: Campaign directory (where chat-history.json will be saved)
        messages: List of messages, each must contain:
            - role (str): Sender role
            - content (str): Message text
            - timestamp (str): ISO 8601 timestamp

    Raises:
        OSError: If file write fails
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
    """Append single message to chat history.

    Args:
        campaign_dir: Campaign directory
        role: Sender role ("user", "assistant", "system")
        content: Message text
        timestamp: ISO 8601 timestamp (defaults to current UTC time)

    Returns:
        List[Dict]: Updated message list
    """
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + "Z"

    messages = load_chat_history(campaign_dir)
    messages.append({"role": role, "content": content, "timestamp": timestamp})
    save_chat_history(campaign_dir, messages)
    return messages


def clear_chat_history(campaign_dir: Path) -> None:
    """Clear chat history for campaign (saves empty list).

    Args:
        campaign_dir: Campaign directory
    """
    save_chat_history(campaign_dir, [])
