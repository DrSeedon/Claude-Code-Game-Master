"""GameSession — turn lifecycle independent of any single WebSocket connection.

One campaign = one GameSession (module-level registry). A turn runs in a
background asyncio.Task; WebSocket handlers only subscribe/publish to the
session's broker channel. Disconnecting a WS does not stop the turn —
reconnecting resumes seeing live output.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Optional

from backend.event_log import append_event
from backend.live_broker import broker
from backend.providers.claude_sdk import ClaudeSDKProvider

logger = logging.getLogger(__name__)

_sessions: Dict[str, "GameSession"] = {}

HIBERNATE_IDLE_SECONDS = 5 * 60


def get_or_create_session(campaign: str, project_root: Path, model_name: str) -> "GameSession":
    """Exactly one GameSession per campaign, ever — so all sockets for a campaign
    share one provider and turn lock (no concurrent turns, no orphaned sessions).

    A header model switch is applied in place via `set_model()`, which takes effect
    on the next turn. We never recreate the session, so open sockets can't diverge.
    """
    session = _sessions.get(campaign)
    if session is None:
        session = GameSession(campaign, project_root, model_name)
        _sessions[campaign] = session
    else:
        session.set_model(model_name)
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
        self._last_turn_end_at: float = 0.0
        self._model_dirty = False  # model changed since last turn → reset CLI session on next send

    def set_model(self, model_name: str) -> None:
        """Switch model for future turns. No effect on a running turn (its model
        is already captured). The CLI conversation resets on the next send so the
        new model starts clean — the on-disk event log (what the player sees) is kept."""
        if model_name == self.model_name:
            return
        self.model_name = model_name
        self._model_dirty = True

    def send(self, user_message: str, system_prompt: str, mcp_servers: Optional[Dict] = None) -> bool:
        """Start a turn in the background. Does not block on WS connection.

        Returns False (and does nothing) if a turn is already running — the SDK
        client is not safe for concurrent queries. Caller should queue/reject.
        """
        if self.running:
            return False
        idle_for = time.monotonic() - self._last_turn_end_at if self._last_turn_end_at else 0.0
        append_event(self.campaign_dir, "user_message", user_message)
        self.running = True
        self._turn_task = asyncio.create_task(self._run_turn(user_message, system_prompt, mcp_servers, idle_for))
        self._turn_task.add_done_callback(self._on_turn_done)
        return True

    async def _run_turn(self, user_message: str, system_prompt: str, mcp_servers: Optional[Dict], idle_for: float) -> None:
        try:
            if self._model_dirty:
                # Model changed — drop the old CLI session so the new model starts a
                # fresh conversation (resume would keep the old model's session).
                await self.provider.close()
                self._model_dirty = False
                logger.info(f"[{self.campaign}] model switched to {self.model_name}")
            elif idle_for > HIBERNATE_IDLE_SECONDS:
                # Idle too long — drop the CLI subprocess. process_message() reconnects
                # and resumes via the provider's cached session_id, so history survives.
                await self.provider.close()
                logger.info(f"[{self.campaign}] hibernated after {idle_for:.0f}s idle")
            async for event in self.provider.process_message(
                user_message=user_message,
                system_prompt=system_prompt,
                model_name=self.model_name,
                mcp_servers=mcp_servers,
            ):
                if event["type"] == "text_delta":
                    broker.publish(self.campaign, {"type": "stream", "content": event["content"]})
                    continue
                if event["type"] in ("text", "activity", "error"):
                    stored = append_event(self.campaign_dir, event["type"], event["content"])
                    broker.publish(self.campaign, stored)
                else:
                    broker.publish(self.campaign, event)
        except Exception as e:
            logger.error(f"[{self.campaign}] turn failed: {e}", exc_info=True)
            stored = append_event(self.campaign_dir, "error", str(e))
            broker.publish(self.campaign, stored)
        finally:
            self.running = False
            self._last_turn_end_at = time.monotonic()
            usage = self.provider.get_context_usage()
            if usage:
                broker.publish(self.campaign, {
                    "type": "usage",
                    "percent": usage["percent"],
                    "used": usage["used_tokens"],
                    "total": usage["total_tokens"],
                })
            broker.publish(self.campaign, {"type": "done"})

    def _on_turn_done(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"[{self.campaign}] turn task crashed: {exc}", exc_info=exc)
