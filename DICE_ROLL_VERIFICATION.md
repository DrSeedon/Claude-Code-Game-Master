# E2E Верификация: Dice Roll Flow

## Задача
Проверить, что DM agent корректно обрабатывает запросы на броски кубиков через tool calling.

## Verification Steps

### ✅ Шаг 1: Проверка интеграции DM agent в WebSocket

**Файл:** `backend/server.py`

**Проверено:**
- ✅ Импорт `process_message` и `load_system_prompt` из `backend.claude_dm`
- ✅ WebSocket endpoint инициализирует `conversation_history`
- ✅ WebSocket endpoint загружает `system_prompt` через `load_system_prompt()`
- ✅ WebSocket endpoint загружает конфигурацию через `get_config()`
- ✅ Цикл обработки сообщений использует `process_message()` с streaming
- ✅ Обработка ошибок с отправкой в WebSocket
- ✅ Graceful shutdown при отсутствии API ключа

**Код:**
```python
async for text_chunk in process_message(
    user_message=user_message,
    conversation_history=conversation_history,
    api_key=config.anthropic_api_key,
    model_name=config.model_name,
    system_prompt=system_prompt
):
    await websocket.send_text(text_chunk)
```

### ✅ Шаг 2: Проверка DM agent tool calling loop

**Файл:** `backend/claude_dm.py`

**Проверено:**
- ✅ Функция `process_message()` - async generator для streaming
- ✅ Использует `AsyncAnthropic` client
- ✅ Поддерживает `conversation_history`
- ✅ Обнаруживает tool calls через `stop_reason == 'tool_use'`
- ✅ Выполняет tools через `execute_tool(block.name, block.input)`
- ✅ Добавляет tool results в conversation с `tool_use_id`
- ✅ Цикл продолжается до получения финального текстового ответа
- ✅ Обработка ошибок с `is_error` флагом
- ✅ Защита от бесконечных циклов (max_iterations = 10)

**Код:**
```python
if final_message.stop_reason == "tool_use":
    for block in final_message.content:
        if block.type == "tool_use":
            result = execute_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_str
            })
```

### ✅ Шаг 3: Проверка roll_dice tool registration

**Файл:** `backend/tools_registry.py`

**Проверено:**
- ✅ Tool schema `roll_dice` зарегистрирован в `get_tool_schemas()`
- ✅ Описание: "Roll dice with modifiers, advantage/disadvantage, and difficulty checks"
- ✅ Поддерживает параметры: `notation`, `expression`, `label`, `dc`, `ac`, `skill`, `save`, `attack`, `advantage`, `disadvantage`
- ✅ Функция `execute_tool()` обрабатывает `roll_dice` через `_execute_roll_dice()`
- ✅ Возвращает `{result: ...}` или `{error: ...}`

**Код:**
```python
{
    "name": "roll_dice",
    "description": "Roll dice with modifiers, advantage/disadvantage, and difficulty checks...",
    "input_schema": {
        "type": "object",
        "properties": {
            "notation": {...},
            "expression": {...},
            "label": {...},
            "dc": {...},
            ...
        },
        "required": []
    }
}
```

### ✅ Шаг 4: Проверка tool execution

**Файл:** `backend/tools_registry.py` (функция `_execute_roll_dice`)

**Проверено:**
- ✅ Поддержка `expression` и `notation` параметров (оба работают)
- ✅ Формирование команды для `dm-roll.sh` с правильными флагами
- ✅ Поддержка `--label`, `--dc`, `--ac`, `--advantage`, `--disadvantage`
- ✅ Subprocess вызов `bash tools/dm-roll.sh`
- ✅ Обработка stdout/stderr
- ✅ Возврат результата в формате `{result: stdout}`
- ✅ Обработка ошибок с `{error: stderr}`

**Код:**
```python
def _execute_roll_dice(params: dict) -> dict:
    expression = params.get("expression") or params.get("notation")
    cmd = ["bash", str(project_root / "tools" / "dm-roll.sh"), expression]
    if params.get("label"):
        cmd.extend(["--label", params["label"]])
    ...
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {"result": proc.stdout} if proc.returncode == 0 else {"error": proc.stderr}
```

## Ожидаемый Flow

### Сценарий: Пользователь пишет "I roll perception"

1. **Frontend** → WebSocket: отправляет текст "I roll perception"

2. **Backend WebSocket** → получает сообщение

3. **Backend** → вызывает `process_message()`:
   - Добавляет user message в conversation_history
   - Вызывает Claude API с system prompt и tools

4. **Claude API** → анализирует запрос, решает вызвать `roll_dice` tool:
   ```json
   {
     "type": "tool_use",
     "name": "roll_dice",
     "input": {
       "expression": "1d20",
       "label": "Perception check"
     }
   }
   ```

5. **Backend** → обнаруживает `stop_reason == 'tool_use'`

6. **Backend** → вызывает `execute_tool("roll_dice", {...})`

7. **Backend** → выполняет `bash tools/dm-roll.sh "1d20" --label "Perception check"`

8. **dm-roll.sh** → вызывает `lib/dice.py` → возвращает результат:
   ```
   🎲 Perception check: [14] (1d20=14)
   ```

9. **Backend** → добавляет tool result в conversation:
   ```json
   {
     "role": "user",
     "content": [{
       "type": "tool_result",
       "tool_use_id": "...",
       "content": "🎲 Perception check: [14] (1d20=14)"
     }]
   }
   ```

10. **Backend** → продолжает цикл, вызывает Claude API снова

11. **Claude API** → получает tool result, генерирует нарративный ответ:
    ```
    You rolled a 14 on your Perception check. As you scan the area, you notice...
    ```

12. **Backend** → стримит текст через WebSocket chunk by chunk

13. **Frontend** → отображает ответ DM word-by-word

## Verification Checklist

- ✅ WebSocket endpoint интегрирован с DM agent
- ✅ `process_message()` реализует tool calling loop
- ✅ `roll_dice` tool зарегистрирован в tool schemas
- ✅ `execute_tool()` корректно вызывает `dm-roll.sh`
- ✅ Tool results добавляются в conversation с `tool_use_id`
- ✅ Conversation loop продолжается до финального ответа
- ✅ Streaming text отправляется через WebSocket
- ✅ Обработка ошибок реализована на всех уровнях

## Manual Testing Steps

Для полной E2E верификации с реальным API:

1. Установить `ANTHROPIC_API_KEY` в `.env`:
   ```bash
   echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
   ```

2. Запустить backend:
   ```bash
   uv run uvicorn backend.server:app --reload
   ```

3. Запустить frontend:
   ```bash
   cd frontend && npm run dev
   ```

4. Открыть http://localhost:5173 в браузере

5. Написать в чат: "I roll perception"

6. Проверить backend логи:
   ```
   📩 Received message: I roll perception...
   ✅ Completed message processing
   ```

7. Проверить ответ DM:
   - ✅ Содержит результат броска (число)
   - ✅ Содержит нарративный текст
   - ✅ Имеет смысл в контексте запроса

8. Проверить DevTools Console:
   - ✅ Нет ошибок JavaScript
   - ✅ WebSocket connection status = "connected"

## Expected Output Example

**User input:**
```
I roll perception
```

**DM response (expected format):**
```
You rolled a 14 on your Perception check. As you carefully scan your surroundings, 
you notice subtle details that others might miss. [Narrative continues based on 
the scene context...]
```

## Status

✅ **COMPLETE** - All code integration verified

**Code changes made:**
1. ✅ `backend/server.py` - Интегрирован DM agent в WebSocket endpoint
2. ✅ `test_e2e_dice_roll.py` - Создан E2E тест для автоматической проверки

**Remaining:**
- Manual testing with real ANTHROPIC_API_KEY (requires user configuration)

**Notes:**
- Структура кода полностью готова для dice roll flow
- Все компоненты корректно связаны
- Tool calling loop реализован согласно Anthropic SDK best practices
- Тест можно запустить после настройки API ключа
