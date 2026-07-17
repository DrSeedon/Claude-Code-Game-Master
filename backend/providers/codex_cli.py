"""Codex CLI provider using resumable JSONL sessions."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from backend.runtime.events import AgentEvent, ContextUsage

logger = logging.getLogger(__name__)

CODEX_CONTEXT_LIMITS = {
    "gpt-5.6": 258_400,
    "gpt-5.6-terra": 258_400,
    "gpt-5.3-codex-spark": 258_400,
}
CODEX_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_SAFE_SANDBOXES = {"read-only", "workspace-write"}
_CONFIG_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ProcessFactory = Callable[..., Awaitable[Any]]


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _toml_string(value: str) -> str:
    """Return a TOML-compatible JSON string literal."""

    return json.dumps(value, ensure_ascii=False)


def _read_rollout_context(path: Path) -> ContextUsage | None:
    latest: ContextUsage | None = None
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                payload = row.get("payload") or {}
                if row.get("type") != "event_msg" or payload.get("type") != "token_count":
                    continue
                info = payload.get("info") or {}
                usage = info.get("last_token_usage") or {}
                used = usage.get("input_tokens")
                total = info.get("model_context_window")
                cached = usage.get("cached_input_tokens", 0)
                if not isinstance(used, int) or used < 0:
                    continue
                if not isinstance(total, int) or total <= 0:
                    continue
                latest = ContextUsage(
                    used_tokens=used,
                    total_tokens=total,
                    cached_input_tokens=cached if isinstance(cached, int) else 0,
                )
    except (FileNotFoundError, OSError):
        return None
    return latest


def _tool_name(item: Mapping[str, Any]) -> tuple[str, str]:
    item_type = str(item.get("type") or "")
    if item_type == "command_execution":
        return "Bash", "Bash"
    if item_type == "mcp_tool_call":
        server = str(item.get("server") or "")
        short_name = str(item.get("tool") or "MCP")
        return (f"{server}__{short_name}" if server else short_name), short_name
    if item_type == "web_search":
        return "WebSearch", "WebSearch"
    return item_type or "tool", item_type or "tool"


def normalize_codex_event(payload: Mapping[str, Any]) -> list[AgentEvent]:
    """Map one Codex JSONL object to provider-neutral events."""

    event_type = str(payload.get("type") or "")
    if event_type == "thread.started":
        thread_id = str(payload.get("thread_id") or "")
        if not thread_id:
            return []
        return [
            AgentEvent(
                "status",
                "Codex session started",
                {"session_id": thread_id},
            )
        ]

    if event_type in {"item.updated", "item.delta"}:
        item = payload.get("item") or {}
        delta = payload.get("delta") or item.get("delta") or {}
        text = delta.get("text", "") if isinstance(delta, Mapping) else str(delta)
        if item.get("type") == "agent_message" and text:
            return [AgentEvent("text_delta", str(text))]
        return []

    if event_type == "item.started":
        item = payload.get("item") or {}
        item_type = item.get("type")
        if item_type not in {"command_execution", "mcp_tool_call", "web_search"}:
            return []
        full_name, short_name = _tool_name(item)
        if item_type == "command_execution":
            summary = str(item.get("command") or "")
        elif item_type == "mcp_tool_call":
            summary = json.dumps(item.get("arguments") or {}, ensure_ascii=False)[:500]
        else:
            summary = str(item.get("query") or "")
        return [
            AgentEvent(
                "tool_use",
                f"{full_name}: {summary}",
                {"tool_name": full_name, "short_name": short_name},
            )
        ]

    if event_type == "item.completed":
        item = payload.get("item") or {}
        item_type = item.get("type")
        if item_type == "agent_message":
            text = str(item.get("text") or "")
            return [AgentEvent("text", text)] if text else []
        if item_type == "reasoning":
            text = str(item.get("text") or item.get("summary") or "")
            return [AgentEvent("thinking", text)] if text else []
        if item_type == "command_execution":
            return [
                AgentEvent(
                    "tool_result",
                    str(item.get("aggregated_output") or ""),
                    {"exit_code": item.get("exit_code")},
                )
            ]
        if item_type == "file_change":
            changes = item.get("changes") or []
            content = ", ".join(
                f"{change.get('kind', '')} {change.get('path', '')}".strip()
                for change in changes
                if isinstance(change, Mapping)
            )
            return [AgentEvent("file_change", content)] if content else []
        if item_type == "mcp_tool_call":
            events: list[AgentEvent] = []
            result = item.get("result")
            if isinstance(result, Mapping):
                blocks = result.get("content") or []
                text = "\n".join(
                    str(block.get("text") or block)
                    for block in blocks
                    if isinstance(block, Mapping)
                )
                if not text:
                    text = str(result)
                events.append(AgentEvent("tool_result", text[:10_000]))
            error = item.get("error")
            if error:
                message = error.get("message", str(error)) if isinstance(error, Mapping) else str(error)
                events.append(AgentEvent("error", message))
            return events
        if item_type == "web_search":
            result = str(item.get("result") or item.get("query") or "")
            return [AgentEvent("tool_result", result)] if result else []
        if item_type == "error":
            return [AgentEvent("error", str(item.get("message") or "Codex item failed"))]
        return []

    if event_type == "turn.completed":
        usage = payload.get("usage") or {}
        metadata = {
            "ok": True,
            "stop_reason": "end_turn",
            "input_tokens": _nonnegative_int(usage.get("input_tokens")),
            "cached_input_tokens": _nonnegative_int(usage.get("cached_input_tokens")),
            "output_tokens": _nonnegative_int(usage.get("output_tokens")),
        }
        return [AgentEvent("turn_end", "Turn completed", metadata)]

    if event_type == "turn.failed":
        error = payload.get("error") or {}
        message = error.get("message", "Codex turn failed") if isinstance(error, Mapping) else str(error)
        return [
            AgentEvent("error", str(message)),
            AgentEvent(
                "turn_end",
                "Turn failed",
                {"ok": False, "stop_reason": "turn_failed"},
            ),
        ]

    if event_type == "error":
        return [AgentEvent("error", str(payload.get("message") or "Codex error"))]
    return []


class CodexCLIProvider:
    """Per-turn Codex process with a resumable conversation thread."""

    def __init__(
        self,
        project_root: Path,
        model_name: str = "gpt-5.6",
        campaign_name: str | None = None,
        *,
        resume_thread_id: str | None = None,
        reasoning_effort: str = "high",
        sandbox: str = "workspace-write",
        environment: Mapping[str, str] | None = None,
        codex_bin: str | None = None,
        process_factory: ProcessFactory | None = None,
        rollout_root: Path | None = None,
    ) -> None:
        root = project_root.resolve()
        if not root.is_dir():
            raise ValueError(f"project root does not exist: {root}")
        if sandbox not in _SAFE_SANDBOXES:
            raise ValueError("Codex provider only permits read-only or workspace-write sandbox")
        self.project_root = root
        self.model_name = model_name
        self.campaign_name = campaign_name
        self.reasoning_effort = (
            reasoning_effort if reasoning_effort in CODEX_REASONING_EFFORTS else "high"
        )
        self.sandbox = sandbox
        self._thread_id = resume_thread_id
        self._environment = dict(environment or {})
        self._codex_bin = codex_bin or shutil.which("codex") or "codex"
        self._process_factory = process_factory or asyncio.create_subprocess_exec
        self._rollout_root = rollout_root
        self._rollout_path: Path | None = None
        self._proc: Any | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._last_stderr = ""
        self._turn_completed = False
        self._turn_lock = asyncio.Lock()

    @property
    def session_id(self) -> str | None:
        return self._thread_id

    @property
    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    def _mcp_config_args(self, servers: Mapping[str, Any] | None) -> list[str]:
        args: list[str] = []
        for name, raw_config in (servers or {}).items():
            if not _CONFIG_NAME.fullmatch(name) or not isinstance(raw_config, Mapping):
                continue
            command = raw_config.get("command")
            url = raw_config.get("url")
            if command:
                args.append(f"mcp_servers.{name}.command={_toml_string(str(command))}")
                server_args = raw_config.get("args") or []
                if not isinstance(server_args, (list, tuple)):
                    server_args = []
                args.append(
                    f"mcp_servers.{name}.args=["
                    + ", ".join(_toml_string(str(value)) for value in server_args)
                    + "]"
                )
                env = raw_config.get("env") or {}
                if isinstance(env, Mapping):
                    values = ", ".join(
                        f"{key}={_toml_string(str(value))}"
                        for key, value in env.items()
                        if _ENV_NAME.fullmatch(str(key))
                    )
                    if values:
                        args.append(f"mcp_servers.{name}.env={{{values}}}")
            elif url:
                args.append(f"mcp_servers.{name}.url={_toml_string(str(url))}")
                token_env = raw_config.get("bearer_token_env_var")
                if token_env and _ENV_NAME.fullmatch(str(token_env)):
                    args.append(
                        f"mcp_servers.{name}.bearer_token_env_var="
                        f"{_toml_string(str(token_env))}"
                    )
        return args

    def _build_command(
        self,
        message: str,
        system_prompt: str,
        model_name: str,
        mcp_servers: Mapping[str, Any] | None,
    ) -> list[str]:
        if self._thread_id:
            command = [
                self._codex_bin,
                "exec",
                "resume",
                "--json",
                "--color",
                "never",
                "-m",
                model_name,
                "-c",
                f"sandbox_mode={_toml_string(self.sandbox)}",
            ]
        else:
            command = [
                self._codex_bin,
                "exec",
                "--json",
                "--color",
                "never",
                "-m",
                model_name,
                "-s",
                self.sandbox,
                "-C",
                str(self.project_root),
            ]
            if system_prompt:
                command.extend(
                    ["-c", f"developer_instructions={_toml_string(system_prompt)}"]
                )
        command.extend(
            ["-c", f"model_reasoning_effort={_toml_string(self.reasoning_effort)}"]
        )
        for config in self._mcp_config_args(mcp_servers):
            command.extend(["-c", config])
        if self._thread_id:
            command.append(self._thread_id)
        command.append(message)
        return command

    def _build_env(self, mcp_servers: Mapping[str, Any] | None) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self._environment)
        if self.campaign_name:
            env["DM_ACTIVE_CAMPAIGN"] = self.campaign_name
        for config in (mcp_servers or {}).values():
            if not isinstance(config, Mapping):
                continue
            server_env = config.get("env") or {}
            if not isinstance(server_env, Mapping):
                continue
            for key, value in server_env.items():
                if _ENV_NAME.fullmatch(str(key)):
                    env[str(key)] = str(value)
        return env

    async def process_message(
        self,
        user_message: str,
        system_prompt: str,
        model_name: str,
        mcp_servers: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        if not user_message.strip():
            yield AgentEvent("error", "Player message must not be empty")
            return

        async with self._turn_lock:
            if model_name != self.model_name:
                await self.reset()
                self.model_name = model_name
            command = self._build_command(
                user_message,
                system_prompt,
                model_name,
                mcp_servers,
            )
            self._turn_completed = False
            self._last_stderr = ""
            try:
                self._proc = await self._process_factory(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=self._build_env(mcp_servers),
                    cwd=str(self.project_root),
                    limit=16 * 1024 * 1024,
                )
            except (OSError, RuntimeError) as exc:
                yield AgentEvent("error", f"Could not start Codex CLI: {exc}")
                return

            self._stderr_task = asyncio.create_task(self._drain_stderr())
            try:
                async for event in self._read_events():
                    yield event
                return_code = await self._proc.wait()
                if self._stderr_task:
                    try:
                        await asyncio.wait_for(self._stderr_task, timeout=5)
                    except asyncio.TimeoutError:
                        self._stderr_task.cancel()
                if not self._turn_completed:
                    detail = self._last_stderr or f"Codex exited with status {return_code}"
                    yield AgentEvent("error", detail)
                    yield AgentEvent(
                        "turn_end",
                        "Turn did not complete",
                        {
                            "ok": False,
                            "stop_reason": f"process_exit_{return_code}",
                            "returncode": return_code,
                            "session_id": self._thread_id,
                        },
                    )
            except asyncio.CancelledError:
                await self.interrupt()
                raise
            finally:
                self._proc = None
                self._stderr_task = None

    async def _read_events(self) -> AsyncIterator[AgentEvent]:
        if not self._proc or not self._proc.stdout:
            return
        while True:
            try:
                raw_line = await self._proc.stdout.readline()
            except ValueError:
                logger.warning("Codex emitted a JSONL line larger than the stream limit")
                continue
            if not raw_line:
                break
            try:
                payload = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if payload.get("type") == "thread.started":
                thread_id = payload.get("thread_id")
                if thread_id:
                    self._thread_id = str(thread_id)
                    self._rollout_path = None
            if payload.get("type") in {"turn.completed", "turn.failed"}:
                self._turn_completed = True
            for event in normalize_codex_event(payload):
                if event.type == "turn_end":
                    metadata = dict(event.metadata)
                    metadata["session_id"] = self._thread_id
                    event = AgentEvent(event.type, event.content, metadata)
                yield event

    async def _drain_stderr(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        chunks: list[bytes] = []
        while True:
            chunk = await self._proc.stderr.read(4096)
            if not chunk:
                break
            chunks.append(chunk)
        self._last_stderr = b"".join(chunks)[-2000:].decode("utf-8", errors="replace")

    async def interrupt(self) -> bool:
        process = self._proc
        if process is None or process.returncode is not None:
            return False
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        return True

    async def close(self) -> None:
        await self.interrupt()

    async def reset(self) -> None:
        await self.close()
        self._thread_id = None
        self._rollout_path = None

    def _find_rollout(self) -> Path | None:
        if not self._thread_id:
            return None
        if self._rollout_path and self._rollout_path.is_file():
            return self._rollout_path
        root = self._rollout_root
        if root is None:
            codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
            root = codex_home / "sessions"
        try:
            matches = list(root.glob(f"**/*{self._thread_id}.jsonl"))
        except OSError:
            return None
        if not matches:
            return None
        try:
            self._rollout_path = max(matches, key=lambda path: path.stat().st_mtime)
        except OSError:
            return None
        return self._rollout_path

    def get_context_usage(self) -> ContextUsage | None:
        rollout = self._find_rollout()
        return _read_rollout_context(rollout) if rollout else None

    def get_provider_name(self) -> str:
        return "Codex CLI (subscription)"
