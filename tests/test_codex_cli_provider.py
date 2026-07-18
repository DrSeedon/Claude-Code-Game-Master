import asyncio
import json

import pytest

from backend.providers.codex_cli import (
    CodexCLIProvider,
    _read_rollout_context,
    normalize_codex_event,
)


class FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def readline(self):
        return self._chunks.pop(0) if self._chunks else b""

    async def read(self, _size):
        return self._chunks.pop(0) if self._chunks else b""


class FakeProcess:
    def __init__(self, stdout_lines, stderr=b"", returncode=0):
        self.stdout = FakeStream(stdout_lines)
        self.stderr = FakeStream([stderr] if stderr else [])
        self.returncode = None
        self._final_returncode = returncode
        self.terminated = False
        self.killed = False

    async def wait(self):
        self.returncode = self._final_returncode
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def collect(provider, **kwargs):
    async def scenario():
        return [
            event
            async for event in provider.process_message(
                kwargs.get("message", "continue"),
                kwargs.get("system_prompt", "Run the campaign."),
                kwargs.get("model", "gpt-5.6-sol"),
                kwargs.get("mcp_servers"),
            )
        ]

    return asyncio.run(scenario())


def test_normalizes_core_codex_events():
    started = normalize_codex_event(
        {
            "type": "item.started",
            "item": {"type": "command_execution", "command": "pwd"},
        }
    )
    completed = normalize_codex_event(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "aggregated_output": "/project",
                "exit_code": 0,
            },
        }
    )
    final = normalize_codex_event(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 80,
                "output_tokens": 20,
            },
        }
    )

    assert started[0].type == "tool_use"
    assert started[0].metadata["tool_name"] == "Bash"
    assert completed[0].type == "tool_result"
    assert completed[0].metadata["exit_code"] == 0
    assert final[0].metadata["input_tokens"] == 100


def test_malformed_usage_is_normalized_without_crashing():
    events = normalize_codex_event(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": "unknown",
                "cached_input_tokens": -5,
                "output_tokens": None,
            },
        }
    )

    assert events[0].metadata["input_tokens"] == 0
    assert events[0].metadata["cached_input_tokens"] == 0
    assert events[0].metadata["output_tokens"] == 0


def test_new_turn_uses_safe_workspace_sandbox_and_campaign_env(tmp_path):
    calls = []
    process = FakeProcess(
        [
            b'{"type":"thread.started","thread_id":"thread-1"}\n',
            b'{"type":"item.completed","item":{"type":"agent_message","text":"Ready"}}\n',
            b'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n',
        ]
    )

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
    assert command[:3] == ("/usr/bin/codex", "exec", "--json")
    assert "-s" in command
    assert command[command.index("-s") + 1] == "workspace-write"
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert options["cwd"] == str(tmp_path.resolve())
    assert options["env"]["DM_ACTIVE_CAMPAIGN"] == "test-campaign"
    assert provider.session_id == "thread-1"
    assert [event.type for event in events] == ["status", "text", "turn_end"]
    assert events[-1].metadata["session_id"] == "thread-1"


def test_second_turn_resumes_persistent_thread(tmp_path):
    calls = []

    async def factory(*command, **options):
        calls.append(command)
        return FakeProcess(
            [
                b'{"type":"turn.completed","usage":{"input_tokens":20,"output_tokens":3}}\n',
            ]
        )

    provider = CodexCLIProvider(
        tmp_path,
        resume_thread_id="thread-existing",
        codex_bin="codex",
        process_factory=factory,
    )
    collect(provider)

    command = calls[0]
    assert command[:3] == ("codex", "exec", "resume")
    assert "thread-existing" in command
    assert "-C" not in command
    assert any(
        value == 'sandbox_mode="workspace-write"'
        for value in command
    )


def test_mcp_servers_use_dotted_config_without_exposing_unsafe_names(tmp_path):
    provider = CodexCLIProvider(tmp_path)

    args = provider._mcp_config_args(
        {
            "game_tools": {
                "command": "uv",
                "args": ["run", "server.py"],
                "env": {"CAMPAIGN": "test"},
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
    assert 'mcp_servers.docs.url="https://example.test/mcp"' in args
    assert not any("bad.name" in arg for arg in args)


def test_spark_uses_its_native_reasoning_profile(tmp_path):
    provider = CodexCLIProvider(tmp_path, model_name="gpt-5.3-codex-spark")

    command = provider._build_command(
        "Make a targeted edit.",
        "Follow the project rules.",
        "gpt-5.3-codex-spark",
        None,
    )

    assert "gpt-5.3-codex-spark" in command
    assert not any("model_reasoning_effort" in value for value in command)


def test_process_exit_without_turn_completed_is_reported(tmp_path):
    async def factory(*command, **options):
        return FakeProcess([], stderr=b"authentication failed", returncode=1)

    provider = CodexCLIProvider(tmp_path, process_factory=factory)
    events = collect(provider)

    assert [event.type for event in events] == ["error", "turn_end"]
    assert "authentication failed" in events[0].content
    assert events[1].metadata["ok"] is False


def test_turn_failed_is_terminal_and_not_duplicated(tmp_path):
    async def factory(*command, **options):
        return FakeProcess(
            [
                b'{"type":"turn.failed","error":{"message":"model unavailable"}}\n',
            ],
            returncode=1,
        )

    provider = CodexCLIProvider(tmp_path, process_factory=factory)
    events = collect(provider)

    assert [event.type for event in events] == ["error", "turn_end"]
    assert events[0].content == "model unavailable"
    assert events[1].metadata["stop_reason"] == "turn_failed"


def test_interrupt_terminates_running_process(tmp_path):
    provider = CodexCLIProvider(tmp_path)
    process = FakeProcess([])
    provider._proc = process

    interrupted = asyncio.run(provider.interrupt())

    assert interrupted is True
    assert process.terminated is True


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
