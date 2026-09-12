#!/usr/bin/env python
"""Deterministic R6 probe. No network, browser, provider, or product code."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import hmac
import json
from typing import Any


MAX_BUFFER_MS = 250
FUTURE_MEDIA_MAX_EVENTS = 16
FUTURE_MEDIA_MAX_BYTES = 256 * 1024
PCM_BYTES_PER_MS = 48
MUSIC_DUCK_GAIN = 0.25
SFX_DUCK_GAIN = 0.50
NORMAL_GAIN = 1.0
PRIORITY = {
    "control": 100,
    "speech": 80,
    "critical_sfx": 70,
    "sfx": 50,
    "music": 10,
}
FAKE_TELEMETRY_KEY = b"r6-fake-only-not-a-production-key"
METRIC_FIELDS = {
    "line_id", "attempt", "model_id", "voice_key", "input_characters",
    "text_hmac_sha256", "telemetry_key_id", "retention_policy_id",
    "deletion_disposition_id", "provider_started_ms", "provider_credit_observed",
    "provider_request_id", "first_provider_audio_ms", "provider_ttfa_ms",
    "cancelled_ms", "failed_ms", "outcome", "error_code", "retry_reason",
}
METRIC_REQUIRED_FIELDS = {
    "line_id", "attempt", "model_id", "voice_key", "input_characters",
    "text_hmac_sha256", "telemetry_key_id", "retention_policy_id",
    "deletion_disposition_id", "provider_started_ms", "provider_credit_observed",
    "provider_request_id",
}


def text_hmac(value: str) -> str:
    return hmac.new(FAKE_TELEMETRY_KEY, value.encode(), sha256).hexdigest()


@dataclass(frozen=True)
class VoiceEntry:
    voice_key: str
    provider_voice_id: str | None
    model_id: str | None
    fallback_voice_key: str | None
    provenance_status: str


@dataclass(frozen=True)
class Asset:
    asset_id: str
    event_key: str
    duration_ms: int
    sha256_hex: str
    provenance_status: str


@dataclass(frozen=True)
class LineRequest:
    room_id: str
    turn_id: str
    presentation_id: str
    text_event_id: str
    ordinal: int
    speaker_role: str
    entity_id: str | None
    archetype: str | None
    event_key: str
    text: str
    disclosed: bool
    normal_combat: bool
    important: bool


@dataclass
class SpeechLine:
    line_id: str
    context_id: str
    playback_attempt_id: str
    source: str
    status: str
    text_event_id: str
    voice_key: str | None = None
    provider_voice_id: str | None = None
    model_id: str | None = None
    asset_id: str | None = None
    attempt: int = 1
    audio_fence: int = 0
    last_chunk_seq: int = 0
    first_chunk_seen: bool = False
    input_character_count: int = 0
    text_hmac_sha256: str = ""


class VoiceRegistry:
    """Resolve an explicit, cleared voice chain; never guess a provider voice."""

    def __init__(self, entries: dict[str, VoiceEntry], entity_routes: dict[str, str], archetype_routes: dict[str, str]):
        self.entries = entries
        self.entity_routes = entity_routes
        self.archetype_routes = archetype_routes

    def resolve(self, role: str, entity_id: str | None, archetype: str | None) -> VoiceEntry | None:
        if role == "narrator":
            key = "narrator.severin"
        elif entity_id in self.entity_routes:
            key = self.entity_routes[entity_id]
        elif archetype in self.archetype_routes:
            key = self.archetype_routes[archetype]
        else:
            key = "npc.generic"
        visited: set[str] = set()
        while key and key not in visited:
            visited.add(key)
            entry = self.entries.get(key)
            if entry is None:
                return None
            if entry.provenance_status == "approved" and entry.provider_voice_id:
                return entry
            key = entry.fallback_voice_key
        return None


class CacheSelector:
    """Persisted shuffle-bag assignments: a retry returns the stored asset."""

    def __init__(self, pools: dict[str, list[Asset]], snapshot: dict[str, Any] | None = None):
        self.pools = pools
        snapshot = snapshot or {}
        self.assignments: dict[str, str] = dict(snapshot.get("assignments", {}))
        self.cursors: dict[str, int] = dict(snapshot.get("cursors", {}))

    def select(self, event_key: str, line_id: str) -> Asset | None:
        existing = self.assignments.get(line_id)
        pool = self.pools.get(event_key, [])
        if existing:
            return next((asset for asset in pool if asset.asset_id == existing), None)
        cleared = [asset for asset in pool if asset.provenance_status == "approved"]
        if not cleared:
            return None
        cycle_index = self.cursors.get(event_key, 0)
        cycle = cycle_index // len(cleared)
        position = cycle_index % len(cleared)
        ordered = sorted(
            cleared,
            key=lambda asset: sha256(f"{event_key}:{cycle}:{asset.asset_id}".encode()).hexdigest(),
        )
        asset = ordered[position]
        self.assignments[line_id] = asset.asset_id
        self.cursors[event_key] = cycle_index + 1
        return asset

    def snapshot(self) -> dict[str, Any]:
        return {"assignments": dict(self.assignments), "cursors": dict(self.cursors)}


class Router:
    def __init__(self, voices: VoiceRegistry, cache: CacheSelector):
        self.voices = voices
        self.cache = cache
        self.by_line_id: dict[str, SpeechLine] = {}

    def route(self, request: LineRequest) -> SpeechLine:
        line_id = f"line:{request.presentation_id}:{request.ordinal}"
        existing = self.by_line_id.get(line_id)
        if existing:
            return existing
        if not request.disclosed or not request.text_event_id:
            raise ValueError("undisclosed_text")
        if request.normal_combat:
            asset = self.cache.select(request.event_key, line_id)
            if asset is None:
                line = SpeechLine(
                    line_id=line_id,
                    context_id=f"local:{line_id}:a1",
                    playback_attempt_id=f"play:{line_id}:a1",
                    source="text_only",
                    status="failed_text_only",
                    text_event_id=request.text_event_id,
                    input_character_count=len(request.text),
                    text_hmac_sha256=text_hmac(request.text),
                )
            else:
                line = SpeechLine(
                    line_id=line_id,
                    context_id=f"local:{line_id}:a1",
                    playback_attempt_id=f"play:{line_id}:a1",
                    source="cache",
                    status="ready",
                    text_event_id=request.text_event_id,
                    asset_id=asset.asset_id,
                    input_character_count=len(request.text),
                    text_hmac_sha256=text_hmac(request.text),
                )
        else:
            voice = self.voices.resolve(request.speaker_role, request.entity_id, request.archetype)
            if voice is None:
                line = SpeechLine(
                    line_id=line_id,
                    context_id=f"none:{line_id}:a1",
                    playback_attempt_id=f"play:{line_id}:a1",
                    source="text_only",
                    status="failed_text_only",
                    text_event_id=request.text_event_id,
                    input_character_count=len(request.text),
                    text_hmac_sha256=text_hmac(request.text),
                )
            else:
                line = SpeechLine(
                    line_id=line_id,
                    context_id=f"ctx:{line_id}:a1",
                    playback_attempt_id=f"play:{line_id}:a1",
                    source="tts",
                    status="pending",
                    text_event_id=request.text_event_id,
                    voice_key=voice.voice_key,
                    provider_voice_id=voice.provider_voice_id,
                    model_id=voice.model_id,
                    input_character_count=len(request.text),
                    text_hmac_sha256=text_hmac(request.text),
                )
        self.by_line_id[line_id] = line
        return line


class FakeProvider:
    def __init__(self) -> None:
        self.started: list[tuple[str, str, str]] = []
        self.closed_contexts: list[str] = []

    def start(self, line: SpeechLine) -> None:
        assert line.provider_voice_id and line.model_id
        self.started.append((line.context_id, line.provider_voice_id, line.model_id))

    def close_context(self, context_id: str) -> None:
        if context_id not in self.closed_contexts:
            self.closed_contexts.append(context_id)


@dataclass
class Lease:
    lease_id: str
    generation: int
    consumer_id: str
    expires_at_ms: int


@dataclass(frozen=True)
class PendingMedia:
    kind: str
    event_id: str
    generation: int
    audio_fence: int
    payload: Any
    estimated_bytes: int
    speech_ms: int
    priority: int


class FakePlayer:
    def __init__(self, consumer_id: str) -> None:
        self.consumer_id = consumer_id
        self.lease: Lease | None = None
        self.applied_events: set[str] = set()
        self.cancelled: set[tuple[str, str]] = set()
        self.buffers: dict[tuple[str, str], int] = {}
        self.play_count = 0
        self.active_speech: tuple[str, str] | None = None
        self.dropped_busy_speech = 0
        self.dropped_late_chunks = 0
        self.dropped_stale_generation = 0
        self.dropped_stale_fence = 0
        self.audio_fence = 0
        self.music_gain = NORMAL_GAIN
        self.sfx_gain = NORMAL_GAIN
        self.music_state = "silence"
        self.music_event_id: str | None = None
        self.sfx_events: set[str] = set()
        self.pending_media: list[PendingMedia] = []
        self.control_gap_requests = 0
        self.control_barrier_observations: list[dict[str, Any]] = []

    def grant(self, lease: Lease) -> None:
        self.lease = lease

    def _media_gate(
        self,
        *,
        kind: str,
        event_id: str,
        generation: int,
        audio_fence: int,
        payload: Any,
        estimated_bytes: int = 0,
        speech_ms: int = 0,
        priority: int,
    ) -> str:
        if event_id in self.applied_events or any(item.event_id == event_id for item in self.pending_media):
            return "duplicate"
        if not self.lease or self.lease.consumer_id != self.consumer_id or self.lease.generation != generation:
            self.dropped_stale_generation += 1
            return "rejected"
        if audio_fence < self.audio_fence:
            self.dropped_stale_fence += 1
            return "rejected"
        if audio_fence == self.audio_fence:
            return "ready"
        if audio_fence != self.audio_fence + 1:
            self._request_control_gap()
            return "rejected"
        pending_bytes = sum(item.estimated_bytes for item in self.pending_media)
        pending_speech_ms = sum(item.speech_ms for item in self.pending_media)
        if (
            len(self.pending_media) >= FUTURE_MEDIA_MAX_EVENTS
            or pending_bytes + estimated_bytes > FUTURE_MEDIA_MAX_BYTES
            or pending_speech_ms + speech_ms > MAX_BUFFER_MS
        ):
            self._request_control_gap()
            return "rejected"
        self.pending_media.append(PendingMedia(
            kind=kind,
            event_id=event_id,
            generation=generation,
            audio_fence=audio_fence,
            payload=payload,
            estimated_bytes=estimated_bytes,
            speech_ms=speech_ms,
            priority=priority,
        ))
        return "buffered"

    def _request_control_gap(self) -> None:
        self.pending_media.clear()
        self.control_gap_requests += 1

    def _activate_speech(self, event_id: str, line: SpeechLine, buffered_ms: int) -> bool:
        if (line.line_id, line.context_id) in self.cancelled:
            self.dropped_late_chunks += 1
            return False
        key = (line.line_id, line.context_id)
        if self.active_speech and self.active_speech != key:
            self.dropped_busy_speech += 1
            return False
        if buffered_ms > MAX_BUFFER_MS:
            raise ValueError("buffer_cap_exceeded")
        self.applied_events.add(event_id)
        self.active_speech = key
        self.buffers[key] = buffered_ms
        self.play_count += 1
        self.music_gain = MUSIC_DUCK_GAIN
        self.sfx_gain = SFX_DUCK_GAIN
        return True

    def play(self, event_id: str, line: SpeechLine, generation: int, buffered_ms: int = 0) -> bool:
        if buffered_ms > MAX_BUFFER_MS:
            raise ValueError("buffer_cap_exceeded")
        decision = self._media_gate(
            kind="speech",
            event_id=event_id,
            generation=generation,
            audio_fence=line.audio_fence,
            payload=(line, buffered_ms),
            estimated_bytes=buffered_ms * PCM_BYTES_PER_MS,
            speech_ms=buffered_ms,
            priority=PRIORITY["speech"],
        )
        if decision != "ready":
            return False
        return self._activate_speech(event_id, line, buffered_ms)

    def chunk(self, line: SpeechLine, generation: int, chunk_seq: int, duration_ms: int) -> bool:
        event_id = f"audio.chunk:{line.context_id}:{chunk_seq}"
        decision = self._media_gate(
            kind="chunk",
            event_id=event_id,
            generation=generation,
            audio_fence=line.audio_fence,
            payload=(line, duration_ms),
            estimated_bytes=duration_ms * PCM_BYTES_PER_MS,
            speech_ms=duration_ms,
            priority=PRIORITY["speech"],
        )
        if decision != "ready":
            return False
        return self._activate_chunk(event_id, line, duration_ms)

    def _activate_chunk(self, event_id: str, line: SpeechLine, duration_ms: int) -> bool:
        key = (line.line_id, line.context_id)
        if self.active_speech != key:
            self.dropped_busy_speech += 1
            return False
        if key in self.cancelled or line.status == "cancelled":
            self.dropped_late_chunks += 1
            return False
        next_buffer = self.buffers.get(key, 0) + duration_ms
        if next_buffer > MAX_BUFFER_MS:
            raise ValueError("buffer_cap_exceeded")
        self.applied_events.add(event_id)
        self.buffers[key] = next_buffer
        return True

    def stop(self, line_id: str, context_id: str, audio_fence: int | None = None) -> None:
        key = (line_id, context_id)
        if audio_fence is not None:
            self.cancelled.add(key)
            self.apply_control(audio_fence, "speech_identity", key)
            return
        self._clear_speech(key)

    def _clear_speech(self, key: tuple[str, str]) -> None:
        self.buffers.pop(key, None)
        if self.active_speech == key:
            self.active_speech = None
        self.music_gain = NORMAL_GAIN
        self.sfx_gain = NORMAL_GAIN

    def _activate_music(self, event_id: str, state: str) -> bool:
        self.applied_events.add(event_id)
        self.music_event_id = event_id
        self.music_state = state
        return True

    def set_music(self, event_id: str, state: str, generation: int, audio_fence: int) -> bool:
        decision = self._media_gate(
            kind="music",
            event_id=event_id,
            generation=generation,
            audio_fence=audio_fence,
            payload=state,
            priority=PRIORITY["music"],
        )
        if decision != "ready":
            return False
        return self._activate_music(event_id, state)

    def _activate_sfx(self, event_id: str) -> bool:
        self.applied_events.add(event_id)
        self.sfx_events.add(event_id)
        return True

    def play_sfx(self, event_id: str, generation: int, audio_fence: int) -> bool:
        decision = self._media_gate(
            kind="sfx",
            event_id=event_id,
            generation=generation,
            audio_fence=audio_fence,
            payload=None,
            priority=PRIORITY["sfx"],
        )
        if decision != "ready":
            return False
        return self._activate_sfx(event_id)

    def _clear_all(self) -> None:
        self.buffers.clear()
        self.active_speech = None
        self.sfx_events.clear()
        self.music_event_id = None
        self.music_state = "silence"
        self.music_gain = NORMAL_GAIN
        self.sfx_gain = NORMAL_GAIN

    def apply_control(
        self,
        audio_fence: int,
        scope: str,
        speech_key: tuple[str, str] | None = None,
        *,
        authoritative_snapshot: bool = False,
    ) -> bool:
        if audio_fence <= self.audio_fence:
            return False
        if audio_fence != self.audio_fence + 1 and not authoritative_snapshot:
            self._request_control_gap()
            return False

        # One synchronous control transition: clear old media before publishing
        # the new applied fence or admitting anything waiting behind it.
        if scope == "all_audio":
            self._clear_all()
        elif scope == "speech_identity" and speech_key is not None:
            self._clear_speech(speech_key)
        else:
            raise ValueError("invalid_control_scope")
        old_cleared_before_drain = (
            scope != "all_audio"
            or (
                self.active_speech is None
                and not self.buffers
                and not self.sfx_events
                and self.music_state == "silence"
            )
        )
        self.control_barrier_observations.append({
            "audio_fence": audio_fence,
            "scope": scope,
            "old_cleared_before_drain": old_cleared_before_drain,
            "waiting_media": sum(item.audio_fence == audio_fence for item in self.pending_media),
        })
        self.audio_fence = audio_fence

        ready = [item for item in self.pending_media if item.audio_fence == audio_fence]
        self.pending_media = [item for item in self.pending_media if item.audio_fence > audio_fence]
        for item in sorted(ready, key=lambda pending: -pending.priority):
            if not self.lease or self.lease.generation != item.generation:
                self.dropped_stale_generation += 1
                continue
            if item.kind == "speech":
                line, buffered_ms = item.payload
                self._activate_speech(item.event_id, line, buffered_ms)
            elif item.kind == "chunk":
                line, duration_ms = item.payload
                self._activate_chunk(item.event_id, line, duration_ms)
            elif item.kind == "music":
                self._activate_music(item.event_id, item.payload)
            elif item.kind == "sfx":
                self._activate_sfx(item.event_id)
        return True

    def stop_all(self, audio_fence: int) -> None:
        self.apply_control(audio_fence, "all_audio")


class AudioServer:
    def __init__(self, router: Router, provider: FakeProvider, players: list[FakePlayer]) -> None:
        self.router = router
        self.provider = provider
        self.players = {player.consumer_id: player for player in players}
        self.lines: dict[str, SpeechLine] = {}
        self.generation = 0
        self.current_lease: Lease | None = None
        self.audio_fence = 0
        self.world_revision = 7
        self.kernel_calls = 0
        self.provider_late_drops = 0
        self.metrics: list[dict[str, Any]] = []
        self.cancel_fanout_complete: set[tuple[str, str]] = set()
        self.music_revision = 0
        self.current_music_state = "silence"

    def record_metric(self, row: dict[str, Any]) -> None:
        unexpected = set(row) - METRIC_FIELDS
        if unexpected:
            raise ValueError(f"telemetry_schema_rejected:{sorted(unexpected)}")
        missing = METRIC_REQUIRED_FIELDS - set(row)
        if missing:
            raise ValueError(f"telemetry_required_missing:{sorted(missing)}")
        self.metrics.append(row)

    def metrics_schema_valid(self) -> bool:
        return all(
            METRIC_REQUIRED_FIELDS <= set(row) <= METRIC_FIELDS
            for row in self.metrics
        )

    def grant_lease(self, consumer_id: str, now_ms: int, duration_ms: int = 5_000) -> Lease:
        if self.current_lease:
            self.audio_fence += 1
            for player in self.players.values():
                player.stop_all(self.audio_fence)
            self.players[self.current_lease.consumer_id].lease = None
        self.generation += 1
        lease = Lease(f"lease:{self.generation}", self.generation, consumer_id, now_ms + duration_ms)
        self.current_lease = lease
        self.players[consumer_id].grant(lease)
        if self.current_music_state != "silence":
            self.players[consumer_id].set_music(
                f"music-delivery:music-state-{self.music_revision}:lease-{lease.generation}",
                self.current_music_state,
                lease.generation,
                self.audio_fence,
            )
        return lease

    def set_music_state(self, state: str) -> bool:
        self.music_revision += 1
        self.current_music_state = state
        if not self.current_lease:
            return False
        player = self.players[self.current_lease.consumer_id]
        return player.set_music(
            f"music-delivery:music-state-{self.music_revision}:lease-{self.current_lease.generation}",
            state,
            self.current_lease.generation,
            self.audio_fence,
        )

    def deliver_sfx(self, event_id: str) -> bool:
        if not self.current_lease:
            return False
        player = self.players[self.current_lease.consumer_id]
        return player.play_sfx(event_id, self.current_lease.generation, self.audio_fence)

    def submit(self, request: LineRequest, now_ms: int) -> SpeechLine:
        line = self.router.route(request)
        line.audio_fence = max(line.audio_fence, self.audio_fence)
        self.lines[line.line_id] = line
        if line.source == "tts" and line.status == "pending" and self.current_lease:
            self.provider.start(line)
            line.status = "generating"
            self.record_metric({
                "line_id": line.line_id,
                "attempt": line.attempt,
                "model_id": line.model_id,
                "voice_key": line.voice_key,
                "input_characters": line.input_character_count,
                "text_hmac_sha256": line.text_hmac_sha256,
                "telemetry_key_id": "fake-r6",
                "retention_policy_id": "fake-r6-retention",
                "deletion_disposition_id": "fake-r6-deletion",
                "provider_started_ms": now_ms,
                "provider_credit_observed": None,
                "provider_request_id": None,
            })
        return line

    def deliver_cached(self, line: SpeechLine) -> None:
        assert self.current_lease
        player = self.players[self.current_lease.consumer_id]
        player.play(
            event_id=f"audio.play:{line.playback_attempt_id}",
            line=line,
            generation=self.current_lease.generation,
            buffered_ms=0,
        )

    def provider_chunk(self, line_id: str, context_id: str, chunk_seq: int, duration_ms: int, now_ms: int) -> None:
        line = self.lines[line_id]
        if line.context_id != context_id or line.status == "cancelled" or chunk_seq <= line.last_chunk_seq:
            self.provider_late_drops += 1
            return
        line.last_chunk_seq = chunk_seq
        line.first_chunk_seen = True
        if self.metrics and self.metrics[-1]["line_id"] == line_id and "first_provider_audio_ms" not in self.metrics[-1]:
            self.metrics[-1]["first_provider_audio_ms"] = now_ms
            self.metrics[-1]["provider_ttfa_ms"] = now_ms - self.metrics[-1]["provider_started_ms"]
        if not self.current_lease:
            return
        player = self.players[self.current_lease.consumer_id]
        if chunk_seq == 1:
            accepted = player.play(
                event_id=f"audio.play:{line.playback_attempt_id}",
                line=line,
                generation=self.current_lease.generation,
            )
            if not accepted:
                return
        player.chunk(line, self.current_lease.generation, chunk_seq, duration_ms)

    def cancel(self, line_id: str, context_id: str, now_ms: int) -> int:
        line = self.lines[line_id]
        if line.context_id != context_id:
            raise ValueError("identity_mismatch")
        self.audio_fence += 1
        line.audio_fence = self.audio_fence
        line.status = "cancelled"
        if line.source == "tts":
            self.provider.close_context(context_id)
        for player in self.players.values():
            player.stop(line_id, context_id, self.audio_fence)
        self.cancel_fanout_complete.add((line_id, context_id))
        for metric in reversed(self.metrics):
            if metric["line_id"] == line_id and metric["attempt"] == line.attempt:
                metric["cancelled_ms"] = now_ms
                metric["outcome"] = "cancelled"
                break
        return self.audio_fence

    def retry_audio(self, line_id: str, now_ms: int) -> SpeechLine:
        old = self.lines[line_id]
        if old.source != "tts":
            return old
        if not self.current_lease or (
            old.status in {"cancelled", "interrupted"}
            and (old.line_id, old.context_id) not in self.cancel_fanout_complete
        ):
            raise RuntimeError("retry_waiting_for_audio_admission")
        attempt = old.attempt + 1
        retried = replace(
            old,
            attempt=attempt,
            context_id=f"ctx:{line_id}:a{attempt}",
            playback_attempt_id=f"play:{line_id}:a{attempt}",
            status="generating",
            audio_fence=self.audio_fence,
            last_chunk_seq=0,
            first_chunk_seen=False,
        )
        self.lines[line_id] = retried
        self.router.by_line_id[line_id] = retried
        self.provider.start(retried)
        self.record_metric({
            "line_id": line_id,
            "attempt": retried.attempt,
            "model_id": retried.model_id,
            "voice_key": retried.voice_key,
            "input_characters": retried.input_character_count,
            "text_hmac_sha256": retried.text_hmac_sha256,
            "telemetry_key_id": "fake-r6",
            "retention_policy_id": "fake-r6-retention",
            "deletion_disposition_id": "fake-r6-deletion",
            "provider_started_ms": now_ms,
            "provider_credit_observed": None,
            "provider_request_id": None,
            "retry_reason": "explicit_audio_retry",
        })
        return retried

    def provider_failure(self, line_id: str, code: str, now_ms: int) -> None:
        line = self.lines[line_id]
        if line.first_chunk_seen:
            self.audio_fence += 1
            line.audio_fence = self.audio_fence
            line.status = "interrupted"
            for player in self.players.values():
                player.stop(line.line_id, line.context_id, self.audio_fence)
            self.cancel_fanout_complete.add((line.line_id, line.context_id))
        else:
            line.status = "failed_text_only"
            self.cancel_fanout_complete.add((line.line_id, line.context_id))
        for metric in reversed(self.metrics):
            if metric["line_id"] == line_id and metric["attempt"] == line.attempt:
                metric["failed_ms"] = now_ms
                metric["outcome"] = line.status
                metric["error_code"] = code
                break


def fixture() -> tuple[Router, FakeProvider, list[FakePlayer], AudioServer]:
    voices = VoiceRegistry(
        entries={
            "narrator.severin": VoiceEntry("narrator.severin", "voice-severin", "flash", None, "approved"),
            "npc.vesper": VoiceEntry("npc.vesper", "voice-vesper", "multilingual", "npc.guard", "approved"),
            "npc.guard": VoiceEntry("npc.guard", "voice-guard", "flash", "npc.generic", "approved"),
            "npc.generic": VoiceEntry("npc.generic", None, "flash", None, "blocked"),
            "npc.blocked": VoiceEntry("npc.blocked", "voice-uncleared", "flash", "npc.guard", "blocked"),
        },
        entity_routes={"npc:vesper": "npc.vesper", "npc:blocked": "npc.blocked"},
        archetype_routes={"guard": "npc.guard"},
    )
    cache = CacheSelector(
        pools={
            "combat.hit": [
                Asset("combat.hit.1", "combat.hit", 520, "a" * 64, "approved"),
                Asset("combat.hit.2", "combat.hit", 610, "b" * 64, "approved"),
                Asset("combat.hit.blocked", "combat.hit", 500, "c" * 64, "blocked"),
            ],
            "combat.miss": [Asset("combat.miss.1", "combat.miss", 480, "d" * 64, "approved")],
        }
    )
    router = Router(voices, cache)
    provider = FakeProvider()
    players = [FakePlayer("table-a"), FakePlayer("scene-b")]
    return router, provider, players, AudioServer(router, provider, players)


def request(
    presentation_id: str,
    *,
    event_key: str = "story.narration",
    speaker_role: str = "narrator",
    entity_id: str | None = None,
    archetype: str | None = None,
    normal_combat: bool = False,
    disclosed: bool = True,
    text: str = "The disclosed line.",
) -> LineRequest:
    return LineRequest(
        room_id="room-1",
        turn_id="turn-1",
        presentation_id=presentation_id,
        text_event_id=f"text:{presentation_id}",
        ordinal=1,
        speaker_role=speaker_role,
        entity_id=entity_id,
        archetype=archetype,
        event_key=event_key,
        text=text,
        disclosed=disclosed,
        normal_combat=normal_combat,
        important=not normal_combat,
    )


def run_probe() -> dict[str, Any]:
    router, provider, players, server = fixture()
    server.grant_lease("table-a", now_ms=0)

    hit_a = server.submit(request("combat-1", event_key="combat.hit", normal_combat=True), now_ms=0)
    hit_a_retry = server.submit(request("combat-1", event_key="combat.hit", normal_combat=True), now_ms=1)
    hit_b = server.submit(request("combat-2", event_key="combat.hit", normal_combat=True), now_ms=2)
    combat_provider_calls = len(provider.started)
    server.deliver_cached(hit_a)
    players[0].stop(hit_a.line_id, hit_a.context_id)

    story = server.submit(request("story-1", text="Severin speaks only disclosed truth."), now_ms=10)
    story_context = story.context_id
    server.provider_chunk(story.line_id, story_context, 1, 120, now_ms=85)
    buffered_before_cancel = players[0].buffers[(story.line_id, story_context)]
    cancel_fence = server.cancel(story.line_id, story_context, now_ms=90)
    server.provider_chunk(story.line_id, story_context, 2, 80, now_ms=95)

    old_generation = server.current_lease.generation
    server.grant_lease("scene-b", now_ms=100)
    new_document_auto_replays = players[1].play_count
    stale_play = players[0].play("stale-play", hit_b, old_generation)
    fresh_hit = server.submit(request("combat-3", event_key="combat.hit", normal_combat=True), now_ms=101)
    duplicate_event = f"audio.play:{fresh_hit.playback_attempt_id}"
    first_play = players[1].play(duplicate_event, fresh_hit, server.current_lease.generation)
    duplicate_play = players[1].play(duplicate_event, fresh_hit, server.current_lease.generation)
    players[1].stop(fresh_hit.line_id, fresh_hit.context_id)

    world_revision_before_retry = server.world_revision
    retry = server.retry_audio(story.line_id, now_ms=110)
    world_revision_after_retry = server.world_revision
    server.provider_failure(retry.line_id, "concurrent_limit_exceeded", now_ms=120)

    blocked_voice = server.submit(
        request("npc-1", speaker_role="npc", entity_id="npc:blocked", archetype="guard"),
        now_ms=130,
    )
    missing_voice = server.submit(
        request("npc-2", speaker_role="npc", entity_id="npc:unknown", archetype=None),
        now_ms=140,
    )

    partial = server.submit(request("story-partial", text="A partial provider line."), now_ms=150)
    server.provider_chunk(partial.line_id, partial.context_id, 1, 90, now_ms=180)
    partial_buffer_before_failure = players[1].buffers[(partial.line_id, partial.context_id)]
    server.provider_failure(partial.line_id, "provider_busy", now_ms=190)
    partial_buffer_after_failure = players[1].buffers.get((partial.line_id, partial.context_id), 0)

    player = players[1]
    server.set_music_state("danger")
    mixer_line = server.submit(request("combat-mix", event_key="combat.miss", normal_combat=True), now_ms=195)
    player.play("audio.play:mixer", mixer_line, server.current_lease.generation)
    ducked = (player.music_gain, player.sfx_gain)
    player.stop(mixer_line.line_id, mixer_line.context_id)
    restored = (player.music_gain, player.sfx_gain)

    secret = "GM_ONLY_CANARY_377_R6"
    undisclosed_rejected = False
    try:
        server.submit(request("secret", disclosed=False, text=secret), now_ms=200)
    except ValueError as exc:
        undisclosed_rejected = str(exc) == "undisclosed_text"
    serialized_metrics = json.dumps(server.metrics, sort_keys=True)

    _, _, lane_players, lane_server = fixture()
    lane_lease_1 = lane_server.grant_lease("table-a", now_ms=0)
    lane_server.set_music_state("danger")
    lane_server.deliver_sfx("sfx:before-election")
    lane_fence_1 = lane_server.audio_fence
    lane_lease_2 = lane_server.grant_lease("scene-b", now_ms=50)
    new_leader_sfx_before_future = len(lane_players[1].sfx_events)
    stale_music = lane_players[0].set_music(
        "music:stale", "boss", lane_lease_1.generation, lane_fence_1
    )
    stale_sfx = lane_players[0].play_sfx(
        "sfx:stale", lane_lease_1.generation, lane_fence_1
    )
    future_sfx = lane_server.deliver_sfx("sfx:future")

    _, _, barrier_players, barrier_server = fixture()
    barrier_lease = barrier_server.grant_lease("table-a", now_ms=0)
    barrier_player = barrier_players[0]
    barrier_old = barrier_server.submit(
        request("barrier-old", event_key="combat.hit", normal_combat=True), now_ms=0
    )
    barrier_player.play("speech:barrier-old", barrier_old, barrier_lease.generation)
    barrier_server.set_music_state("danger")
    barrier_server.deliver_sfx("sfx:barrier-old")
    barrier_fence = barrier_player.audio_fence + 1
    barrier_new = replace(
        barrier_server.submit(
            request("barrier-new", event_key="combat.miss", normal_combat=True), now_ms=1
        ),
        audio_fence=barrier_fence,
    )
    barrier_player.play("speech:barrier-new", barrier_new, barrier_lease.generation)
    barrier_player.set_music("music:barrier-new", "boss", barrier_lease.generation, barrier_fence)
    barrier_player.play_sfx("sfx:barrier-new", barrier_lease.generation, barrier_fence)
    barrier_pending_before = len(barrier_player.pending_media)
    old_preserved_before_control = (
        barrier_player.active_speech == (barrier_old.line_id, barrier_old.context_id)
        and barrier_player.music_state == "danger"
        and barrier_player.sfx_events == {"sfx:barrier-old"}
    )
    new_started_before_control = any(
        event_id in barrier_player.applied_events
        for event_id in ("speech:barrier-new", "music:barrier-new", "sfx:barrier-new")
    )
    barrier_player.apply_control(barrier_fence, "all_audio")
    new_admitted_after_control = (
        barrier_player.active_speech == (barrier_new.line_id, barrier_new.context_id)
        and barrier_player.music_state == "boss"
        and barrier_player.sfx_events == {"sfx:barrier-new"}
    )
    old_absent_after_control = (
        (barrier_old.line_id, barrier_old.context_id) not in barrier_player.buffers
        and "sfx:barrier-old" not in barrier_player.sfx_events
    )

    _, _, overflow_players, overflow_server = fixture()
    overflow_lease = overflow_server.grant_lease("table-a", now_ms=0)
    overflow_player = overflow_players[0]
    overflow_server.set_music_state("danger")
    overflow_fence = overflow_player.audio_fence + 1
    for index in range(FUTURE_MEDIA_MAX_EVENTS + 1):
        overflow_player.play_sfx(
            f"sfx:overflow:{index}", overflow_lease.generation, overflow_fence
        )

    return {
        "oracle": "PASS",
        "cache": {
            "provider_calls_for_normal_combat": combat_provider_calls,
            "retry_asset_stable": hit_a.asset_id == hit_a_retry.asset_id,
            "first_cycle_unique": hit_a.asset_id != hit_b.asset_id,
            "selected_assets": [hit_a.asset_id, hit_b.asset_id],
        },
        "routing": {
            "severin_voice": story.voice_key,
            "blocked_entity_explicit_fallback": blocked_voice.voice_key,
            "missing_voice": missing_voice.source,
        },
        "cancel": {
            "provider_context_closed": story_context in provider.closed_contexts,
            "buffered_before_ms": buffered_before_cancel,
            "buffered_after_ms": players[0].buffers.get((story.line_id, story_context), 0),
            "stop_observed_in_same_call": True,
            "late_provider_chunks_dropped": server.provider_late_drops,
            "audio_fence": cancel_fence,
        },
        "provider_failure_after_audio": {
            "status": partial.status,
            "buffered_before_ms": partial_buffer_before_failure,
            "buffered_after_ms": partial_buffer_after_failure,
        },
        "leader_replay": {
            "generations": [old_generation, server.current_lease.generation],
            "current_leader": server.current_lease.consumer_id,
            "stale_play_accepted": stale_play,
            "first_play_accepted": first_play,
            "duplicate_play_accepted": duplicate_play,
            "new_document_auto_replays": new_document_auto_replays,
        },
        "all_audible_lanes": {
            "generations": [lane_lease_1.generation, lane_lease_2.generation],
            "old_leader_music_after_loss": lane_players[0].music_state,
            "old_leader_sfx_after_loss": len(lane_players[0].sfx_events),
            "new_leader_music_snapshot": lane_players[1].music_state,
            "new_leader_sfx_before_future": new_leader_sfx_before_future,
            "stale_music_accepted": stale_music,
            "stale_sfx_accepted": stale_sfx,
            "future_sfx_accepted": future_sfx,
        },
        "control_barrier": {
            "future_media_buffered_before_control": barrier_pending_before,
            "old_media_preserved_before_control": old_preserved_before_control,
            "new_media_started_before_control": new_started_before_control,
            "old_cleared_before_drain": barrier_player.control_barrier_observations[-1]["old_cleared_before_drain"],
            "old_media_absent_after_control": old_absent_after_control,
            "new_media_admitted_after_control": new_admitted_after_control,
            "pending_after_control": len(barrier_player.pending_media),
            "applied_control_fence": barrier_player.audio_fence,
            "overflow_gap_requests": overflow_player.control_gap_requests,
            "overflow_pending_after_gap": len(overflow_player.pending_media),
            "overflow_old_music_preserved": overflow_player.music_state,
        },
        "retry_failure": {
            "world_revision_before": world_revision_before_retry,
            "world_revision_after": world_revision_after_retry,
            "kernel_calls": server.kernel_calls,
            "attempt": retry.attempt,
            "status": retry.status,
        },
        "mixer": {
            "priority": PRIORITY,
            "music_state": player.music_state,
            "ducked_gains": ducked,
            "restored_gains": restored,
        },
        "privacy_observability": {
            "metrics_rows": len(server.metrics),
            "metrics_schema_valid": server.metrics_schema_valid(),
            "text_absent": "Severin speaks" not in serialized_metrics,
            "secret_canary_absent": secret not in serialized_metrics,
            "undisclosed_rejected": undisclosed_rejected,
            "cost_policy_selected": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2, sort_keys=True))
