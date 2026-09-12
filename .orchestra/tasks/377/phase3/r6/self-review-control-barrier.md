# R6 adversarial self-review — control barrier closure

Date: 2026-08-16  
Scope: only the second-round media-before-control ordering blocker and telemetry required-field suggestion  
Independence: none; author self-review after the model-review ceiling

**Review status: Sol Round 2 NEEDS WORK before orchestrator-directed fix; no fresh model verdict due prose ceiling.**

The orchestrator selected the strict barrier rather than media-triggered atomic clear: only authenticated control/stop/snapshot may advance client `applied_control_fence`; media never advances it; playable media requires equality.

## Load-bearing invariants checked

1. A next-fence media handler cannot start/mark/fetch/decode speech, music, or SFX. It can only add an envelope/chunk to the bounded `future_control_wait` queue.
2. Receiving next-fence media does not clear or alter old current-fence media.
3. The control reducer closes admission, clears its scope, observes old lanes empty, commits the new applied fence, and only then drains exact-fence/current-lease media.
4. A stale media fence is dropped. A gap, timeout, or queue bound failure drops the entire future queue and requests a control snapshot without changing the applied fence.
5. Telemetry rows require the content HMAC/key ID, retention policy, and deletion disposition, while unknown/plaintext/unkeyed content fields are rejected.

The contract statement inspected is: “No speech, chunk, SFX, or music handler may change it.” The fake implements media admission in `_media_gate` and fence advance only in `apply_control`.

## Adversarial cases and evidence

| Case | Attack order | Required observation | Recorded observation |
|---|---|---|---|
| Reordered all lanes | old fence N speech + music + SFX active → new N+1 speech + music + SFX → N+1 `all_audio` | no new event applied; all old lanes remain until control | `future_media_buffered_before_control=3`; `new_media_started_before_control=false`; `old_media_preserved_before_control=true` |
| Atomic barrier | same trace, then apply N+1 control | old sources empty before drain; only N+1 media active afterward; no pending media | `old_cleared_before_drain=true`; `old_media_absent_after_control=true`; `new_media_admitted_after_control=true`; `pending_after_control=0` |
| Bounded wait | queue 17 next-fence SFX envelopes with max 16 | overflow discards future queue, requests recovery, leaves current state/fence unchanged | `overflow_gap_requests=1`; `overflow_pending_after_gap=0`; `overflow_old_music_preserved="danger"`; applied fence remains `0` in the focused test |
| Stale former leader | re-elect with old music/SFX, then send old lease/fence media | old lanes clear; stale events silent; successor reconstructs music only | old leader `music="silence"`, SFX count `0`; stale music/SFX accepted `false`; new leader music `danger`, old SFX replay `0` |
| Missing telemetry authority | remove `retention_policy_id`; inject `text`, `text_sha256`, or unknown `content_fingerprint` | row rejected | `telemetry_required_missing` / `telemetry_schema_rejected`; complete rows validate |

Exact command:

```bash
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output --frozen python -m unittest discover -s docs/tasks/377/phase3/r6 -p 'test_audio_routing_probe.py' -v
```

Result: `Ran 16 tests in 0.004s` and `OK`. The separately executed probe matches `probe-results.json` byte-for-byte.

## Attempts to falsify the closure

- **Can higher media advance the fence?** No fake media method assigns `audio_fence`; `_media_gate` returns `buffered` for exactly N+1 and `rejected` for a larger gap.
- **Can queued media set its event dedupe marker early?** No; `_media_gate` checks the pending ID but `_activate_*` alone adds it to `applied_events`, after control drain.
- **Can the control publish N+1 before clearing N?** In the fake, `_clear_all`/`_clear_speech` and the recorded empty-lane observation occur before `self.audio_fence = audio_fence`; drain follows that assignment in the same synchronous call.
- **Can a queued old-lease event drain after election?** No; drain rechecks the exact current lease generation and drops a mismatch.
- **Can queue overflow leave a valid-looking partial prefix?** No; `_request_control_gap` clears the whole pending queue.
- **Can a row omit retention/deletion identity yet pass?** No; `METRIC_REQUIRED_FIELDS <= set(row) <= METRIC_FIELDS` is required.

## Counter-evidence and remaining gates

- Python call atomicity does not prove browser/AudioWorklet scheduling. I6 must keep clear → fence commit → drain in one synchronous reducer transition with no `await`, callback, media fetch, or node start between those steps.
- The fake exercises event-count overflow but not a real monotonic 250 ms timeout, wire byte accounting, or AudioWorklet/decoder memory. Production-shaped browser tests must cover all three bounds.
- The fake's `48 bytes/ms` estimate models 24 kHz mono S16LE only. The wire adapter must validate actual retained bytes and discard the whole queue on mismatch/overflow.
- Logical source clearing does not prove last physical audible sample; G2 speaker-to-loopback evidence remains required.
- No independent model assessed the orchestrator-directed patch after the ceiling. The previous Sol verdict must not be described as approved.

## Self-verdict

**The selected contract and synthetic oracle close the documented ordering race at the logical state-machine level.** The result is suitable for Phase-2 planning with the implementation/browser falsification gates above. This is an author self-verdict, not a fresh model verdict and not physical-audio evidence.
