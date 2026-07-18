import asyncio
import json

import pytest

from backend.providers.codex_cli import (
    CodexCLIProvider,
    _read_rollout_context,
    normalize_codex_event,
)


class QueueStream:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def readline(self):
        return await self.queue.get()

    async def read(self, _size):
        return await self.queue.get()

    def feed_json(self, payload):
        self.queue.put_nowait((json.dumps(payload) + "\n").encode())

    def feed(self, chunk):
        self.queue.put_nowait(chunk)


class FakeStdin:
    def __init__(self, process):
        self.process = process

    def write(self, data):
        for line in data.decode().splitlines():
            if line:
                self.process.handle(json.loads(line))

    async def drain(self):
        return None


class FakeAppServerProcess:
    def __init__(
        self,
        *,
        thread_id="thread-1",
        auto_complete=True,
        turn_status="completed",
        turn_error=None,
        usage=None,
        exit_after_turn_start=False,
    ):
        self.stdout = QueueStream()
        self.stderr = QueueStream()
        self.stdin = FakeStdin(self)
        self.returncode = None
        self.thread_id = thread_id
        self.auto_complete = auto_complete
        self.turn_status = turn_status
        self.turn_error = turn_error
        self.usage = usage or {
            "inputTokens": 100,
            "cachedInputTokens": 80,
            "outputTokens": 20,
        }
        self.exit_after_turn_start = exit_after_turn_start
        self.requests = []
        self.terminated = False
        self.killed = False
        self._closed = asyncio.Event()
        self._turn_number = 0

    def _response(self, request, result=None, error=None):
        payload = {"id": request["id"]}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = result or {}
        self.stdout.feed_json(payload)

    def handle(self, request):
        self.requests.append(request)
        method = request.get("method")
        if request.get("id") is None:
            return
        if method == "initialize":
            self._response(request, {"userAgent": "fake-app-server"})
            return
        if method in {"thread/start", "thread/resume"}:
            self._response(request, {"thread": {"id": self.thread_id}})
            self.stdout.feed_json(
                {
                    "method": "thread/started",
                    "params": {
                        "thread": {"id": self.thread_id},
                        "threadId": self.thread_id,
                    },
                }
            )
            return
        if method == "turn/start":
            self._turn_number += 1
            turn_id = f"turn-{self._turn_number}"
            self._response(request, {"turn": {"id": turn_id}})
            if self.exit_after_turn_start:
                self.stderr.feed(b"authentication failed")
                self.stderr.feed(b"")
                self.returncode = 1
                self.stdout.feed(b"")
                self._closed.set()
                return
            self.stdout.feed_json(
                {
                    "method": "turn/started",
                    "params": {
                        "threadId": self.thread_id,
                        "turn": {"id": turn_id},
                    },
                }
            )
            if self.auto_complete:
                self.stdout.feed_json(
                    {
                        "method": "item/agentMessage/delta",
                        "params": {
                            "threadId": self.thread_id,
                            "turnId": turn_id,
                            "delta": "Ready",
                        },
                    }
                )
                self.stdout.feed_json(
                    {
                        "method": "item/completed",
                        "params": {
                            "threadId": self.thread_id,
                            "turnId": turn_id,
                            "item": {
                                "id": f"message-{self._turn_number}",
                                "type": "agentMessage",
                                "text": "Ready",
                            },
                        },
                    }
                )
                self.stdout.feed_json(
                    {
                        "method": "thread/tokenUsage/updated",
                        "params": {
                            "threadId": self.thread_id,
                            "turnId": turn_id,
                            "tokenUsage": {
                                "last": self.usage,
                                "total": self.usage,
                                "modelContextWindow": 200,
                            },
                        },
                    }
                )
                turn = {"id": turn_id, "status": self.turn_status}
                if self.turn_error:
                    turn["error"] = self.turn_error
                self.stdout.feed_json(
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": self.thread_id,
                            "turn": turn,
                        },
                    }
                )
            return
        if method == "turn/interrupt":
            self._response(request)
            self.stdout.feed_json(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": self.thread_id,
                        "turn": {
                            "id": request["params"]["turnId"],
                            "status": "interrupted",
                        },
                    },
                }
            )
            return
        if method == "thread/compact/start":
            self._response(request)
            compact_usage = {
                "inputTokens": 40,
                "cachedInputTokens": 20,
                "outputTokens": 5,
            }
            self.stdout.feed_json(
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "threadId": self.thread_id,
                        "turnId": "compact-1",
                        "tokenUsage": {
                            "last": compact_usage,
                            "total": compact_usage,
                            "modelContextWindow": 200,
                        },
                    },
                }
            )
            self.stdout.feed_json(
                {
                    "method": "thread/compacted",
                    "params": {"threadId": self.thread_id},
                }
            )

    async def wait(self):
        if self.returncode is None:
            await self._closed.wait()
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.stdout.feed(b"")
        self.stderr.feed(b"")
        self._closed.set()

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.stdout.feed(b"")
        self.stderr.feed(b"")
        self._closed.set()


def collect(provider, **kwargs):
    async def scenario():
        events = [
            event
            async for event in provider.process_message(
                kwargs.get("message", "continue"),
                kwargs.get("system_prompt", "Run the campaign."),
                kwargs.get("model", provider.model_name),
                kwargs.get("mcp_servers"),
            )
        ]
        await provider.close()
        return events

    return asyncio.run(scenario())


def test_normalizes_core_app_server_events():
    started = normalize_codex_event(
        {
            "method": "item/started",
            "params": {
                "item": {
                    "id": "command-1",
                    "type": "commandExecution",
                    "command": "pwd",
                }
            },
        }
    )
    completed = normalize_codex_event(
        {
            "method": "item/completed",
            "params": {
                "item": {
                    "id": "command-1",
                    "type": "commandExecution",
                    "aggregatedOutput": "/project",
                    "exitCode": 0,
                }
            },
        }
    )
    delta = normalize_codex_event(
        {
            "method": "item/agentMessage/delta",
            "params": {"delta": "Hello"},
        }
    )

    assert started[0].type == "tool_use"
    assert started[0].metadata["tool_name"] == "Bash"
    assert completed[0].type == "tool_result"
    assert completed[0].metadata["exit_code"] == 0
    assert delta[0].type == "text_delta"


def test_new_turn_uses_persistent_app_server_and_safe_sandbox(tmp_path):
    calls = []
    process = FakeAppServerProcess()

    async def factory(*command, **options):
        calls.append((command, options))
        return process

    provider = CodexCLIProvider(
        tmp_path,
        campaign_name="test-campaign",
        codex_bin="/usr/bin/codex",
        process_factory=factory,
    )
    events = collect(provider)

    command, options = calls[0]
    assert command[-2:] == ("app-server", "--stdio")
    assert "exec" not in command
    assert options["stdin"] == asyncio.subprocess.PIPE
    assert options["cwd"] == str(tmp_path.resolve())
    assert options["env"]["DM_ACTIVE_CAMPAIGN"] == "test-campaign"
    assert options["env"]["NO_COLOR"] == "1"
    assert options["env"]["TERM"] == "dumb"
    thread_start = next(
        request for request in process.requests if request.get("method") == "thread/start"
    )
    assert thread_start["params"]["sandbox"] == "workspace-write"
    assert thread_start["params"]["approvalPolicy"] == "never"
    assert thread_start["params"]["developerInstructions"] == "Run the campaign."
    assert provider.session_id == "thread-1"
    assert [event.type for event in events] == [
        "status",
        "status",
        "text_delta",
        "text",
        "turn_end",
    ]
    assert events[-1].metadata["session_id"] == "thread-1"


def test_second_turn_reuses_process_and_thread(tmp_path):
    calls = []
    process = FakeAppServerProcess(thread_id="thread-existing")

    async def factory(*command, **options):
        calls.append(command)
        return process

    provider = CodexCLIProvider(
        tmp_path,
        resume_thread_id="thread-existing",
        codex_bin="codex",
        process_factory=factory,
    )

    async def scenario():
        for message in ("first", "second"):
            events = [
                event
                async for event in provider.process_message(
                    message,
                    "system",
                    "gpt-5.6-sol",
                )
            ]
            assert events[-1].type == "turn_end"
        assert provider.is_alive is True
        await provider.close()

    asyncio.run(scenario())

    assert len(calls) == 1
    assert sum(r.get("method") == "thread/resume" for r in process.requests) == 1
    assert sum(r.get("method") == "turn/start" for r in process.requests) == 2


def test_mcp_servers_use_dotted_config_without_exposing_unsafe_names(tmp_path):
    provider = CodexCLIProvider(tmp_path)

    args = provider._mcp_config_args(
        {
            "game_tools": {
                "command": "uv",
                "args": ["run", "server.py"],
                "env": {"CAMPAIGN": "test"},
                "enabled_tools": ["show_choices", "bad tool"],
                "default_tools_approval_mode": "approve",
                "required": True,
            },
            "bad.name": {"command": "ignored"},
            "docs": {
                "url": "https://example.test/mcp",
                "bearer_token_env_var": "DOCS_TOKEN",
            },
        }
    )

    assert 'mcp_servers.game_tools.command="uv"' in args
    assert 'mcp_servers.game_tools.args=["run", "server.py"]' in args
    assert 'mcp_servers.game_tools.env={CAMPAIGN="test"}' in args
    assert 'mcp_servers.game_tools.enabled_tools=["show_choices"]' in args
    assert 'mcp_servers.game_tools.default_tools_approval_mode="approve"' in args
    assert "mcp_servers.game_tools.required=true" in args
    assert 'mcp_servers.docs.url="https://example.test/mcp"' in args
    assert not any("bad.name" in arg for arg in args)


def test_spark_uses_native_reasoning_profile(tmp_path):
    provider = CodexCLIProvider(tmp_path, model_name="gpt-5.3-codex-spark")

    command = provider._build_command(None)

    assert provider.reasoning_effort == "native"
    assert command[-2:] == ["app-server", "--stdio"]
    assert not any("model_reasoning_effort" in value for value in command)


def test_malformed_usage_is_normalized_without_crashing(tmp_path):
    process = FakeAppServerProcess(
        usage={
            "inputTokens": "unknown",
            "cachedInputTokens": -5,
            "outputTokens": None,
        }
    )

    async def factory(*_command, **_options):
        return process

    provider = CodexCLIProvider(tmp_path, process_factory=factory)
    events = collect(provider)
    end = events[-1]

    assert end.metadata["input_tokens"] == 0
    assert end.metadata["cached_input_tokens"] == 0
    assert end.metadata["output_tokens"] == 0


def test_process_exit_during_turn_is_reported(tmp_path):
    process = FakeAppServerProcess(exit_after_turn_start=True)

    async def factory(*_command, **_options):
        return process

    provider = CodexCLIProvider(tmp_path, process_factory=factory)
    events = collect(provider)

    assert [event.type for event in events][-2:] == ["error", "turn_end"]
    assert events[-1].metadata["ok"] is False
    assert events[-1].metadata["stop_reason"] == "process_exit_1"


def test_failed_turn_is_terminal_and_not_duplicated(tmp_path):
    process = FakeAppServerProcess(
        turn_status="failed",
        turn_error={"message": "model unavailable"},
    )

    async def factory(*_command, **_options):
        return process

    provider = CodexCLIProvider(tmp_path, process_factory=factory)
    events = collect(provider)

    assert [event.type for event in events][-2:] == ["error", "turn_end"]
    assert events[-2].content == "model unavailable"
    assert events[-1].metadata["stop_reason"] == "turn_failed"


def test_interrupt_uses_native_turn_interrupt(tmp_path):
    process = FakeAppServerProcess(auto_complete=False)

    async def factory(*_command, **_options):
        return process

    provider = CodexCLIProvider(tmp_path, process_factory=factory)

    async def scenario():
        await provider._connect("system", None)
        await provider._start_turn("wait")
        interrupted = await provider.interrupt()
        await provider.close()
        return interrupted

    interrupted = asyncio.run(scenario())

    assert interrupted is True
    request = next(
        request for request in process.requests if request.get("method") == "turn/interrupt"
    )
    assert request["params"] == {
        "threadId": "thread-1",
        "turnId": "turn-1",
    }


def test_compact_uses_native_thread_request_and_refreshes_usage(tmp_path):
    process = FakeAppServerProcess()

    async def factory(*_command, **_options):
        return process

    provider = CodexCLIProvider(tmp_path, process_factory=factory)

    async def scenario():
        await provider._connect("system", None)
        compacted = await provider.compact()
        usage = provider.get_context_usage()
        await provider.close()
        return compacted, usage

    compacted, usage = asyncio.run(scenario())

    assert compacted is True
    request = next(
        request
        for request in process.requests
        if request.get("method") == "thread/compact/start"
    )
    assert request["params"] == {"threadId": "thread-1"}
    assert usage.used_tokens == 40
    assert usage.percent == 20


def test_reset_forgets_thread_and_rejects_dangerous_sandbox(tmp_path):
    provider = CodexCLIProvider(tmp_path, resume_thread_id="thread-1")
    asyncio.run(provider.reset())
    assert provider.session_id is None

    with pytest.raises(ValueError, match="only permits"):
        CodexCLIProvider(tmp_path, sandbox="danger-full-access")


def test_rollout_context_uses_latest_model_call(tmp_path):
    rollout = tmp_path / "rollout-thread-1.jsonl"
    rows = [
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {
                        "input_tokens": 50,
                        "cached_input_tokens": 30,
                    },
                    "model_context_window": 200,
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {
                        "input_tokens": 90,
                        "cached_input_tokens": 70,
                    },
                    "model_context_window": 200,
                },
            },
        },
    ]
    rollout.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    usage = _read_rollout_context(rollout)

    assert usage is not None
    assert usage.used_tokens == 90
    assert usage.cached_input_tokens == 70
    assert usage.percent == 45


def test_context_usage_prefers_native_app_server_notification(tmp_path):
    process = FakeAppServerProcess()

    async def factory(*_command, **_options):
        return process

    provider = CodexCLIProvider(tmp_path, process_factory=factory)
    collect(provider)

    usage = provider.get_context_usage()

    assert usage is not None
    assert usage.used_tokens == 100
    assert usage.cached_input_tokens == 80
    assert usage.percent == 50


def test_context_usage_locates_thread_rollout(tmp_path):
    rollout = tmp_path / "nested" / "rollout-thread-9.jsonl"
    rollout.parent.mkdir()
    rollout.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"input_tokens": 25},
                        "model_context_window": 100,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    provider = CodexCLIProvider(
        tmp_path,
        resume_thread_id="thread-9",
        rollout_root=tmp_path,
    )

    usage = provider.get_context_usage()

    assert usage is not None
    assert usage.to_dict()["percent"] == 25
