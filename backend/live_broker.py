"""In-memory pub/sub for game session events — decouples WS connections from turns.

A turn runs in a background asyncio.Task independent of any WebSocket. Events are
published here; WS handlers subscribe/unsubscribe as players connect/disconnect.
Single process only (in-memory, no cross-worker fanout — matches uvicorn single-worker deploy).
"""

import asyncio
from collections import defaultdict

_MAXSIZE = 256  # per-subscriber backlog; drop-oldest beyond this


class LiveBroker:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, campaign: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_MAXSIZE)
        self._subs[campaign].add(q)
        return q

    def unsubscribe(self, campaign: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(campaign)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(campaign, None)

    def publish(self, campaign: str, payload: dict) -> None:
        for q in tuple(self._subs.get(campaign, ())):  # snapshot — safe if set mutates
            if q.full():
                try:
                    q.get_nowait()  # drop oldest — partials are ephemeral
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


broker = LiveBroker()
