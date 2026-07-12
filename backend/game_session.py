"""GameSession — turn lifecycle independent of any single WebSocket connection.

One campaign = one GameSession (module-level registry). A turn runs in a
background asyncio.Task; WebSocket handlers only subscribe/publish to the
session's broker channel. Disconnecting a WS does not stop the turn —
reconnecting resumes seeing live output.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

from backend.event_log import append_event
from backend.live_broker import broker
from backend.providers.claude_sdk import ClaudeSDKProvider

logger = logging.getLogger(__name__)

_sessions: Dict[str, "GameSession"] = {}


def get_or_create_session(campaign: str, project_root: Path, model_name: str) -> "GameSession":
    session = _sessions.get(campaign)
    if session is None:
        session = GameSession(campaign, project_root, model_name)
        _sessions[campaign] = session
    return session


class GameSession:
    """Owns the provider + turn task for one campaign."""

    def __init__(self, campaign: str, project_root: Path, model_name: str):
        self.campaign = campaign
        self.project_root = project_root
        self.model_name = model_name
        self.provider = ClaudeSDKProvider(project_root=project_root, model_name=model_name)
        self.campaign_dir = project_root / "world-state" / "campaigns" / campaign
        self.running = False
        self._turn_task: Optional[asyncio.Task] = None

    def send(self, user_message: str, system_prompt: str, mcp_servers: Optional[Dict] = None) -> bool:
        """Start a turn in the background. Does not block on WS connection.

        Returns False (and does nothing) if a turn is already running — the SDK
        client is not safe for concurrent queries. Caller should queue/reject.
        """
        if self.running:
            return False
        append_event(self.campaign_dir, "user_message", user_message)
        self.running = True
        self._turn_task = asyncio.create_task(self._run_turn(user_message, system_prompt, mcp_servers))
        self._turn_task.add_done_callback(self._on_turn_done)
        return True

    async def _run_turn(self, user_message: str, system_prompt: str, mcp_servers: Optional[Dict]) -> None:
        try:
            async for event in self.provider.process_message(
                user_message=user_message,
                system_prompt=system_prompt,
                model_name=self.model_name,
                mcp_servers=mcp_servers,
            ):
                if event["type"] == "text_delta":
                    broker.publish(self.campaign, {"type": "stream", "content": event["content"]})
                    continue
                if event["type"] == "text":
                    append_event(self.campaign_dir, "text", event["content"])
                elif event["type"] == "activity":
                    append_event(self.campaign_dir, "activity", event["content"])
                elif event["type"] == "error":
                    append_event(self.campaign_dir, "error", event["content"])
                broker.publish(self.campaign, event)
        except Exception as e:
            logger.error(f"[{self.campaign}] turn failed: {e}", exc_info=True)
            err_event = {"type": "error", "content": str(e)}
            append_event(self.campaign_dir, "error", str(e))
            broker.publish(self.campaign, err_event)
        finally:
            self.running = False
            done_event = {"type": "done"}
            broker.publish(self.campaign, done_event)

    def _on_turn_done(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"[{self.campaign}] turn task crashed: {exc}", exc_info=exc)
