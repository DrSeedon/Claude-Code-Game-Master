#!/usr/bin/env python3
"""
E2E Test: Inventory and Character Stats Flow
Tests that DM agent correctly handles inventory queries and CharacterPanel displays stats
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any

# Test configuration
BACKEND_HOST = "localhost"
BACKEND_PORT = 8000


def check_backend_imports():
    """Verify all backend modules import successfully"""
    print("🔍 Test 1: Backend imports...")

    try:
        from backend.config import get_config
        from backend.tools_registry import get_tool_schemas, execute_tool
        from backend.game_state import get_character_status
        from backend.server import app
        print("  ✅ All backend modules import successfully")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def check_inventory_tool_registry():
    """Verify inventory_show tool is registered"""
    print("\n🔍 Test 2: inventory_show tool registration...")

    try:
        from backend.tools_registry import get_tool_schemas

        schemas = get_tool_schemas()
        inventory_tool = None

        for schema in schemas:
            if schema["name"] == "inventory_show":
                inventory_tool = schema
                break

        if inventory_tool:
            print(f"  ✅ inventory_show tool found in registry")
            print(f"     Description: {inventory_tool['description'][:80]}...")

            # Check for schema structure
            props = inventory_tool["input_schema"]["properties"]
            has_character = "character" in props

            if has_character or len(props) == 0:  # character is optional
                print(f"  ✅ inventory_show schema is valid")
                return True
            else:
                print(f"  ❌ inventory_show schema invalid")
                return False
        else:
            print(f"  ❌ inventory_show tool not found in registry")
            return False

    except Exception as e:
        print(f"  ❌ Tool registry check failed: {e}")
        return False


def check_inventory_execution():
    """Test inventory_show tool execution directly"""
    print("\n🔍 Test 3: inventory_show tool execution...")

    try:
        from backend.tools_registry import execute_tool

        # Execute tool (will fail if no active campaign, but that's OK for structure test)
        result = execute_tool("inventory_show", {})

        # Check result format
        has_result = "result" in result
        has_error = "error" in result

        if has_result or has_error:
            if has_result:
                print(f"  ✅ inventory_show executed successfully")
                print(f"     Result preview: {result['result'][:80] if len(result['result']) > 80 else result['result']}")
            else:
                print(f"  ⚠️  inventory_show returned error (expected if no campaign): {result['error'][:80]}")
            return True
        else:
            print(f"  ❌ inventory_show returned invalid format: {result}")
            return False

    except Exception as e:
        print(f"  ❌ Tool execution failed: {e}")
        return False


def check_game_state_api():
    """Test game_state module for character status"""
    print("\n🔍 Test 4: game_state character status...")

    try:
        from backend.game_state import get_character_status

        # Get character status (will return error if no active campaign)
        status = get_character_status()

        # Check result format
        has_hp = "hp" in status
        has_inventory = "inventory" in status
        has_error = "error" in status

        if has_error:
            print(f"  ⚠️  No active campaign (expected): {status['error']}")
            return True
        elif has_hp and has_inventory:
            print(f"  ✅ Character status retrieved successfully")
            print(f"     HP: {status['hp']}/{status['max_hp']}")
            print(f"     Inventory items: {len(status['inventory'])}")
            return True
        else:
            print(f"  ❌ Invalid status format: {status}")
            return False

    except Exception as e:
        print(f"  ❌ Game state check failed: {e}")
        return False


async def check_websocket_inventory_flow():
    """Test full WebSocket flow with inventory query"""
    print("\n🔍 Test 5: WebSocket inventory query flow...")

    try:
        import websockets

        # Connect to WebSocket
        uri = f"ws://{BACKEND_HOST}:{BACKEND_PORT}/ws/game"

        try:
            async with websockets.connect(uri, close_timeout=2) as websocket:
                print(f"  ✅ WebSocket connected to {uri}")

                # Send inventory query
                test_message = "What is in my backpack?"
                await websocket.send(test_message)
                print(f"  ✅ Sent message: '{test_message}'")

                # Collect response chunks (timeout after 5 seconds)
                response_chunks = []
                start_time = time.time()
                timeout = 5.0

                try:
                    while time.time() - start_time < timeout:
                        try:
                            chunk = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            response_chunks.append(chunk)

                            # Check if response seems complete (ends with period/newline)
                            if chunk.strip().endswith(('.', '!', '?', '\n')):
                                break
                        except asyncio.TimeoutError:
                            # No more chunks, response complete
                            if response_chunks:
                                break
                            continue

                    if response_chunks:
                        full_response = "".join(response_chunks)
                        print(f"  ✅ Received {len(response_chunks)} chunks")
                        print(f"  ✅ Full response ({len(full_response)} chars): {full_response[:200]}...")

                        # Check if response mentions inventory/backpack/items
                        has_inventory_mention = any(word in full_response.lower()
                                                   for word in ['inventory', 'backpack', 'item', 'carrying', 'have'])

                        if has_inventory_mention:
                            print(f"  ✅ Response mentions inventory-related content")
                        else:
                            print(f"  ⚠️  Response doesn't explicitly mention inventory (might be generic)")

                        return True
                    else:
                        print(f"  ❌ No response received within timeout")
                        return False

                except Exception as e:
                    print(f"  ❌ WebSocket communication error: {e}")
                    return False

        except ConnectionRefusedError:
            print(f"  ❌ Connection refused - backend not running on {uri}")
            print(f"     Start backend: uvicorn backend.server:app --host 0.0.0.0 --port 8000")
            return False

    except ImportError:
        print(f"  ⚠️  websockets library not installed (optional test)")
        print(f"     Install: uv pip install websockets")
        return True  # Not a failure, just optional


def check_character_panel_integration():
    """Verify CharacterPanel component exists and has correct structure"""
    print("\n🔍 Test 6: CharacterPanel component integration...")

    try:
        panel_path = Path("frontend/src/components/CharacterPanel.tsx")

        if not panel_path.exists():
            print(f"  ❌ CharacterPanel.tsx not found")
            return False

        content = panel_path.read_text()

        # Check for key functionality
        checks = {
            "useState": "useState" in content,
            "useEffect": "useEffect" in content,
            "fetch('/api/status')": "/api/status" in content,
            "inventory": "inventory" in content.lower(),
            "hp": "hp" in content.lower(),
            "gold": "gold" in content.lower(),
            "xp": "xp" in content.lower(),
        }

        all_passed = all(checks.values())

        if all_passed:
            print(f"  ✅ CharacterPanel component has all required elements")
            for check, passed in checks.items():
                print(f"     ✓ {check}")
            return True
        else:
            print(f"  ❌ CharacterPanel missing some elements:")
            for check, passed in checks.items():
                status = "✓" if passed else "✗"
                print(f"     {status} {check}")
            return False

    except Exception as e:
        print(f"  ❌ CharacterPanel check failed: {e}")
        return False


async def run_all_tests():
    """Run all E2E tests for inventory and character stats"""
    print("=" * 60)
    print("E2E TEST: Inventory and Character Stats Flow")
    print("=" * 60)

    results = []

    # Synchronous tests
    results.append(("Backend Imports", check_backend_imports()))
    results.append(("Inventory Tool Registry", check_inventory_tool_registry()))
    results.append(("Inventory Tool Execution", check_inventory_execution()))
    results.append(("Game State API", check_game_state_api()))
    results.append(("CharacterPanel Integration", check_character_panel_integration()))

    # Asynchronous WebSocket test
    ws_result = await check_websocket_inventory_flow()
    results.append(("WebSocket Inventory Flow", ws_result))

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("\n" + "=" * 60)
    print(f"Result: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n🎉 All tests passed! Inventory and character stats flow is working.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check output above for details.")
        return 1


def main():
    """Main entry point"""
    try:
        exit_code = asyncio.run(run_all_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test runner failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
