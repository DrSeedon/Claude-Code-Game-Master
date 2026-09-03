# R5 deterministic synthetic probe results

- Run date: 2026-08-16
- Scope: contract/state/event behavior only
- Route modeled: browser → VPS speech proxy → fake per-capture provider stream
- External network/provider calls: **0**
- Raw audio files created: **0**

## Predeclared pass/fail

Pass required all of the following in one deterministic run: every one of the 26 named checks is `true`; world mutations remain `0`; four complete inputs yield exactly four drafts; the current declared-roll sequence yields exactly one commit; rejected/disconnected/cancelled/conflicting/abnormally-closed attempts yield none; admission/R4/approval duplicates do not create another result; the complete candidate and attempt reference survive simulated restart; every published event and durable attempt validates against `protocol-schemas.json`; purpose/pending-roll-invalid samples fail schema validation; and the raw-audio canary appears in neither durable attempt metadata nor the audit stream.

Any missing/false check, schema error, non-zero network call count, raw file, world mutation, extra draft, or extra roll commit was a failure. These criteria were fixed before the final run.

## Commands and measured output

```text
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-room-input --frozen pytest -p no:cacheprovider -q docs/tasks/377/phase3/r5/test_synthetic_probe.py
...                                                                      [100%]
3 passed in 0.13s
```

Two independent process invocations produced byte-identical JSON:

```text
cmp -s /tmp/r5-probe-results-a.json /tmp/r5-probe-results-b.json
exit 0
sha256 b97629e1676909e41ccc08869535b60f75fcf57596ab60cbdb0628b1a4e29c13
```

The final contract/schema and probe hashes were:

```text
protocol-schemas.json  3378f0acca37c60ca210a952c52559f292d56eeb09d2a56c79865f34a0b74740
synthetic_probe.py      e558266e62a27f8f90bdf2096825e4b50ea22e9afbd0527be80ccf74366905f3
```

## Result summary

| Measure | Result |
|---|---:|
| attempts | 9 |
| checks passed / total | 26 / 26 |
| submitted attempts | 4 |
| failed attempts | 4 |
| cancelled attempts | 1 |
| drafts | 4 |
| world mutations before approval | 0 |
| declared-roll commits | 1 |
| late provider events ignored | 2 |
| network/provider calls | 0 |
| raw audio files | 0 |

The nine attempts and the admission-only rejection cover:

1. A non-allowlisted/cross-room actor receives `input.capture.rejected` with no attempt/capture/audio ticket; identical admission command returns its stored result.
2. PTT action: actor bound before audio; admission replayed by command identity; mutable interim rewritten; two final segments concatenated; exact duplicate ignored; Metadata plus normal close created one durably referenced candidate; repeated R4 receive returned the same draft; PTT also fenced the exact active playback context.
3. Interrupted stream: one final segment followed by provider disconnect; all partial text was discarded; the durable attempt is `failed/audio_stream_lost`; a late event was ignored.
4. Ambiguous pending roll: `У меня 17 стрел` while a roll was pending produced `failed/unrecognized_roll_declaration`, not a roll candidate or action draft.
5. Declared roll revision 6: `Бросок — 17` produced a review candidate; structured correction produced immutable version 2 with total 18; approval of version 1 failed, and approval of v2 after the pending roll advanced to revision 7 also failed.
6. Terminal race: final segment and Metadata followed by abnormal close produced `failed/provider_protocol_error` and no candidate/draft.
7. Conflicting final: the same provider segment identity with different text produced `failed/conflicting_final_segment` and no candidate/draft.
8. Cancellation: user cancel discarded provisional state, emitted `input.capture.cancelled`, and produced no candidate/draft.
9. Ready recovery: the complete `speech.finalized` event and attempt `candidate_event_id` existed before simulated restart; recovery loaded the exact event and applied `receive:{capture_id}` once; a repeated call returned the stored result.
10. Fresh declared roll revision 7: structured correction to 18 produced v2; current approval succeeded; exact duplicate approval returned the stored result and did not commit twice.

The durable attempt contains capture/actor/route/purpose/state/generation/count/provider/transcript/candidate IDs and safe error enums. The complete immutable final text and segment/authority tuple live in the separately schema-validated `speech.finalized` record referenced by `candidate_event_id`. Neither record has a raw-audio or interim-transcript field. The raw PCM canary was also absent from the in-memory audit projection. This proves the fake adapter's data-shape invariant, not absence from future process dumps or third-party infrastructure.

## Pilot defect and disposition

The first schema test incorrectly instantiated the `InputAttempt` subschema without its root `$defs`; `jsonschema` correctly failed with `PointerToNowhere: '/$defs/Identifier'`. The harness was changed to resolve `#/$defs/InputAttempt` inside the complete schema. No event schema or behavior was weakened. The final run above validates both top-level event samples and all durable attempts.

## What this experiment does not prove

- It does not measure Russian word-error rate, room echo/noise, microphone directionality, speaker distance, browser resampling, or actual `getUserMedia` settings.
- It does not emulate Deepgram's implementation; official provider documentation is the evidence for provider fields and close behavior. Real protocol conformance remains gated.
- It does not measure browser-direct or proxy latency, VPS bandwidth, WebSocket backpressure, handshake failure rates, or cross-browser behavior.
- It does not prove raw audio is absent from future reverse-proxy/APM/crash-dump configuration; release inspection must test those consumers explicitly.
- It models admission/R4 idempotency, the atomic ready record pair and restart behavior in memory, but does not exercise the future private repository, actual database transaction/process restart, or projection reducer.

Those gaps are intentional: real provider/room calls require separate authorization, recorded participant consent, and frozen measurement thresholds.
