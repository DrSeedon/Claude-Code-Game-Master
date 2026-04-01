"""Провайдер для Claude Agent SDK (подписка, не требует API ключ)."""

import logging
from typing import AsyncGenerator, List, Dict, Any
from pathlib import Path

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from backend.providers.base import BaseProvider
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    BaseProvider = object  # Fallback for type hints

logger = logging.getLogger(__name__)


class ClaudeSDKProvider(BaseProvider if SDK_AVAILABLE else object):
    """AI провайдер через Claude Agent SDK (подписка).

    Требует:
    - Claude Code CLI установлен
    - OAuth токен из Claude Code (автоматически через CLI)
    - НЕ требует ANTHROPIC_API_KEY

    Этот провайдер подходит для пользователей с подпиской Claude Max/Pro.

    Важно: Tools должны быть зарегистрированы в allowed_tools как строки
    ("Read", "Bash", "dm_roll", и т.д.). SDK автоматически вызывает их.
    """

    def __init__(self, project_root: Path, model_name: str = "claude-3-5-sonnet-20241022"):
        """Инициализация провайдера.

        Args:
            project_root: Корневая директория проекта (для cwd)
            model_name: Имя модели Claude
        """
        if not SDK_AVAILABLE:
            raise ImportError(
                "claude-agent-sdk не установлен. Установите с помощью: pip install claude-agent-sdk"
            )

        self.project_root = project_root
        self.model_name = model_name
        self.client = None

    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает сообщение через Claude SDK с tool calling.

        Алгоритм SDK:
        1. client.query(message) отправляет сообщение
        2. client.receive_response() стримит ответ
        3. SDK автоматически вызывает tools при необходимости
        4. Возвращаем только текстовые части ответа

        ВАЖНО: SDK управляет tool calling автоматически. Нам нужно только
        зарегистрировать tools в allowed_tools и предоставить их имена.

        Args:
            user_message: Сообщение от игрока
            conversation_history: История разговора (модифицируется)
            system_prompt: Системный промпт DM
            model_name: Имя модели Claude
            tools: Tool schemas в формате Anthropic (конвертируются в имена)

        Yields:
            Текстовые чанки стриминг-ответа
        """
        # Конвертируем tool schemas в список имен для SDK
        # SDK ожидает просто список строк: ["Read", "Bash", "dm_roll", ...]
        allowed_tools = [tool["name"] for tool in tools]

        # Опции для SDK клиента
        options_kwargs = {
            "model": model_name,
            "system_prompt": system_prompt,
            "allowed_tools": allowed_tools,
            "max_turns": 10,  # Максимум итераций tool calling
            "cwd": str(self.project_root.resolve()),
            "max_thinking_tokens": None,  # Отключаем extended thinking для игры
        }

        # Создаем клиент SDK
        client = ClaudeSDKClient(options=ClaudeAgentOptions(**options_kwargs))

        try:
            # Используем async context manager
            async with client:
                # Отправляем сообщение пользователя
                await client.query(user_message)

                # Стримим ответ
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__

                    # Обрабатываем только текстовые сообщения от ассистента
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        # AssistantMessage может содержать текст или tool_use
                        content = msg.content
                        if isinstance(content, str):
                            # Текстовый контент - возвращаем его
                            yield content
                        elif hasattr(content, "text") and content.text:
                            # Structured content с текстом
                            yield content.text

                    # Игнорируем ToolCallMessage, ToolResultMessage - SDK обрабатывает их сам

        except Exception as e:
            logger.error(f"Ошибка Claude SDK провайдера: {e}", exc_info=True)
            yield f"\n\n[Ошибка: {str(e)}]"

        # Обновляем историю разговора после обработки
        # ПРИМЕЧАНИЕ: SDK управляет историей внутри сессии автоматически,
        # но для совместимости с API провайдером добавляем сообщения в историю
        conversation_history.append({
            "role": "user",
            "content": user_message
        })
        # Ответ ассистента будет добавлен вызывающим кодом (в claude_dm.py)

    def get_provider_name(self) -> str:
        """Возвращает имя провайдера."""
        return "Claude SDK (подписка)"
