#!/usr/bin/env python3
"""
Структурный тест: Dice Roll Flow Integration
Проверяет, что все компоненты для dice roll flow корректно интегрированы
"""

import sys
import ast
from pathlib import Path


def test_server_dm_integration():
    """Проверка интеграции DM agent в server.py"""
    print("🔍 Test 1: Интеграция DM agent в WebSocket endpoint...")

    server_path = Path("backend/server.py")
    if not server_path.exists():
        print("  ❌ backend/server.py не найден")
        return False

    content = server_path.read_text()

    # Проверка импортов
    checks = [
        ("process_message import", "from backend.claude_dm import process_message"),
        ("load_system_prompt import", "load_system_prompt"),
        ("conversation_history", "conversation_history"),
        ("load_system_prompt() call", "load_system_prompt()"),
        ("process_message() call", "async for text_chunk in process_message"),
        ("api_key parameter", "api_key=config.anthropic_api_key"),
        ("model_name parameter", "model_name=config.model_name"),
        ("system_prompt parameter", "system_prompt=system_prompt"),
        ("websocket.send_text", "await websocket.send_text(text_chunk)"),
    ]

    all_passed = True
    for check_name, check_pattern in checks:
        if isinstance(check_pattern, str) and check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - не найден")
            all_passed = False

    return all_passed


def test_claude_dm_tool_calling():
    """Проверка tool calling loop в claude_dm.py"""
    print("\n🔍 Test 2: Tool calling loop в claude_dm.py...")

    claude_dm_path = Path("backend/claude_dm.py")
    if not claude_dm_path.exists():
        print("  ❌ backend/claude_dm.py не найден")
        return False

    content = claude_dm_path.read_text()

    checks = [
        ("process_message function", "async def process_message"),
        ("AsyncAnthropic", "AsyncAnthropic"),
        ("conversation_history", "conversation_history"),
        ("get_tool_schemas", "get_tool_schemas()"),
        ("tool_use detection", 'stop_reason == "tool_use"'),
        ("execute_tool call", "execute_tool(block.name, block.input)"),
        ("tool_result with tool_use_id", '"tool_use_id": block.id'),
        ("is_error flag", '"is_error"'),
        ("max_iterations", "max_iterations"),
        ("yield text chunks", "yield text"),
    ]

    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - не найден")
            all_passed = False

    return all_passed


def test_roll_dice_tool_schema():
    """Проверка регистрации roll_dice tool"""
    print("\n🔍 Test 3: Регистрация roll_dice tool...")

    registry_path = Path("backend/tools_registry.py")
    if not registry_path.exists():
        print("  ❌ backend/tools_registry.py не найден")
        return False

    content = registry_path.read_text()

    checks = [
        ("get_tool_schemas function", "def get_tool_schemas()"),
        ("roll_dice tool name", '"name": "roll_dice"'),
        ("roll_dice description", "Roll dice"),
        ("input_schema", '"input_schema"'),
        ("notation parameter", '"notation"'),
        ("expression parameter", '"expression"'),
        ("label parameter", '"label"'),
        ("advantage parameter", '"advantage"'),
        ("disadvantage parameter", '"disadvantage"'),
        ("dc parameter", '"dc"'),
    ]

    all_passed = True
    for check_name, check_pattern in checks:
        if isinstance(check_pattern, str) and check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - не найден")
            all_passed = False

    return all_passed


def test_roll_dice_execution():
    """Проверка выполнения roll_dice tool"""
    print("\n🔍 Test 4: Реализация execute_tool для roll_dice...")

    registry_path = Path("backend/tools_registry.py")
    content = registry_path.read_text()

    checks = [
        ("execute_tool function", "def execute_tool("),
        ("_execute_roll_dice function", "def _execute_roll_dice("),
        ("expression/notation support", "params.get(\"expression\") or params.get(\"notation\")"),
        ("dm-roll.sh call", '"dm-roll.sh"'),
        ("subprocess.run", "subprocess.run"),
        ("result dict", '{"result"'),
        ("error dict", '{"error"'),
        ("label flag", '"--label"'),
        ("advantage flag", '"--advantage"'),
        ("dc flag", '"--dc"'),
    ]

    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - не найден")
            all_passed = False

    return all_passed


def test_conversation_flow():
    """Проверка полного flow conversation"""
    print("\n🔍 Test 5: Полный conversation flow...")

    claude_dm_path = Path("backend/claude_dm.py")
    content = claude_dm_path.read_text()

    checks = [
        ("User message append", 'conversation_history.append'),
        ("Assistant message append", '"role": "assistant"'),
        ("Tool results append", 'tool_results'),
        ("Loop continuation", "while iteration < max_iterations"),
        ("Stream iteration", "async for text in stream.text_stream"),
        ("Final message check", "final_message = await stream.get_final_message()"),
        ("Break on non-tool response", "break"),
    ]

    all_passed = True
    for check_name, check_pattern in checks:
        if isinstance(check_pattern, str) and check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - не найден")
            all_passed = False

    return all_passed


def run_structural_tests():
    """Запуск всех структурных тестов"""
    print("=" * 70)
    print("СТРУКТУРНЫЙ ТЕСТ: Dice Roll Flow Integration")
    print("=" * 70)

    results = []

    results.append(("WebSocket DM integration", test_server_dm_integration()))
    results.append(("Tool calling loop", test_claude_dm_tool_calling()))
    results.append(("roll_dice tool schema", test_roll_dice_tool_schema()))
    results.append(("roll_dice execution", test_roll_dice_execution()))
    results.append(("Conversation flow", test_conversation_flow()))

    # Summary
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ ТЕСТОВ")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status:10} {test_name}")

    print("\n" + "-" * 70)
    print(f"Итого: {passed}/{total} тестов пройдено")

    if failed == 0:
        print("\n✅ Все структурные проверки пройдены!")
        print("   Код готов для dice roll flow")
        return 0
    else:
        print(f"\n❌ {failed} тестов не прошли")
        return 1


if __name__ == "__main__":
    sys.exit(run_structural_tests())
