"""Провайдер для Anthropic API (требует ANTHROPIC_API_KEY)."""

import json
from typing import AsyncGenerator, List, Dict, Any
from anthropic import AsyncAnthropic
from backend.providers.base import BaseProvider
from backend.tools_registry import execute_tool


class AnthropicAPIProvider(BaseProvider):
    """AI провайдер через Anthropic REST API.

    Требует:
    - ANTHROPIC_API_KEY в environment переменных
    - Использует AsyncAnthropic клиент для стриминга
    - Поддерживает tool calling через API

    Этот провайдер подходит для пользователей с API ключами от Anthropic.
    """

    def __init__(self, api_key: str):
        """Инициализация провайдера.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key
        self.client = AsyncAnthropic(api_key=api_key)

    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает сообщение через Anthropic API с tool calling loop.

        Алгоритм:
        1. Добавляет user_message в историю
        2. Стримит ответ от Claude
        3. Если stop_reason == "tool_use" — выполняет tools
        4. Добавляет результаты в историю и повторяет с шага 2
        5. Иначе — завершает

        Args:
            user_message: Сообщение от игрока
            conversation_history: История разговора (модифицируется)
            system_prompt: Системный промпт DM
            model_name: Имя модели Claude
            tools: Tool schemas в формате Anthropic

        Yields:
            Текстовые чанки стриминг-ответа
        """
        # Добавляем сообщение пользователя в историю
        conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Tool calling loop: продолжаем до финального текстового ответа
        max_iterations = 10  # Защита от бесконечных циклов
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Стримим ответ от Claude
            async with self.client.messages.stream(
                model=model_name,
                max_tokens=4096,
                system=system_prompt,
                messages=conversation_history,
                tools=tools
            ) as stream:
                # Отдаем стриминг-текст вызывающему коду
                async for text in stream.text_stream:
                    yield text

                # Получаем финальное сообщение для проверки tool calls
                final_message = await stream.get_final_message()

                # Добавляем ответ ассистента в историю
                conversation_history.append({
                    "role": "assistant",
                    "content": final_message.content
                })

                # Проверяем, запросил ли Claude выполнение tools
                if final_message.stop_reason == "tool_use":
                    # Выполняем все запрошенные tools
                    tool_results = []

                    for block in final_message.content:
                        if block.type == "tool_use":
                            try:
                                # Выполняем tool через tools_registry
                                result = execute_tool(block.name, block.input)

                                # Конвертируем результат в строку для Claude
                                if isinstance(result, dict):
                                    if "error" in result:
                                        # Tool вернул ошибку
                                        tool_results.append({
                                            "type": "tool_result",
                                            "tool_use_id": block.id,
                                            "content": result["error"],
                                            "is_error": True
                                        })
                                    else:
                                        # Tool выполнен успешно
                                        result_str = (
                                            json.dumps(result["result"])
                                            if isinstance(result.get("result"), dict)
                                            else str(result.get("result", ""))
                                        )
                                        tool_results.append({
                                            "type": "tool_result",
                                            "tool_use_id": block.id,
                                            "content": result_str
                                        })
                                else:
                                    # Fallback для не-dict результатов
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": block.id,
                                        "content": str(result)
                                    })

                            except Exception as e:
                                # Возвращаем ошибку Claude, чтобы он объяснил игроку
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": f"Error executing tool: {str(e)}",
                                    "is_error": True
                                })

                    # Добавляем результаты tools в историю
                    conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Продолжаем цикл — Claude обработает результаты в следующей итерации
                    # Не возвращаем текст здесь, просто продолжаем к следующему API вызову

                else:
                    # Нет tool use — финальный ответ получен, выходим из цикла
                    break

        # Если достигли максимума итераций, выдаем предупреждение
        if iteration >= max_iterations:
            yield "\n\n[Предупреждение: Достигнут лимит итераций tool calling]"

    def get_provider_name(self) -> str:
        """Возвращает имя провайдера."""
        return "Anthropic API"
