#!/usr/bin/env python
"""Deterministic R5 speech-contract probe; no browser, network, audio file, or provider."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


AUDIO_PROFILE = {
    "encoding": "linear16",
    "sample_rate_hz": 16000,
    "channels": 1,
    "sample_endianness": "little",
    "frame_duration_ms": 20,
}
NUMBER_WORDS = {
    "ноль": 0,
    "один": 1,
    "два": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20,
}


@dataclass
class PendingRoll:
    pending_roll_id: str
    actor_id: str
    expected_aggregate_version: int


@dataclass
class Draft:
    turn_id: str
    actor_id: str
    kind: str
    text: str
    version: int = 1
    pending_roll_id: str | None = None
    declared_total: int | None = None
    expected_aggregate_version: int = 0
    approved: bool = False


@dataclass
class Attempt:
    capture_id: str
    turn_id: str
    actor_id: str
    activation_source: str
    purpose: str
    pending_roll_id: str | None
    expected_aggregate_version: int
    stream_generation: int
    state: str = "armed"
    frame_count: int = 0
    next_frame_seq: int = 1
    provider_request_id: str | None = None
    provisional_text: str = ""
    final_segments: dict[str, str] = field(default_factory=dict)
    final_transcript_id: str | None = None
    candidate_event_id: str | None = None
    provider_metadata_received: bool = False
    failure_code: str | None = None

    def durable_record(self) -> dict[str, Any]:
        """The durable shape deliberately omits raw audio and provisional text."""
        return {
            "schema_version": 1,
            "room_id": "room-synthetic",
            "capture_id": self.capture_id,
            "turn_id": self.turn_id,
            "actor_id": self.actor_id,
            "activation_source": self.activation_source,
            "route": "server_proxy",
            "purpose": self.purpose,
            "pending_roll_id": self.pending_roll_id,
            "state": self.state,
            "stream_generation": self.stream_generation,
            "expected_aggregate_version": self.expected_aggregate_version,
            "frame_count": self.frame_count,
            "provider_request_id": self.provider_request_id,
            "final_transcript_id": self.final_transcript_id,
            "candidate_event_id": self.candidate_event_id,
            "failure_code": self.failure_code,
        }


class ContractError(RuntimeError):
    pass


class SpeechContract:
    def __init__(self) -> None:
        self.allowed_actors = {"actor-1", "actor-2", "actor-3"}
        self.attempts: dict[str, Attempt] = {}
        self.active_capture_id: str | None = None
        self.admission_results: dict[str, tuple[str, dict[str, Any]]] = {}
        self.finalized_events: dict[str, dict[str, Any]] = {}
        self.r4_receive_results: dict[str, tuple[str, dict[str, Any]]] = {}
        self.drafts: dict[str, Draft] = {}
        self.pending_rolls: dict[str, PendingRoll] = {}
        self.approval_results: dict[str, tuple[str, dict[str, Any]]] = {}
        self.audit: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.capture_counter = 0
        self.world_mutations = 0
        self.declared_roll_commits = 0
        self.provider_frames = 0
        self.ambient_frames_ignored = 0
        self.late_provider_events = 0
        self.current_audio: tuple[str, str] | None = None

    def set_pending_roll(self, roll: PendingRoll) -> None:
        self.pending_rolls[roll.actor_id] = roll

    def ambient_frame(self) -> None:
        self.ambient_frames_ignored += 1

    def start_capture(
        self,
        actor_id: str,
        expected_aggregate_version: int,
        activation_source: str = "ptt",
        command_id: str | None = None,
    ) -> dict[str, Any]:
        command_id = command_id or f"start-auto-{self.capture_counter + 1}"
        digest = f"{actor_id}:{expected_aggregate_version}:{activation_source}"
        if command_id in self.admission_results:
            first_digest, first_result = self.admission_results[command_id]
            if first_digest != digest:
                raise ContractError("idempotency_conflict")
            return first_result
        if activation_source not in {"ptt", "wake_word"}:
            raise ContractError("bad_activation_source")
        if actor_id not in self.allowed_actors:
            return self._reject_start(command_id, digest, "actor_not_allowed", retryable=False)
        if self.active_capture_id is not None:
            return self._reject_start(command_id, digest, "capture_already_active", retryable=True)
        pending = self.pending_rolls.get(actor_id)
        if pending and pending.expected_aggregate_version != expected_aggregate_version:
            return self._reject_start(command_id, digest, "stale_version", retryable=True)
        self.capture_counter += 1
        capture_id = f"00000000-0000-4000-8000-{self.capture_counter:012d}"
        turn_id = f"turn-{self.capture_counter:04d}"
        purpose = "declared_roll" if pending else "action"
        attempt = Attempt(
            capture_id=capture_id,
            turn_id=turn_id,
            actor_id=actor_id,
            activation_source=activation_source,
            purpose=purpose,
            pending_roll_id=pending.pending_roll_id if pending else None,
            expected_aggregate_version=(
                pending.expected_aggregate_version if pending else expected_aggregate_version
            ),
            stream_generation=self.capture_counter,
            state="capturing",
        )
        self.attempts[capture_id] = attempt
        self.active_capture_id = capture_id
        barge_requested = self.current_audio is not None
        if barge_requested:
            line_id, context_id = self.current_audio
            self.events.append(
                {
                    "kind": "audio.stop",
                    "line_id": line_id,
                    "context_id": context_id,
                    "reason": "input_barge_in",
                }
            )
            self.current_audio = None
        event = {
            "protocol_version": 1,
            "kind": "input.capture.accepted",
            "capture_id": capture_id,
            "turn_id": turn_id,
            "actor_id": actor_id,
            "route": "server_proxy",
            "purpose": purpose,
            "pending_roll_id": attempt.pending_roll_id,
            "stream_generation": attempt.stream_generation,
            "audio_profile": AUDIO_PROFILE,
            "audio_ticket_expires_at": "2026-08-16T18:00:30Z",
            "barge_in": {
                "requested": barge_requested,
                "local_playback_stopped": barge_requested,
                "server_audio_fenced": barge_requested,
            },
        }
        self.events.append(event)
        self.admission_results[command_id] = (digest, event)
        self._audit("capture_started", attempt)
        return event

    def _reject_start(
        self,
        command_id: str,
        digest: str,
        code: str,
        *,
        retryable: bool,
    ) -> dict[str, Any]:
        event = {
            "protocol_version": 1,
            "kind": "input.capture.rejected",
            "command_id": command_id,
            "error_code": code,
            "retryable": retryable,
        }
        self.admission_results[command_id] = (digest, event)
        self.events.append(event)
        return event

    def send_frame(self, capture_id: str, frame_seq: int, payload: bytes) -> None:
        attempt = self._current(capture_id, {"capturing"})
        if frame_seq != attempt.next_frame_seq:
            self._fail(attempt, "audio_stream_lost")
            raise ContractError("frame_gap")
        if len(payload) != 640 or len(payload) % 2:
            self._fail(attempt, "unsupported_audio_profile")
            raise ContractError("bad_frame_size")
        attempt.frame_count += 1
        attempt.next_frame_seq += 1
        self.provider_frames += 1
        # The payload is intentionally neither stored nor logged.

    def provider_result(
        self,
        capture_id: str,
        request_id: str,
        start_ms: int,
        duration_ms: int,
        text: str,
        *,
        is_final: bool,
        speech_final: bool,
    ) -> None:
        attempt = self.attempts[capture_id]
        if attempt.state not in {"capturing", "finalizing"}:
            self.late_provider_events += 1
            self._audit("late_provider_event", attempt)
            return
        if attempt.provider_request_id is None:
            attempt.provider_request_id = request_id
        elif attempt.provider_request_id != request_id:
            self._fail(attempt, "provider_protocol_error")
            return
        if not is_final:
            attempt.provisional_text = text
            return
        segment_id = f"seg:{request_id}:{start_ms}:{duration_ms}"
        existing = attempt.final_segments.get(segment_id)
        if existing is not None and existing != text:
            self._fail(attempt, "conflicting_final_segment")
            return
        attempt.final_segments[segment_id] = text.strip()
        if speech_final:
            self._audit("provider_pause_observed", attempt)

    def end_audio(self, capture_id: str, reason: str = "released") -> dict[str, Any]:
        attempt = self._current(capture_id, {"capturing"})
        if reason == "cancelled":
            attempt.state = "cancelled"
            attempt.provisional_text = ""
            attempt.final_segments.clear()
            self.active_capture_id = None
        elif reason == "released":
            attempt.state = "finalizing"
        else:
            raise ContractError("bad_end_reason")
        event = {
            "protocol_version": 1,
            "kind": "input.audio.end",
            "capture_id": capture_id,
            "stream_generation": attempt.stream_generation,
            "last_frame_seq": max(attempt.next_frame_seq - 1, 0),
            "reason": reason,
        }
        self.events.append(event)
        if reason == "cancelled":
            self.events.append(
                {
                    "protocol_version": 1,
                    "kind": "input.capture.cancelled",
                    "capture_id": capture_id,
                    "partial_discarded": True,
                }
            )
        return event

    def provider_metadata(self, capture_id: str, request_id: str) -> dict[str, Any] | None:
        attempt = self.attempts[capture_id]
        if attempt.state != "finalizing":
            self.late_provider_events += 1
            self._audit("late_provider_event", attempt)
            return None
        if attempt.provider_request_id != request_id:
            return self._fail(attempt, "provider_protocol_error")
        attempt.provider_metadata_received = True
        self._audit("provider_metadata_received", attempt)
        return None

    def provider_closed(self, capture_id: str, *, normal: bool) -> dict[str, Any] | None:
        attempt = self.attempts[capture_id]
        if attempt.state != "finalizing":
            self.late_provider_events += 1
            self._audit("late_provider_event", attempt)
            return None
        if not normal:
            return self._fail(attempt, "provider_protocol_error")
        if not attempt.provider_metadata_received:
            return self._fail(attempt, "provider_terminal_missing")
        return self._persist_candidate(attempt)

    def _persist_candidate(self, attempt: Attempt) -> dict[str, Any]:
        capture_id = attempt.capture_id
        segments = sorted(
            attempt.final_segments.items(),
            key=lambda pair: tuple(int(value) for value in pair[0].rsplit(":", 2)[1:]),
        )
        text = " ".join(part for _, part in segments if part).strip()
        if not text:
            return self._fail(attempt, "no_speech")
        attempt.state = "ready"
        attempt.provisional_text = ""
        attempt.final_transcript_id = f"transcript:{capture_id}:1"
        attempt.candidate_event_id = f"speech-final:{capture_id}"
        speech_event = {
            "protocol_version": 1,
            "kind": "speech.finalized",
            "event_id": attempt.candidate_event_id,
            "room_id": "room-synthetic",
            "capture_id": capture_id,
            "turn_id": attempt.turn_id,
            "actor_id": attempt.actor_id,
            "purpose": attempt.purpose,
            "pending_roll_id": attempt.pending_roll_id,
            "final_transcript_id": attempt.final_transcript_id,
            "text": text,
            "provider_request_id": attempt.provider_request_id,
            "segment_ids": [segment_id for segment_id, _ in segments],
            "expected_aggregate_version": attempt.expected_aggregate_version,
        }
        if attempt.purpose == "declared_roll":
            total = parse_explicit_roll(text)
            if total is None:
                return self._fail(attempt, "unrecognized_roll_declaration")
        self.finalized_events[attempt.candidate_event_id] = speech_event
        self.events.append(speech_event)
        self.active_capture_id = None
        self._audit("candidate_ready", attempt)
        return speech_event

    def submit_ready(self, capture_id: str) -> dict[str, Any]:
        attempt = self.attempts[capture_id]
        if attempt.state == "submitted":
            command_id = f"receive:{capture_id}"
            return self.r4_receive_results[command_id][1]
        if attempt.state != "ready" or attempt.candidate_event_id is None:
            raise ContractError("candidate_not_ready")
        speech_event = self.finalized_events[attempt.candidate_event_id]
        expected = {
            "capture_id": attempt.capture_id,
            "turn_id": attempt.turn_id,
            "actor_id": attempt.actor_id,
            "purpose": attempt.purpose,
            "pending_roll_id": attempt.pending_roll_id,
            "final_transcript_id": attempt.final_transcript_id,
            "provider_request_id": attempt.provider_request_id,
            "expected_aggregate_version": attempt.expected_aggregate_version,
        }
        if any(speech_event[key] != value for key, value in expected.items()):
            return self._fail(attempt, "provider_protocol_error")
        command_id = f"receive:{capture_id}"
        event_digest = speech_event["event_id"]
        if command_id in self.r4_receive_results:
            first_digest, first_result = self.r4_receive_results[command_id]
            if first_digest != event_digest:
                raise ContractError("idempotency_conflict")
            attempt.state = "submitted"
            return first_result
        text = speech_event["text"]
        if attempt.purpose == "declared_roll":
            total = parse_explicit_roll(text)
            if total is None:
                return self._fail(attempt, "unrecognized_roll_declaration")
            draft = Draft(
                turn_id=attempt.turn_id,
                actor_id=attempt.actor_id,
                kind="declared_roll",
                text=text,
                pending_roll_id=attempt.pending_roll_id,
                declared_total=total,
                expected_aggregate_version=attempt.expected_aggregate_version,
            )
            self.drafts[draft.turn_id] = draft
            roll_event = self._roll_event(draft, attempt.final_transcript_id)
            self.events.append(roll_event)
        else:
            self.drafts[attempt.turn_id] = Draft(
                turn_id=attempt.turn_id,
                actor_id=attempt.actor_id,
                kind="action",
                text=text,
                expected_aggregate_version=attempt.expected_aggregate_version,
            )
        attempt.state = "submitted"
        self._audit("final_submitted", attempt)
        self.r4_receive_results[command_id] = (event_digest, speech_event)
        return speech_event

    def recover_after_restart(self) -> None:
        for attempt in list(self.attempts.values()):
            if attempt.state in {"armed", "capturing", "finalizing"}:
                self._fail(attempt, "server_restart")
            elif attempt.state == "ready":
                self.submit_ready(attempt.capture_id)

    def disconnect(self, capture_id: str) -> dict[str, Any]:
        attempt = self.attempts[capture_id]
        return self._fail(attempt, "audio_stream_lost")

    def correct_draft(self, turn_id: str, expected_version: int, replacement: str) -> Draft:
        draft = self.drafts[turn_id]
        if draft.version != expected_version or draft.approved:
            raise ContractError("stale_draft")
        if draft.kind == "declared_roll":
            raise ContractError("structured_roll_correction_required")
        draft.version += 1
        draft.text = replacement
        return draft

    def correct_declared_roll(
        self,
        turn_id: str,
        expected_version: int,
        pending_roll_id: str,
        declared_total: int,
    ) -> Draft:
        draft = self.drafts[turn_id]
        if draft.version != expected_version or draft.approved:
            raise ContractError("stale_draft")
        if draft.kind != "declared_roll" or draft.pending_roll_id != pending_roll_id:
            raise ContractError("stale_pending_roll")
        draft.version += 1
        draft.text = str(declared_total)
        draft.declared_total = declared_total
        return draft

    def approve_draft(self, command_id: str, turn_id: str, draft_version: int) -> dict[str, Any]:
        digest = f"{turn_id}:{draft_version}"
        if command_id in self.approval_results:
            first_digest, first_result = self.approval_results[command_id]
            if first_digest != digest:
                return {"status": "rejected", "code": "idempotency_conflict"}
            return first_result
        draft = self.drafts[turn_id]
        if draft.version != draft_version:
            result = {"status": "rejected", "code": "stale_draft", "turn_id": turn_id}
        elif draft.approved:
            result = {"status": "accepted", "code": "stored_result", "turn_id": turn_id}
        else:
            draft.approved = True
            if draft.kind == "declared_roll":
                pending = self.pending_rolls.get(draft.actor_id)
                if (
                    pending is None
                    or pending.pending_roll_id != draft.pending_roll_id
                    or pending.expected_aggregate_version != draft.expected_aggregate_version
                ):
                    draft.approved = False
                    result = {"status": "rejected", "code": "stale_pending_roll", "turn_id": turn_id}
                else:
                    self.declared_roll_commits += 1
                    del self.pending_rolls[draft.actor_id]
                    result = {
                        "status": "accepted",
                        "code": "declared_roll_recorded",
                        "turn_id": turn_id,
                        "declared_total": draft.declared_total,
                    }
            else:
                result = {"status": "accepted", "code": "approval_delegated_to_r4", "turn_id": turn_id}
        self.approval_results[command_id] = (digest, result)
        return result

    def _roll_event(self, draft: Draft, transcript_id: str) -> dict[str, Any]:
        return {
            "protocol_version": 1,
            "kind": "roll.declared_candidate",
            "event_id": f"roll-candidate:{draft.turn_id}:{draft.version}",
            "turn_id": draft.turn_id,
            "pending_roll_id": draft.pending_roll_id,
            "actor_id": draft.actor_id,
            "declared_total": draft.declared_total,
            "draft_version": draft.version,
            "source_final_transcript_id": transcript_id,
        }

    def _current(self, capture_id: str, allowed_states: set[str]) -> Attempt:
        attempt = self.attempts[capture_id]
        if self.active_capture_id != capture_id or attempt.state not in allowed_states:
            raise ContractError("capture_not_active")
        return attempt

    def _fail(self, attempt: Attempt, code: str) -> dict[str, Any]:
        attempt.state = "failed"
        attempt.failure_code = code
        attempt.provisional_text = ""
        attempt.final_segments.clear()
        attempt.final_transcript_id = None
        attempt.candidate_event_id = None
        if self.active_capture_id == attempt.capture_id:
            self.active_capture_id = None
        event = {
            "protocol_version": 1,
            "kind": "input.capture.failed",
            "capture_id": attempt.capture_id,
            "error_code": code,
            "retryable": code not in {"permission_denied", "device_missing"},
            "partial_discarded": True,
        }
        self.events.append(event)
        self._audit("capture_failed", attempt, code=code)
        return event

    def _audit(self, event: str, attempt: Attempt, **fields: Any) -> None:
        self.audit.append(
            {
                "event": event,
                "capture_id": attempt.capture_id,
                "actor_id": attempt.actor_id,
                "state": attempt.state,
                **fields,
            }
        )


def parse_explicit_roll(text: str) -> int | None:
    normalized = re.sub(r"[—–-]", " ", text.casefold())
    if not re.search(r"\b(бросок|результат)\b", normalized):
        return None
    return parse_correction_total(normalized)


def parse_correction_total(text: str) -> int | None:
    digits = re.findall(r"(?<!\w)[+-]?\d+(?!\w)", text)
    words = [NUMBER_WORDS[token] for token in re.findall(r"[а-яё]+", text.casefold()) if token in NUMBER_WORDS]
    values = [int(value) for value in digits] + words
    return values[0] if len(values) == 1 else None


def run_probe() -> dict[str, Any]:
    raw_canary = (b"ROOM_RAW_AUDIO_CANARY" * 31)[:640].ljust(640, b"X")
    contract = SpeechContract()

    # Ambient room speech has no provider path without an activation.
    contract.ambient_frame()
    contract.ambient_frame()

    # An actor outside the session allowlist receives no capture or audio ticket.
    disallowed = contract.start_capture(
        "actor-other-room",
        expected_aggregate_version=4,
        command_id="start-disallowed",
    )

    # PTT binds actor before capture, fences current output, and assembles only final segments.
    contract.current_audio = ("line-7", "context-7")
    accepted = contract.start_capture(
        "actor-1",
        expected_aggregate_version=4,
        command_id="start-action",
    )
    accepted_replay = contract.start_capture(
        "actor-1",
        expected_aggregate_version=4,
        command_id="start-action",
    )
    action_capture = accepted["capture_id"]
    contract.send_frame(action_capture, 1, raw_canary)
    contract.provider_result(action_capture, "dg-action", 0, 900, "Осматриваю", is_final=False, speech_final=False)
    contract.provider_result(action_capture, "dg-action", 0, 900, "Осматриваю алтарь", is_final=True, speech_final=False)
    contract.provider_result(action_capture, "dg-action", 900, 800, "и ищу ловушки", is_final=True, speech_final=True)
    contract.provider_result(action_capture, "dg-action", 900, 800, "и ищу ловушки", is_final=True, speech_final=True)
    action_end = contract.end_audio(action_capture)
    contract.provider_metadata(action_capture, "dg-action")
    action_ready = contract.provider_closed(action_capture, normal=True)
    action_final = contract.submit_ready(action_capture)
    action_replay = contract.submit_ready(action_capture)
    contract.provider_metadata(action_capture, "dg-action")  # late terminal is ignored

    # A broken provider stream discards partials; a new capture is required.
    broken = contract.start_capture("actor-2", expected_aggregate_version=5)
    broken_capture = broken["capture_id"]
    contract.send_frame(broken_capture, 1, b"Y" * 640)
    contract.provider_result(broken_capture, "dg-broken", 0, 500, "Открываю", is_final=True, speech_final=False)
    broken_failure = contract.disconnect(broken_capture)
    contract.provider_result(broken_capture, "dg-broken", 500, 500, "дверь", is_final=True, speech_final=True)

    # Ordinary numbers cannot satisfy an explicit pending-roll declaration.
    contract.set_pending_roll(PendingRoll("pending-roll-1", "actor-3", 6))
    ambiguous = contract.start_capture("actor-3", expected_aggregate_version=6)
    ambiguous_capture = ambiguous["capture_id"]
    contract.send_frame(ambiguous_capture, 1, b"Z" * 640)
    contract.provider_result(ambiguous_capture, "dg-ambiguous", 0, 700, "У меня 17 стрел", is_final=True, speech_final=True)
    contract.end_audio(ambiguous_capture)
    contract.provider_metadata(ambiguous_capture, "dg-ambiguous")
    ambiguous_failure = contract.provider_closed(ambiguous_capture, normal=True)

    # A first explicit declaration freezes revision 6 and becomes stale when the pending roll advances.
    explicit = contract.start_capture("actor-3", expected_aggregate_version=6)
    explicit_capture = explicit["capture_id"]
    contract.send_frame(explicit_capture, 1, b"Q" * 640)
    contract.provider_result(explicit_capture, "dg-roll", 0, 600, "Бросок — 17", is_final=True, speech_final=True)
    contract.end_audio(explicit_capture)
    contract.provider_metadata(explicit_capture, "dg-roll")
    roll_ready = contract.provider_closed(explicit_capture, normal=True)
    roll_final = contract.submit_ready(explicit_capture)
    corrected = contract.correct_declared_roll(
        explicit["turn_id"],
        1,
        "pending-roll-1",
        18,
    )
    stale_approval = contract.approve_draft("approve-stale", explicit["turn_id"], 1)
    contract.pending_rolls["actor-3"].expected_aggregate_version = 7
    stale_revision_approval = contract.approve_draft(
        "approve-stale-revision",
        explicit["turn_id"],
        2,
    )

    # Metadata without a normal close is terminal failure, not a candidate.
    abnormal = contract.start_capture("actor-2", expected_aggregate_version=5)
    abnormal_capture = abnormal["capture_id"]
    contract.send_frame(abnormal_capture, 1, b"M" * 640)
    contract.provider_result(abnormal_capture, "dg-abnormal", 0, 500, "Иду", is_final=True, speech_final=True)
    contract.end_audio(abnormal_capture)
    contract.provider_metadata(abnormal_capture, "dg-abnormal")
    abnormal_failure = contract.provider_closed(abnormal_capture, normal=False)

    # Same segment identity with different text is a conflict and fails closed.
    conflicting = contract.start_capture("actor-2", expected_aggregate_version=5)
    conflicting_capture = conflicting["capture_id"]
    contract.send_frame(conflicting_capture, 1, b"C" * 640)
    contract.provider_result(conflicting_capture, "dg-conflict", 0, 500, "Лево", is_final=True, speech_final=False)
    contract.provider_result(conflicting_capture, "dg-conflict", 0, 500, "Право", is_final=True, speech_final=False)
    conflicting_failure = contract.events[-1]

    # User cancellation discards partials and never asks the provider to finalize a candidate.
    cancelled = contract.start_capture("actor-2", expected_aggregate_version=5)
    cancelled_capture = cancelled["capture_id"]
    contract.send_frame(cancelled_capture, 1, b"K" * 640)
    contract.provider_result(cancelled_capture, "dg-cancel", 0, 500, "Пробую", is_final=False, speech_final=False)
    contract.end_audio(cancelled_capture, reason="cancelled")
    cancelled_event = contract.events[-1]

    # A complete candidate is persisted as ready; restart replays only its deterministic R4 receive.
    recovery = contract.start_capture(
        "actor-1",
        expected_aggregate_version=5,
        command_id="start-recovery",
    )
    recovery_replay = contract.start_capture(
        "actor-1",
        expected_aggregate_version=5,
        command_id="start-recovery",
    )
    recovery_capture = recovery["capture_id"]
    contract.send_frame(recovery_capture, 1, b"R" * 640)
    contract.provider_result(recovery_capture, "dg-recovery", 0, 500, "Жду", is_final=True, speech_final=True)
    contract.end_audio(recovery_capture)
    contract.provider_metadata(recovery_capture, "dg-recovery")
    recovery_ready = contract.provider_closed(recovery_capture, normal=True)
    ready_record_before_restart = contract.attempts[recovery_capture].durable_record()
    contract.recover_after_restart()
    recovery_after_restart = contract.submit_ready(recovery_capture)

    # A fresh capture freezes revision 7; structured correction and duplicate approval are deterministic.
    refreshed = contract.start_capture("actor-3", expected_aggregate_version=7)
    refreshed_capture = refreshed["capture_id"]
    contract.send_frame(refreshed_capture, 1, b"Q" * 640)
    contract.provider_result(refreshed_capture, "dg-roll-2", 0, 600, "Бросок — 17", is_final=True, speech_final=True)
    contract.end_audio(refreshed_capture)
    contract.provider_metadata(refreshed_capture, "dg-roll-2")
    contract.provider_closed(refreshed_capture, normal=True)
    contract.submit_ready(refreshed_capture)
    refreshed_corrected = contract.correct_declared_roll(
        refreshed["turn_id"],
        1,
        "pending-roll-1",
        18,
    )
    approval = contract.approve_draft("approve-current", refreshed["turn_id"], 2)
    duplicate_approval = contract.approve_draft("approve-current", refreshed["turn_id"], 2)

    schema_samples = [
        {
            "protocol_version": 1,
            "kind": "input.capture.start",
            "command_id": "start-sample",
            "actor_id": "actor-1",
            "activation_source": "ptt",
            "expected_aggregate_version": 4,
        },
        disallowed,
        accepted,
        action_end,
        cancelled_event,
        broken_failure,
        action_final,
        {
            "protocol_version": 1,
            "kind": "draft.correct",
            "command_id": "correct-sample",
            "turn_id": accepted["turn_id"],
            "expected_draft_version": 1,
            "replacement_text": "Осматриваю другой проход",
        },
        {
            "protocol_version": 1,
            "kind": "roll.declared_correct",
            "command_id": "roll-correct-sample",
            "turn_id": refreshed["turn_id"],
            "expected_draft_version": 1,
            "pending_roll_id": "pending-roll-1",
            "declared_total": 18,
        },
        next(event for event in contract.events if event.get("kind") == "roll.declared_candidate"),
    ]

    checks = {
        "ambient_audio_never_reaches_provider": contract.provider_frames == 9 and contract.ambient_frames_ignored == 2,
        "disallowed_actor_has_no_capture": disallowed["error_code"] == "actor_not_allowed"
        and len(contract.attempts) == 9,
        "same_command_admission_is_idempotent": accepted_replay == accepted
        and recovery_replay == recovery,
        "actor_bound_before_audio": accepted["actor_id"] == "actor-1" and accepted["purpose"] == "action",
        "barge_in_fences_exact_playback": accepted["barge_in"] == {
            "requested": True,
            "local_playback_stopped": True,
            "server_audio_fenced": True,
        },
        "interim_rewrite_not_committed": action_final["text"] == "Осматриваю алтарь и ищу ловушки",
        "duplicate_final_segment_applies_once": len(action_final["segment_ids"]) == 2,
        "late_terminal_does_not_duplicate_draft": action_replay == action_final
        and accepted["turn_id"] in contract.drafts,
        "disconnect_discards_partial": broken_failure["partial_discarded"] and broken["turn_id"] not in contract.drafts,
        "late_provider_event_after_failure_ignored": contract.late_provider_events == 2,
        "ordinary_number_not_roll": ambiguous_failure is not None and ambiguous_failure["error_code"] == "unrecognized_roll_declaration",
        "explicit_roll_requires_pending_roll": roll_ready is not None
        and roll_final["pending_roll_id"] == "pending-roll-1",
        "roll_correction_versions": corrected.version == 2 and corrected.declared_total == 18,
        "stale_roll_approval_rejected": stale_approval["code"] == "stale_draft",
        "stale_pending_roll_revision_rejected": stale_revision_approval["code"] == "stale_pending_roll",
        "metadata_then_abnormal_close_discards": abnormal_failure is not None
        and abnormal_failure["error_code"] == "provider_protocol_error"
        and abnormal["turn_id"] not in contract.drafts,
        "conflicting_final_segment_discards": conflicting_failure["error_code"] == "conflicting_final_segment"
        and conflicting["turn_id"] not in contract.drafts,
        "cancel_discards_without_candidate": cancelled_event["kind"] == "input.capture.cancelled"
        and contract.attempts[cancelled_capture].candidate_event_id is None
        and cancelled["turn_id"] not in contract.drafts,
        "ready_candidate_has_atomic_event_reference": ready_record_before_restart["state"] == "ready"
        and ready_record_before_restart["candidate_event_id"] == recovery_ready["event_id"]
        and recovery_ready["event_id"] in contract.finalized_events,
        "restart_replays_ready_receive_once": recovery_after_restart == recovery_ready
        and recovery["turn_id"] in contract.drafts
        and len(contract.r4_receive_results) == 4,
        "purpose_binding_is_consistent": all(
            (attempt.purpose == "action" and attempt.pending_roll_id is None)
            or (attempt.purpose == "declared_roll" and attempt.pending_roll_id is not None)
            for attempt in contract.attempts.values()
        ),
        "structured_roll_correction_versions": refreshed_corrected.version == 2
        and refreshed_corrected.declared_total == 18,
        "duplicate_roll_approval_same_result": approval == duplicate_approval and contract.declared_roll_commits == 1,
        "speech_path_never_mutates_world": contract.world_mutations == 0,
        "durable_attempt_has_no_raw_or_interim_fields": all(
            "raw" not in key and "provisional" not in key and "interim" not in key
            for attempt in contract.attempts.values()
            for key in attempt.durable_record()
        ),
        "audit_has_no_speech_or_audio_payload": raw_canary.decode("ascii") not in json.dumps(contract.audit, ensure_ascii=False)
        and "Осматриваю" not in json.dumps(contract.audit, ensure_ascii=False),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise AssertionError(f"probe checks failed: {failed}")

    return {
        "probe_version": 1,
        "route_under_test": "server_proxy",
        "network_or_provider_calls": 0,
        "raw_audio_files_created": 0,
        "summary": {
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            "attempts": len(contract.attempts),
            "drafts": len(contract.drafts),
            "declared_roll_commits": contract.declared_roll_commits,
            "world_mutations": contract.world_mutations,
            "late_provider_events_ignored": contract.late_provider_events,
        },
        "checks": checks,
        "route_comparison_inputs": {
            "server_proxy": {
                "browser_provider_credential": "none",
                "provider_connection_owner": "VPS",
                "audio_network_legs": ["browser_to_VPS", "VPS_to_Deepgram"],
                "authoritative_normalizer": "VPS",
            },
            "browser_direct": {
                "browser_provider_credential": "temporary_usage_write_token",
                "provider_connection_owner": "browser",
                "audio_network_legs": ["browser_to_Deepgram"],
                "authoritative_normalizer": "browser_untrusted_then_VPS_validated",
            },
        },
        "state_counts": {
            state: sum(attempt.state == state for attempt in contract.attempts.values())
            for state in ["submitted", "failed", "cancelled"]
        },
        "schema_samples": schema_samples,
        "durable_attempts": [attempt.durable_record() for attempt in contract.attempts.values()],
        "approved_roll": asdict(contract.drafts[refreshed["turn_id"]]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_probe()
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
