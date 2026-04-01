#!/usr/bin/env python3
"""
E2E тест для базового chat flow
Проверяет импорты, конфигурацию и базовую функциональность
"""

import sys
import os

def test_backend_imports():
    """Тест 1: Проверка импортов backend"""
    print("✓ Тест 1: Проверка импортов backend...")
    try:
        from backend.config import get_config
        from backend.server import app
        from backend.tools_registry import get_tool_schemas, execute_tool
        from backend.claude_dm import load_system_prompt, process_message
        from backend.game_state import get_character_status
        print("  ✅ Все backend модули импортируются корректно")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка импорта backend: {e}")
        return False

def test_tool_registry():
    """Тест 2: Проверка регистрации инструментов"""
    print("\n✓ Тест 2: Проверка tool registry...")
    try:
        from backend.tools_registry import get_tool_schemas, execute_tool

        schemas = get_tool_schemas()
        print(f"  ℹ️  Зарегистрировано инструментов: {len(schemas)}")

        if len(schemas) < 8:
            print(f"  ❌ Недостаточно инструментов (требуется ≥8, получено {len(schemas)})")
            return False

        # Проверка наличия ключевых инструментов
        tool_names = [schema['name'] for schema in schemas]
        required_tools = ['roll_dice', 'inventory_show', 'session_move']

        for tool in required_tools:
            if tool not in tool_names:
                print(f"  ❌ Отсутствует обязательный инструмент: {tool}")
                return False

        print(f"  ✅ Все обязательные инструменты зарегистрированы")
        print(f"  📋 Список инструментов: {', '.join(tool_names[:5])}...")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка в tool registry: {e}")
        return False

def test_system_prompt():
    """Тест 3: Проверка загрузки system prompt"""
    print("\n✓ Тест 3: Проверка system prompt loader...")
    try:
        from backend.claude_dm import load_system_prompt

        prompt = load_system_prompt()
        prompt_length = len(prompt)

        print(f"  ℹ️  Длина системного промпта: {prompt_length} символов")

        if prompt_length < 100:
            print(f"  ❌ System prompt слишком короткий ({prompt_length} < 100)")
            return False

        print(f"  ✅ System prompt загружен корректно")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка загрузки system prompt: {e}")
        return False

def test_game_state():
    """Тест 4: Проверка game state cache"""
    print("\n✓ Тест 4: Проверка game state...")
    try:
        from backend.game_state import get_character_status

        status = get_character_status()

        # Ожидаем либо данные персонажа, либо ошибку об отсутствии кампании
        if 'error' in status:
            print(f"  ⚠️  Нет активной кампании (это OK для тестирования): {status['error']}")
        elif 'hp' in status:
            print(f"  ✅ Game state работает: HP={status.get('hp', 'N/A')}, Gold={status.get('gold', 'N/A')}")
        else:
            print(f"  ❌ Неожиданный формат ответа game state: {status}")
            return False

        return True
    except Exception as e:
        print(f"  ❌ Ошибка в game state: {e}")
        return False

def test_fastapi_app():
    """Тест 5: Проверка FastAPI приложения"""
    print("\n✓ Тест 5: Проверка FastAPI app...")
    try:
        from backend.server import app

        # Проверка наличия маршрутов
        routes = [route.path for route in app.routes]

        required_routes = ['/api/health', '/api/status', '/ws/game']
        missing_routes = [r for r in required_routes if r not in routes]

        if missing_routes:
            print(f"  ❌ Отсутствуют маршруты: {missing_routes}")
            return False

        print(f"  ✅ Все обязательные маршруты присутствуют")
        print(f"  📋 Маршруты: {', '.join(required_routes)}")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка в FastAPI app: {e}")
        return False

def test_frontend_build():
    """Тест 6: Проверка TypeScript компиляции frontend"""
    print("\n✓ Тест 6: Проверка frontend build...")
    try:
        import subprocess

        result = subprocess.run(
            ['npm', 'run', 'build'],
            cwd='frontend',
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print(f"  ✅ Frontend успешно скомпилирован")
            return True
        else:
            print(f"  ❌ Ошибка компиляции frontend:")
            print(f"     {result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ❌ Таймаут при компиляции frontend (>60s)")
        return False
    except Exception as e:
        print(f"  ❌ Ошибка при сборке frontend: {e}")
        return False

def main():
    """Запуск всех тестов"""
    print("=" * 70)
    print("🧪 E2E ТЕСТИРОВАНИЕ: Базовый Chat Flow")
    print("=" * 70)

    tests = [
        ("Backend Imports", test_backend_imports),
        ("Tool Registry", test_tool_registry),
        ("System Prompt", test_system_prompt),
        ("Game State", test_game_state),
        ("FastAPI App", test_fastapi_app),
        ("Frontend Build", test_frontend_build),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Неожиданная ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))

    # Итоговый отчёт
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("=" * 70)
    print(f"Пройдено тестов: {passed}/{total}")

    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return 0
    else:
        print(f"⚠️  Провалено тестов: {total - passed}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
