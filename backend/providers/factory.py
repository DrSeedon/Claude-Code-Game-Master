"""Фабрика для создания AI провайдера на основе доступных credentials."""

import os
import logging
from pathlib import Path
from typing import Optional
from backend.providers.base import BaseProvider
from backend.providers.anthropic_api import AnthropicAPIProvider
from backend.providers.claude_sdk import ClaudeSDKProvider, SDK_AVAILABLE

logger = logging.getLogger(__name__)


def create_provider(
    provider_type: str = "auto",
    api_key: Optional[str] = None,
    project_root: Optional[Path] = None
) -> BaseProvider:
    """Создает подходящий AI провайдер на основе доступных credentials.

    Логика выбора:
    1. Если provider_type == "api" → Anthropic API (требует api_key)
    2. Если provider_type == "sdk" → Claude SDK (требует подписку)
    3. Если provider_type == "auto" (по умолчанию):
       - Если ANTHROPIC_API_KEY есть в env → Anthropic API
       - Иначе → Claude SDK (подписка)

    Args:
        provider_type: Тип провайдера ("auto", "api", "sdk")
        api_key: Anthropic API key (опционально, берется из env если не указан)
        project_root: Корень проекта для SDK провайдера (нужен для cwd)

    Returns:
        Экземпляр BaseProvider (AnthropicAPIProvider или ClaudeSDKProvider)

    Raises:
        ValueError: Если запрошенный провайдер недоступен
    """
    # Получаем API key из env если не передан
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    # Определяем project_root если не передан
    if project_root is None:
        # По умолчанию - родительская директория backend/
        project_root = Path(__file__).parent.parent.parent.absolute()

    # Автоматический выбор провайдера
    if provider_type == "auto":
        if api_key:
            logger.info("🔑 Автовыбор провайдера: Anthropic API (найден ANTHROPIC_API_KEY)")
            provider_type = "api"
        else:
            logger.info("🎫 Автовыбор провайдера: Claude SDK (подписка)")
            provider_type = "sdk"

    # Создаем провайдер API
    if provider_type == "api":
        if not api_key:
            raise ValueError(
                "Anthropic API провайдер требует ANTHROPIC_API_KEY. "
                "Установите в .env файле или используйте AI_PROVIDER=sdk"
            )
        logger.info("✅ Используем провайдер: Anthropic API")
        return AnthropicAPIProvider(api_key=api_key)

    # Создаем провайдер SDK
    elif provider_type == "sdk":
        if not SDK_AVAILABLE:
            raise ValueError(
                "Claude SDK не установлен. Установите с помощью: pip install claude-agent-sdk\n"
                "Или используйте AI_PROVIDER=api с ANTHROPIC_API_KEY"
            )
        logger.info("✅ Используем провайдер: Claude SDK (подписка)")
        return ClaudeSDKProvider(project_root=project_root)

    else:
        raise ValueError(
            f"Неизвестный тип провайдера: {provider_type}. "
            f"Доступные: 'auto', 'api', 'sdk'"
        )
