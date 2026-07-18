"""Persistent Codex app-server provider for web game sessions."""

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
    "gpt-5.3-codex-spark": 128_000,
    "gpt-5.6-sol": 258_400,
    "gpt-5.6-terra": 258_400,
    "gpt-5.6-luna": 258_400,
}
CODEX_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_SAFE_SANDBOXES = {"read-only", "workspace-write"}
_MCP_APPROVAL_MODES = {"auto", "prompt", "writes", "approve"}
_CONFIG_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ProcessFactory = Callable[..., Awaitable[Any]]


class CodexProtocolError(RuntimeError):
    """JSON-RPC error returned by Codex app-server."""

    def __init__(self, method: str, error: Mapping[str, Any]):
        self.method = method
        self.error = dict(error)
        super().__init__(f"{method}: {error.get('message', 'Codex app-server error')}")


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _toml_string(value: str) -> str:
    """Return a TOML-compatible JSON string literal."""

    return json.dumps(value, ensure_ascii=False)


def _read_rollout_context(path: Path) -> ContextUsage | None:
    """Read the latest model-call context as a fallback for older app-server builds."""

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


def _result_text(result: Any) -> str:
    if isinstance(result, Mapping):
        content = result.get("content")
        if isinstance(content, list):
            return "\n".join(
                str(block.get("text", block)) if isinstance(block, Mapping) else str(block)
                for block in content
            )[:10_000]
        return json.dumps(result, ensure_ascii=False)[:10_000]
    if isinstance(result, list):
        return "\n".join(
            str(block.get("text", block)) if isinstance(block, Mapping) else str(block)
            for block in result
        )[:10_000]
    return str(result)[:10_000]


def _reasoning_text(item: Mapping[str, Any]) -> str:
    raw = item.get("summary") or item.get("content") or item.get("text") or ""
    if isinstance(raw, list):
        return "\n".join(
            str(part.get("text", part)) if isinstance(part, Mapping) else str(part)
            for part in raw
            if part
        )
    return str(raw)


def _tool_use(name: str, summary: str, item_id: str = "") -> AgentEvent:
    short_name = name.rsplit("__", 1)[-1]
    return AgentEvent(
        "tool_use",
        f"{name}: {summary}",
        {
            "tool_name": name,
            "short_name": short_name,
            "tool_use_id": item_id,
        },
    )


def normalize_codex_event(payload: Mapping[str, Any]) -> list[AgentEvent]:
    """Map one Codex app-server notification to provider-neutral events."""

    method = str(payload.get("method") or "")
    params = payload.get("params") or {}
    if not isinstance(params, Mapping):
        params = {}

    if method == "thread/started":
        thread = params.get("thread") or {}
        thread_id = str(
            (thread.get("id") if isinstance(thread, Mapping) else None)
            or params.get("threadId")
            or ""
        )
        return (
            [AgentEvent("status", "Codex session started", {"session_id": thread_id})]
            if thread_id
            else []
        )

    if method == "turn/started":
        turn = params.get("turn") or {}
        turn_id = str(turn.get("id") if isinstance(turn, Mapping) else "")
        return [AgentEvent("status", f"Codex turn {turn_id} started")]

    if method == "item/agentMessage/delta":
        text = str(params.get("delta") or "")
        return [AgentEvent("text_delta", text)] if text else []

    if method == "item/started":
        item = params.get("item") or {}
        if not isinstance(item, Mapping):
            return []
        item_type = item.get("type")
        item_id = str(item.get("id") or "")
        if item_type == "commandExecution":
            return [_tool_use("Bash", str(item.get("command") or ""), item_id)]
        if item_type == "mcpToolCall":
            server = str(item.get("server") or "")
            tool = str(item.get("tool") or "MCP")
            name = f"mcp__{server}__{tool}" if server else tool
            args = json.dumps(item.get("arguments") or {}, ensure_ascii=False)[:500]
            return [_tool_use(name, args, item_id)]
        if item_type == "webSearch":
            return [_tool_use("WebSearch", str(item.get("query") or ""), item_id)]
        if item_type == "contextCompaction":
            return [AgentEvent("activity", "Codex is compacting the conversation context")]
        return []

    if method == "item/completed":
        item = params.get("item") or {}
        if not isinstance(item, Mapping):
            return []
        item_type = item.get("type")
        item_id = str(item.get("id") or "")
        if item_type == "agentMessage":
            text = str(item.get("text") or "")
            return [AgentEvent("text", text)] if text else []
        if item_type in {"reasoning", "plan"}:
            text = _reasoning_text(item)
            return [AgentEvent("thinking", text)] if text else []
        if item_type == "commandExecution":
            return [
                AgentEvent(
                    "tool_result",
                    str(item.get("aggregatedOutput") or ""),
                    {"exit_code": item.get("exitCode"), "tool_use_id": item_id},
                )
            ]
        if item_type == "fileChange":
            changes = item.get("changes") or []
            content = ", ".join(
                f"{change.get('kind', '')} {change.get('path', '')}".strip()
                for change in changes
                if isinstance(change, Mapping)
            )
            return (
                [AgentEvent("file_change", content, {"tool_use_id": item_id})]
                if content
                else []
            )
        if item_type == "mcpToolCall":
            events: list[AgentEvent] = []
            if item.get("result") is not None:
                events.append(
                    AgentEvent(
                        "tool_result",
                        _result_text(item["result"]),
                        {"tool_use_id": item_id},
                    )
                )
            if item.get("error"):
                error = item["error"]
                message = (
                    error.get("message", str(error))
                    if isinstance(error, Mapping)
                    else str(error)
                )
                events.append(AgentEvent("error", str(message)))
            return events
        if item_type == "webSearch":
            return [
                AgentEvent(
                    "tool_result",
                    f"Web search completed: {item.get('query', '')}",
                    {"tool_use_id": item_id},
                )
            ]
        if item_type == "error":
            return [AgentEvent("error", str(item.get("message") or "Codex item failed"))]
        return []

    if method == "context/compacted":
        return [AgentEvent("activity", "Codex conversation context compacted")]
    if method == "item/mcpToolCall/progress":
        return [AgentEvent("activity", f"MCP: {params.get('message', '')}")]
    return []


class CodexCLIProvider:
    """Persistent Codex app-server process with one resumable thread."""

    def __init__(
        self,
        project_root: Path,
        model_name: str = "gpt-5.6-sol",
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
            "native"
            if model_name == "gpt-5.3-codex-spark"
            else reasoning_effort if reasoning_effort in CODEX_REASONING_EFFORTS else "high"
        )
        self.sandbox = sandbox
        self._thread_id = resume_thread_id
        self._environment = dict(environment or {})
        self._codex_bin = codex_bin or shutil.which("codex") or "codex"
        self._process_factory = process_factory or asyncio.create_subprocess_exec
        self._rollout_root = rollout_root
        self._rollout_path: Path | None = None
        self._proc: Any | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._notifications: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending_requests: dict[int, asyncio.Future[Any]] = {}
        self._request_seq = 0
        self._write_lock = asyncio.Lock()
        self._turn_lock = asyncio.Lock()
        self._active_turn_id: str | None = None
        self._disconnecting = False
        self._last_stderr = ""
        self._last_call_usage: dict[str, int] | None = None
        self._context_window = CODEX_CONTEXT_LIMITS.get(model_name, 258_400)

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
            enabled_tools = raw_config.get("enabled_tools")
            if isinstance(enabled_tools, (list, tuple)):
                safe_tools = [
                    str(tool)
                    for tool in enabled_tools
                    if _TOOL_NAME.fullmatch(str(tool))
                ]
                args.append(
                    f"mcp_servers.{name}.enabled_tools=["
                    + ", ".join(_toml_string(tool) for tool in safe_tools)
                    + "]"
                )
            approval_mode = raw_config.get("default_tools_approval_mode")
            if approval_mode in _MCP_APPROVAL_MODES:
                args.append(
                    f"mcp_servers.{name}.default_tools_approval_mode="
                    f"{_toml_string(str(approval_mode))}"
                )
            for option in ("enabled", "required"):
                if isinstance(raw_config.get(option), bool):
                    args.append(
                        f"mcp_servers.{name}.{option}="
                        f"{str(raw_config[option]).lower()}"
                    )
        return args

    def _build_command(self, mcp_servers: Mapping[str, Any] | None) -> list[str]:
        command = [self._codex_bin]
        if self.reasoning_effort != "native":
            command.extend(
                ["-c", f"model_reasoning_effort={_toml_string(self.reasoning_effort)}"]
            )
        for config in self._mcp_config_args(mcp_servers):
            command.extend(["-c", config])
        command.extend(["app-server", "--stdio"])
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

    async def _connect(
        self,
        system_prompt: str,
        mcp_servers: Mapping[str, Any] | None,
    ) -> None:
        if self.is_alive:
            return
        if self._proc is not None:
            await self.close()

        self._notifications = asyncio.Queue()
        self._disconnecting = False
        self._last_stderr = ""
        self._proc = await self._process_factory(
            *self._build_command(mcp_servers),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._build_env(mcp_servers),
            cwd=str(self.project_root),
            limit=16 * 1024 * 1024,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            await asyncio.wait_for(
                self._request(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "dm-game-master",
                            "title": "DM Game Master",
                            "version": "1",
                        }
                    },
                ),
                timeout=30,
            )
            await self._notify("initialized", {})
            params: dict[str, Any] = {
                "cwd": str(self.project_root),
                "model": self.model_name,
                "approvalPolicy": "never",
                "sandbox": self.sandbox,
            }
            if system_prompt:
                params["developerInstructions"] = system_prompt
            if self._thread_id:
                params["threadId"] = self._thread_id
                method = "thread/resume"
            else:
                method = "thread/start"
            result = await asyncio.wait_for(self._request(method, params), timeout=30)
            thread = result.get("thread") or {}
            thread_id = thread.get("id") if isinstance(thread, Mapping) else None
            if not thread_id:
                raise RuntimeError("Codex app-server returned no thread id")
            self._thread_id = str(thread_id)
            self._rollout_path = None
        except BaseException:
            await self.close()
            raise

    async def _start_turn(self, user_message: str) -> None:
        if not self._thread_id:
            raise RuntimeError("Codex thread is not initialized")
        params: dict[str, Any] = {
            "threadId": self._thread_id,
            "input": [{"type": "text", "text": user_message}],
            "model": self.model_name,
        }
        if self.reasoning_effort != "native":
            params["effort"] = self.reasoning_effort
        result = await asyncio.wait_for(self._request("turn/start", params), timeout=30)
        turn = result.get("turn") or {}
        turn_id = turn.get("id") if isinstance(turn, Mapping) else None
        if not turn_id:
            raise RuntimeError("Codex app-server returned no turn id")
        self._active_turn_id = str(turn_id)

    async def process_message(
        self,
        user_message: str,
        system_prompt: str,
        model_name: str,
        mcp_servers: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        if not user_message.strip():
            yield AgentEvent("error", "Player message must not be empty")
            yield AgentEvent("turn_end", "Turn failed", {"ok": False})
            return

        async with self._turn_lock:
            if model_name != self.model_name:
                await self.reset()
                self.model_name = model_name
                self._context_window = CODEX_CONTEXT_LIMITS.get(model_name, 258_400)
            self._last_call_usage = None
            try:
                await self._connect(system_prompt, mcp_servers)
                await self._start_turn(user_message)
            except (OSError, RuntimeError, asyncio.TimeoutError) as exc:
                await self.close()
                yield AgentEvent("error", f"Could not start Codex app-server turn: {exc}")
                yield AgentEvent(
                    "turn_end",
                    "Turn failed",
                    {
                        "ok": False,
                        "stop_reason": "startup_error",
                        "session_id": self._thread_id,
                    },
                )
                return

            try:
                async for event in self._events():
                    yield event
            except asyncio.CancelledError:
                await self.interrupt()
                raise

    async def _events(self) -> AsyncIterator[AgentEvent]:
        while True:
            message = await self._notifications.get()
            method = str(message.get("method") or "")
            params = message.get("params") or {}
            if not isinstance(params, Mapping):
                params = {}
            thread_id = params.get("threadId")
            if thread_id and self._thread_id and str(thread_id) != self._thread_id:
                continue

            if method == "thread/tokenUsage/updated":
                usage = params.get("tokenUsage") or {}
                if isinstance(usage, Mapping):
                    last = usage.get("last") or {}
                    if isinstance(last, Mapping):
                        self._last_call_usage = {
                            "input_tokens": _nonnegative_int(last.get("inputTokens")),
                            "cached_input_tokens": _nonnegative_int(
                                last.get("cachedInputTokens")
                            ),
                            "output_tokens": _nonnegative_int(last.get("outputTokens")),
                        }
                    window = usage.get("modelContextWindow")
                    if isinstance(window, int) and window > 0:
                        self._context_window = window
                continue

            if method == "error":
                error = params.get("error") or {}
                if not isinstance(error, Mapping):
                    error = {"message": str(error)}
                content = str(error.get("message") or "Codex error")
                if params.get("willRetry"):
                    yield AgentEvent("activity", f"Codex reconnecting: {content}")
                    continue
                model_error = self._classify_error(error)
                event_type = "rate_limit" if model_error == "rate_limit" else "error"
                yield AgentEvent(event_type, content, {"model_error": model_error})
                continue

            if method == "turn/completed":
                turn = params.get("turn") or {}
                if not isinstance(turn, Mapping):
                    turn = {}
                status = str(turn.get("status") or "failed")
                error = turn.get("error") or {}
                if status == "failed" and isinstance(error, Mapping) and error.get("message"):
                    yield AgentEvent("error", str(error["message"]))
                self._active_turn_id = None
                usage = self._last_call_usage or {}
                yield AgentEvent(
                    "turn_end",
                    f"Turn {status}",
                    {
                        "ok": status == "completed",
                        "stop_reason": {
                            "completed": "end_turn",
                            "interrupted": "interrupted",
                            "failed": "turn_failed",
                        }.get(status, status),
                        "session_id": self._thread_id,
                        **usage,
                    },
                )
                return

            if method == "_process/exited":
                self._active_turn_id = None
                returncode = params.get("returncode")
                detail = str(params.get("stderr") or "").strip()
                yield AgentEvent(
                    "error",
                    detail or f"Codex app-server exited with status {returncode}",
                )
                yield AgentEvent(
                    "turn_end",
                    "Turn failed",
                    {
                        "ok": False,
                        "stop_reason": f"process_exit_{returncode}",
                        "returncode": returncode,
                        "session_id": self._thread_id,
                    },
                )
                return

            for event in normalize_codex_event(message):
                yield event

    async def _request(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        if not self.is_alive or not self._proc.stdin:
            raise RuntimeError("Codex app-server is not running")
        self._request_seq += 1
        request_id = self._request_seq
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future
        try:
            await self._write({"method": method, "id": request_id, "params": dict(params)})
            result = await future
            return dict(result) if isinstance(result, Mapping) else {}
        except CodexProtocolError as exc:
            raise CodexProtocolError(method, exc.error) from exc
        finally:
            self._pending_requests.pop(request_id, None)

    async def _notify(self, method: str, params: Mapping[str, Any]) -> None:
        await self._write({"method": method, "params": dict(params)})

    async def _write(self, payload: Mapping[str, Any]) -> None:
        if not self.is_alive or not self._proc.stdin:
            raise RuntimeError("Codex app-server stdin is unavailable")
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
        async with self._write_lock:
            self._proc.stdin.write(encoded)
            await self._proc.stdin.drain()

    async def _read_stdout(self) -> None:
        process = self._proc
        if not process or not process.stdout:
            return
        try:
            while True:
                raw = await process.stdout.readline()
                if not raw:
                    break
                try:
                    message = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    logger.warning("Codex app-server emitted invalid JSONL")
                    continue
                request_id = message.get("id")
                if request_id is not None and message.get("method"):
                    await self._write(
                        {
                            "id": request_id,
                            "error": {
                                "code": -32601,
                                "message": (
                                    "DM Game Master does not implement client request "
                                    f"{message.get('method')}"
                                ),
                            },
                        }
                    )
                    continue
                if request_id is not None:
                    future = self._pending_requests.get(request_id)
                    if future and not future.done():
                        if "error" in message:
                            future.set_exception(
                                CodexProtocolError(
                                    "request",
                                    message.get("error") or {},
                                )
                            )
                        else:
                            future.set_result(message.get("result") or {})
                    continue
                if message.get("method"):
                    await self._notifications.put(message)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.exception("Codex app-server reader failed: %s", exc)
        finally:
            returncode = await process.wait()
            failure = RuntimeError(f"Codex app-server exited with status {returncode}")
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(failure)
            if not self._disconnecting:
                await self._notifications.put(
                    {
                        "method": "_process/exited",
                        "params": {
                            "returncode": returncode,
                            "stderr": self._last_stderr,
                        },
                    }
                )

    async def _drain_stderr(self) -> None:
        process = self._proc
        if not process or not process.stderr:
            return
        try:
            while True:
                chunk = await process.stderr.read(4096)
                if not chunk:
                    break
                self._last_stderr = (
                    self._last_stderr + chunk.decode("utf-8", errors="replace")
                )[-4000:]
        except asyncio.CancelledError:
            return

    async def interrupt(self) -> bool:
        if not self._active_turn_id or not self._thread_id or not self.is_alive:
            return False
        try:
            await asyncio.wait_for(
                self._request(
                    "turn/interrupt",
                    {
                        "threadId": self._thread_id,
                        "turnId": self._active_turn_id,
                    },
                ),
                timeout=5,
            )
            return True
        except (RuntimeError, asyncio.TimeoutError):
            return False

    async def close(self) -> None:
        process = self._proc
        if process is None:
            return
        self._disconnecting = True
        if self._active_turn_id and process.returncode is None:
            await self.interrupt()
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                task.cancel()
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(RuntimeError("Codex app-server disconnected"))
        self._pending_requests.clear()
        self._proc = None
        self._reader_task = None
        self._stderr_task = None
        self._active_turn_id = None

    async def reset(self) -> None:
        await self.close()
        self._thread_id = None
        self._rollout_path = None
        self._last_call_usage = None

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
        if self._last_call_usage:
            return ContextUsage(
                used_tokens=self._last_call_usage["input_tokens"],
                total_tokens=self._context_window,
                cached_input_tokens=self._last_call_usage["cached_input_tokens"],
            )
        rollout = self._find_rollout()
        return _read_rollout_context(rollout) if rollout else None

    @staticmethod
    def _classify_error(error: Mapping[str, Any]) -> str:
        info = error.get("codexErrorInfo")
        if info in {"usageLimitExceeded", "sessionBudgetExceeded"}:
            return "rate_limit"
        if info == "contextWindowExceeded":
            return "context_window"
        if info in {"serverOverloaded", "internalServerError"}:
            return "server_error"
        if isinstance(info, Mapping) and any(
            key in info
            for key in (
                "httpConnectionFailed",
                "responseStreamConnectionFailed",
                "responseStreamDisconnected",
                "responseTooManyFailedAttempts",
            )
        ):
            return "server_error"
        message = str(error.get("message") or "").lower()
        if any(
            part in message
            for part in (
                "rate limit",
                "usage limit",
                "session limit",
                "too many requests",
                "429",
            )
        ):
            return "rate_limit"
        if any(
            part in message
            for part in (
                "connection refused",
                "stream disconnected",
                "network error",
                "tls",
                "unexpected eof",
            )
        ):
            return "server_error"
        return "error"

    def get_provider_name(self) -> str:
        return "Codex app-server (subscription)"


# Compatibility name for callers that want to state the transport explicitly.
CodexAppServerProvider = CodexCLIProvider
