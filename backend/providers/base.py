"""Базовый интерфейс для AI провайдеров."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional


class BaseProvider(ABC):
    """Абстрактный базовый класс для всех AI провайдеров.

    Определяет единый интерфейс для работы с разными AI бэкендами
    (Anthropic API, Claude SDK, etc.).
    """

    @abstractmethod
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает сообщение пользователя и возвращает стриминг-ответ.

        Args:
            user_message: Сообщение от игрока
            conversation_history: История разговора (модифицируется на месте)
            system_prompt: Системный промпт с правилами DM
            model_name: Имя модели Claude
            tools: Список tool schemas в формате Anthropic

        Yields:
            Текстовые чанки из стриминг-ответа Claude
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Возвращает имя провайдера для логирования."""
        pass
