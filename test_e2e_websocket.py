#!/usr/bin/env python3
"""
E2E тест для WebSocket chat flow
Запускает backend сервер и тестирует WebSocket подключение
"""

import asyncio
import sys
import time
import subprocess
import signal
import json
from pathlib import Path

# Добавляем websockets если есть
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("⚠️  Модуль websockets не установлен, будет использован упрощённый тест")


class ServerManager:
    """Менеджер для запуска/остановки backend сервера"""

    def __init__(self):
        self.process = None

    def start(self, port=8000):
        """Запуск backend сервера"""
        print(f"🚀 Запуск backend сервера на порту {port}...")

        env = {
            **subprocess.os.environ.copy(),
            'UV_CACHE_DIR': str(Path.cwd() / '.uv-cache'),
        }

        self.process = subprocess.Popen(
            ['uv', 'run', 'uvicorn', 'backend.server:app', '--host', '127.0.0.1', '--port', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            preexec_fn=subprocess.os.setsid  # Создать новую группу процессов
        )

        # Ждём запуска сервера
        print("  Ожидание запуска сервера...")
        max_wait = 15
        start_time = time.time()

        for line in self.process.stdout:
            print(f"  [backend] {line.strip()}")

            if "Application startup complete" in line:
                print("  ✅ Backend сервер запущен")
                return True

            if time.time() - start_time > max_wait:
                print(f"  ❌ Таймаут запуска сервера ({max_wait}s)")
                self.stop()
                return False

            if self.process.poll() is not None:
                print(f"  ❌ Процесс backend завершился с кодом {self.process.returncode}")
                return False

        return False

    def stop(self):
        """Остановка backend сервера"""
        if self.process:
            print("🛑 Остановка backend сервера...")
            try:
                # Отправить SIGTERM всей группе процессов
                subprocess.os.killpg(subprocess.os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
                print("  ✅ Backend сервер остановлен")
            except subprocess.TimeoutExpired:
                print("  ⚠️  Принудительная остановка (SIGKILL)...")
                subprocess.os.killpg(subprocess.os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()
            except Exception as e:
                print(f"  ⚠️  Ошибка при остановке: {e}")
            finally:
                self.process = None


async def test_websocket_connection(url="ws://127.0.0.1:8000/ws/game"):
    """Тест WebSocket подключения"""
    print(f"\n✓ Тест WebSocket: подключение к {url}")

    try:
        async with websockets.connect(url) as websocket:
            print("  ✅ WebSocket подключение установлено")

            # Отправка тестового сообщения
            test_message = "Hello, DM!"
            print(f"  📤 Отправка сообщения: '{test_message}'")
            await websocket.send(test_message)

            # Ожидание ответа (с таймаутом)
            print("  ⏳ Ожидание ответа от DM (макс. 30s)...")
            response_chunks = []
            timeout_seconds = 30
            start_time = time.time()

            while time.time() - start_time < timeout_seconds:
                try:
                    chunk = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_chunks.append(chunk)
                    print(f"  📥 Получен чанк: '{chunk[:50]}...'")

                    # Если получили достаточно данных, прерываем
                    if len(''.join(response_chunks)) > 50:
                        break
                except asyncio.TimeoutError:
                    # Если 5 секунд нет новых чанков, считаем что ответ завершён
                    if response_chunks:
                        break
                    continue

            full_response = ''.join(response_chunks)

            if full_response:
                print(f"  ✅ Получен ответ от DM ({len(full_response)} символов)")
                print(f"  💬 Начало ответа: '{full_response[:100]}...'")
                return True
            else:
                print(f"  ⚠️  Ответ от DM не получен за {timeout_seconds}s (возможно требуется ANTHROPIC_API_KEY)")
                return False

    except websockets.exceptions.WebSocketException as e:
        print(f"  ❌ Ошибка WebSocket: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Неожиданная ошибка: {e}")
        return False


def test_http_health(port=8000):
    """Тест HTTP health endpoint"""
    print(f"\n✓ Тест HTTP: GET /api/health")

    try:
        import urllib.request

        url = f"http://127.0.0.1:{port}/api/health"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())

            if data.get('status') == 'healthy':
                print(f"  ✅ Health check пройден: {data}")
                return True
            else:
                print(f"  ❌ Неожиданный статус: {data}")
                return False

    except Exception as e:
        print(f"  ❌ Ошибка HTTP запроса: {e}")
        return False


def test_http_status(port=8000):
    """Тест HTTP status endpoint"""
    print(f"\n✓ Тест HTTP: GET /api/status")

    try:
        import urllib.request

        url = f"http://127.0.0.1:{port}/api/status"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())

            # Ожидаем либо данные персонажа, либо ошибку
            if 'error' in data or 'hp' in data:
                print(f"  ✅ Status endpoint работает: {list(data.keys())}")
                return True
            else:
                print(f"  ❌ Неожиданный формат ответа: {data}")
                return False

    except Exception as e:
        print(f"  ❌ Ошибка HTTP запроса: {e}")
        return False


async def run_integration_tests():
    """Запуск интеграционных тестов с реальным сервером"""
    print("=" * 70)
    print("🧪 E2E ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ: WebSocket Chat Flow")
    print("=" * 70)

    server = ServerManager()
    results = []

    try:
        # Запуск сервера
        if not server.start(port=8000):
            print("\n❌ Не удалось запустить backend сервер")
            return 1

        # Даём серверу время на полную инициализацию
        await asyncio.sleep(2)

        # HTTP тесты
        results.append(("HTTP Health Check", test_http_health()))
        results.append(("HTTP Status Endpoint", test_http_status()))

        # WebSocket тесты (если доступны)
        if HAS_WEBSOCKETS:
            ws_result = await test_websocket_connection()
            results.append(("WebSocket Connection & Chat", ws_result))
        else:
            print("\n⚠️  WebSocket тесты пропущены (модуль websockets не установлен)")
            results.append(("WebSocket Connection & Chat", None))

    except KeyboardInterrupt:
        print("\n⚠️  Тестирование прервано пользователем")
    finally:
        server.stop()

    # Итоговый отчёт
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 70)

    passed = sum(1 for _, result in results if result is True)
    skipped = sum(1 for _, result in results if result is None)
    failed = sum(1 for _, result in results if result is False)
    total = len(results)

    for test_name, result in results:
        if result is True:
            status = "✅ PASS"
        elif result is None:
            status = "⏭️  SKIP"
        else:
            status = "❌ FAIL"
        print(f"{status} - {test_name}")

    print("=" * 70)
    print(f"Пройдено: {passed}/{total}, Пропущено: {skipped}, Провалено: {failed}")

    if failed == 0 and passed > 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return 0
    elif failed > 0:
        print(f"⚠️  Провалено тестов: {failed}")
        return 1
    else:
        print("⚠️  Тесты не были выполнены")
        return 1


def main():
    """Точка входа"""
    try:
        result = asyncio.run(run_integration_tests())
        sys.exit(result)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
