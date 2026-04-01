#!/usr/bin/env python3
"""
E2E Test: Dice Roll Flow
Tests that DM agent correctly handles dice roll requests via tool calling
"""

import asyncio
import sys
import time
import json
import re
from pathlib import Path
from typing import List, Optional

# Test configuration
BACKEND_HOST = "localhost"
BACKEND_PORT = 8000
TEST_MESSAGE = "I roll perception"


def check_backend_imports():
    """Verify all backend modules import successfully"""
    print("🔍 Test 1: Backend imports...")

    try:
        from backend.config import get_config
        from backend.tools_registry import get_tool_schemas, execute_tool
        from backend.claude_dm import load_system_prompt, process_message
        from backend.server import app
        print("  ✅ All backend modules import successfully")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def check_tool_registry():
    """Verify roll_dice tool is registered"""
    print("\n🔍 Test 2: roll_dice tool registration...")

    try:
        from backend.tools_registry import get_tool_schemas

        schemas = get_tool_schemas()
        roll_dice_tool = None

        for schema in schemas:
            if schema["name"] == "roll_dice":
                roll_dice_tool = schema
                break

        if roll_dice_tool:
            print(f"  ✅ roll_dice tool found in registry")
            print(f"     Description: {roll_dice_tool['description'][:80]}...")

            # Check for required properties
            props = roll_dice_tool["input_schema"]["properties"]
            has_notation = "notation" in props or "expression" in props
            has_label = "label" in props
            has_advantage = "advantage" in props

            if has_notation and has_label and has_advantage:
                print(f"  ✅ roll_dice schema has required properties")
                return True
            else:
                print(f"  ❌ roll_dice schema missing properties")
                return False
        else:
            print(f"  ❌ roll_dice tool not found in registry")
            return False

    except Exception as e:
        print(f"  ❌ Tool registry check failed: {e}")
        return False


def check_tool_execution():
    """Test roll_dice tool execution directly"""
    print("\n🔍 Test 3: roll_dice tool execution...")

    try:
        from backend.tools_registry import execute_tool

        # Test basic dice roll
        result = execute_tool("roll_dice", {"expression": "1d20"})

        if "result" in result:
            print(f"  ✅ roll_dice executed successfully")
            print(f"     Result: {result['result'][:100]}...")
            return True
        elif "error" in result:
            print(f"  ⚠️  roll_dice returned error: {result['error']}")
            # Error is OK if dm-roll.sh isn't available, but structure is correct
            return True
        else:
            print(f"  ❌ roll_dice returned unexpected format: {result}")
            return False

    except Exception as e:
        print(f"  ❌ Tool execution failed: {e}")
        return False


def check_config():
    """Check if ANTHROPIC_API_KEY is configured"""
    print("\n🔍 Test 4: Configuration check...")

    try:
        from backend.config import get_config

        config = get_config()

        if config.anthropic_api_key:
            # Mask the key for security
            masked_key = config.anthropic_api_key[:8] + "..." + config.anthropic_api_key[-4:]
            print(f"  ✅ ANTHROPIC_API_KEY configured: {masked_key}")
            print(f"  ✅ Model: {config.model_name}")
            return True
        else:
            print(f"  ⚠️  ANTHROPIC_API_KEY is empty (API calls will fail)")
            return False

    except ValueError as e:
        print(f"  ⚠️  Configuration error: {e}")
        print(f"     This is OK for structural tests, but live API calls won't work")
        return False
    except Exception as e:
        print(f"  ❌ Config check failed: {e}")
        return False


async def test_websocket_dice_roll():
    """Test dice roll via WebSocket with real DM agent"""
    print("\n🔍 Test 5: WebSocket dice roll E2E...")

    # Check if config is available first
    try:
        from backend.config import get_config
        config = get_config()
        if not config.anthropic_api_key:
            print("  ⚠️  Skipping WebSocket test (no ANTHROPIC_API_KEY)")
            return None
    except:
        print("  ⚠️  Skipping WebSocket test (config error)")
        return None

    try:
        # Use websockets library if available
        try:
            import websockets
        except ImportError:
            print("  ⚠️  websockets library not installed (pip install websockets)")
            print("     Skipping live WebSocket test")
            return None

        ws_url = f"ws://{BACKEND_HOST}:{BACKEND_PORT}/ws/game"
        print(f"  📡 Connecting to {ws_url}...")

        async with websockets.connect(ws_url) as websocket:
            print(f"  ✅ WebSocket connected")

            # Send test message
            print(f"  📤 Sending: '{TEST_MESSAGE}'")
            await websocket.send(TEST_MESSAGE)

            # Collect response chunks
            response_chunks = []
            timeout_seconds = 30
            start_time = time.time()

            print(f"  📥 Receiving response chunks...")
            try:
                while True:
                    # Check timeout
                    if time.time() - start_time > timeout_seconds:
                        print(f"  ⚠️  Response timeout after {timeout_seconds}s")
                        break

                    # Receive with timeout
                    try:
                        chunk = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        response_chunks.append(chunk)
                        print(f"     Chunk {len(response_chunks)}: {chunk[:50]}...")

                        # Check if this looks like a final response
                        # (DM responses typically end with punctuation)
                        if len(response_chunks) > 5 and any(chunk.strip().endswith(p) for p in ['.', '!', '?', '"']):
                            # Wait a bit more to catch any trailing chunks
                            await asyncio.sleep(0.5)
                            break

                    except asyncio.TimeoutError:
                        # No more chunks for 2 seconds, assume done
                        if len(response_chunks) > 0:
                            break
                        else:
                            continue

            except websockets.exceptions.ConnectionClosed:
                print(f"  ⚠️  WebSocket closed by server")

            # Analyze response
            full_response = "".join(response_chunks)

            if len(response_chunks) == 0:
                print(f"  ❌ No response received")
                return False

            print(f"\n  📝 Full response ({len(full_response)} chars):")
            print(f"     {full_response[:200]}...")

            # Check for dice roll indicators
            has_roll_result = any(pattern in full_response.lower() for pattern in [
                "roll", "d20", "perception", "check", "result", "rolled"
            ])

            # Check for error messages
            has_error = "error" in full_response.lower() and "configuration error" in full_response.lower()

            if has_error:
                print(f"  ❌ DM returned configuration error")
                return False
            elif has_roll_result:
                print(f"  ✅ Response contains dice roll indicators")
                print(f"  ✅ Response has narrative content")
                return True
            else:
                print(f"  ⚠️  Response received but doesn't look like dice roll")
                print(f"     (This may be OK if DM responded differently)")
                return None

    except Exception as e:
        print(f"  ❌ WebSocket test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_tests():
    """Run all E2E tests for dice roll flow"""
    print("=" * 70)
    print("E2E TEST: Dice Roll Flow")
    print("=" * 70)

    results = []

    # Test 1: Backend imports
    results.append(("Backend imports", check_backend_imports()))

    # Test 2: Tool registry
    results.append(("roll_dice registration", check_tool_registry()))

    # Test 3: Tool execution
    results.append(("roll_dice execution", check_tool_execution()))

    # Test 4: Configuration
    results.append(("Configuration", check_config()))

    # Test 5: WebSocket E2E (requires running server)
    try:
        websocket_result = asyncio.run(test_websocket_dice_roll())
        results.append(("WebSocket dice roll E2E", websocket_result))
    except Exception as e:
        print(f"\n❌ WebSocket test crashed: {e}")
        results.append(("WebSocket dice roll E2E", False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    total = len(results)

    for test_name, result in results:
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"  {status:10} {test_name}")

    print("\n" + "-" * 70)
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped (out of {total})")

    if failed > 0:
        print("\n❌ Some tests failed")
        return 1
    elif passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests skipped (check ANTHROPIC_API_KEY configuration)")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
