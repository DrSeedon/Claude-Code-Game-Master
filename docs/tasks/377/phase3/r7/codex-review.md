# R7 Sol review record

## Gate inputs

- Route: mandatory Sol technical review (`codex_review`) because the artifacts fix authentication/capability, secret projection, shared delivery/cursor and external schema/protocol contracts.
- Author runtime: Orchestra Codex runtime; no versioned model ID was exposed.
- Changed consumers: research files in this directory; future consumers are I1/I3/I8 server transport/projection and browser reducers.
- Exact AC: R7 ticket in `docs/tasks/377/plan.md:172-182` and the oracle in `surface-contract.md`.
- Mechanical check after self-review fixes: `uv run --active --frozen --no-sync pytest -q docs/tasks/377/phase3/r7/test_surface_protocol_probe.py` → `10 passed in 0.54s`.
- Independent oracle status: the synthetic oracle was authored during this research, so it is evidence but not an independent pre-existing gate.

## Attempt journal

1. **No reviewer response; no round consumed.** Wrapper rejected the request as `invalid_argument: context must include caller-supplied task instructions and PROJECT CONTEXT`. The next request supplied both blocks.
2. **No reviewer response; no round consumed.** Corrected request was blocked before reviewer start: `weekly_quota_unknown: New Codex worker turn blocked: weekly quota status for gpt-5.6-sol is unavailable or stale (FileNotFoundError ...)`.

3. **No reviewer response; no round consumed.** The final corrected request, made after material artifact fixes, was blocked by the same `weekly_quota_unknown` / missing quota-status file error.

The tool-attempt ceiling is exhausted. Per the review skill, no fourth launch is allowed. There is **no Sol verdict** and the review route is recorded as unavailable; the checks below are adversarial author self-review, not a substitute independent verdict.

## Adversarial self-review after unavailable route

| Finding | Verification | Resolution |
|---|---|---|
| **blocking (found/fixed): composite reducer could visibly commit table before scene.** | The original generic `Client.receive_projection` committed each snapshot immediately; the final-only assertion could not prove atomic panes. | Added per-batch staging, equal aggregate/world boundary check, a single two-surface commit, and assertions that state/cursors remain empty after the first half. |
| **blocking (found/fixed): public transport schema omitted actor selection and draft submit/approve/reject.** | `transport-schemas.json` originally began at `client.hello`/projection ack, leaving table authority messages prose-only. | Added four closed messages; approval accepts only envelope kind/version plus `turn_id`, `draft_version`, and nonce. A test proves an injected `room_id` is rejected. |
| **blocking (found/fixed): projection ack allowed mismatched `surface` and projection schema.** | The original enums independently allowed `surface=table` with `admin.v1`. | Added conditional const binding and a mechanical rejection assertion. Server session authorization remains mandatory. |
| **blocking (found/fixed): consumed/stale draft card schema required a reusable nonce string.** | `DraftCard` required `approval_nonce` for every approval state. | Awaiting approval requires a string; approved/rejected/stale requires `null`. |
| **suggestion (accepted): admin health should mechanically contain table, scene, admin once each.** | Original array had exactly three items but permitted three rows for one surface. | Ordered `prefixItems` now require table, scene, admin and forbid extras. |
| **suggestion (accepted): overlay probe shape differed from transport schema and ticket replay lacked audit evidence.** | Probe used coordinate arrays and different field names; replay raised without an audit row. | Aligned point/object and field names; added hashed replay denial audit plus protected-fingerprint assertion. |
| **open limitation, non-blocking for research:** logical lease uniqueness does not by itself prove physical no-echo after a partition with buffered media. | The harness fences server authorization/generation, not an actual crashed browser/audio device. | Contract caps buffer at 250 ms, uses conservative stop/not-before guards and fails silent when clock uncertainty is unbounded. I8 real-browser/room testing remains mandatory; `surface-contract.md` labels physical no-echo LIKELY, not CONFIRMED. |

## Route outcome

- Review route: mandatory Sol technical review, unavailable after 3 tool attempts.
- Rounds: 0; no reviewer response occurred.
- Verdict: **no model verdict — route unavailable**.
- Mechanical evidence: JSON schemas pass Draft 2020-12 meta-validation and adversarial samples; `10 passed in 0.54s`.
- Independence: `cross-family verdict unavailable`; the self-review above is same-author evidence only.
