## Summary

The research is strong on current transport behavior, provider constraints, and repository provenance, but it is not yet decision-grade. I found no blocking crash/corruption/security error in the research itself, but six material issues could distort Phase 2 architecture selection.

The CURRENT FLOW claims are well supported. I independently verified the artifact-only quote: “A rendering exception can make a same-page reconnect skip the event whose UI side effect failed.” The cited frontend does advance `afterId` before rendering. Replay/live overlap, raw unacknowledged sends, queue eviction, and restart limitations also follow from the cited code.

The current Deepgram token/keepalive facts and ElevenLabs token, voice-path, context, and concurrency facts match current official documentation. However, the artifact overstates what `close_context` accomplishes for audible interruption.

## Findings

suggestion: [docs/tasks/377/research.md:161](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:161) — The reuse percentages have no defined denominator or scoring procedure. “How many tested behaviors in matrix A survive” is insufficient because rows have radically different sizes and importance, O3 counts “lifecycle + domain behaviors,” while O4 includes tests/fixtures/spec knowledge despite “reuse” elsewhere meaning surviving observable behavior. Consequently, 55–65%, 40–55%, and 15–25% cannot be reproduced or meaningfully compared. Replace percentages with an enumerated capability scorecard, or define a fixed weighted denominator and show each option’s arithmetic.

suggestion: [docs/tasks/377/research.md:151](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:151) — “Five semantic exchanges” mixes unlike units: STT delivery, model request/response, a human decision plus command acknowledgement, model execution, and both first and complete TTS audio. All options therefore score exactly five even though their serial network legs differ. This column cannot compare latency or topology. Separate mandatory serial gates from one-way network legs/provider request-response cycles, and distinguish TTS time-to-first-audio from completion.

suggestion: [docs/tasks/377/research.md:66](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:66) — The claimed “minimum architecture invariants” prematurely require append-only events plus checkpoints and later name O4 an “event-sourced” service. The product invariants do require durable idempotency, recovery, replayable projections, and causal turn identity; they do not establish event sourcing as the only implementation. A transactional current-state model with command deduplication and an outbox could satisfy the same observable requirements. State the required guarantees without selecting persistence architecture.

suggestion: [docs/tasks/377/research.md:103](/home/kesha/orchestra/worktrees/home-kesha-projects/dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:103) — Matrix B omits the fixed player-dice path from task #5: players physically roll, speak the result, and honesty is not verified. That creates a distinct input contract—recognize or explicitly capture a declared roll, associate it with the approved party action, allow correction, and prevent ordinary table speech from being interpreted as a roll. Add a row with failure semantics and a deterministic oracle. This omission changes the minimum transcript/approval command schema.

suggestion: [docs/tasks/377/research.md:81](/home/kesha/orchestra/worktrees/home-kesha-projects/dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:81) — Matrix A does not fully audit the reuse inventory required by task #5. `lib/entity_enhancer.py` and `lib/campaign_manager.py` were explicitly supplied for evaluation but have no capability rows; `campaign_manager` appears only in a footprint statistic. Add explicit reuse/avoid findings with dependencies, coupling, evidence, and rationale so absence is not silently interpreted as rejection.

suggestion: [docs/tasks/377/research.md:196](/home/kesha/orchestra/worktrees/home-kesha-projects/dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:196) — “Barge-in/cancel can stop only audio work” overstates the provider guarantee. ElevenLabs documents closing the generation context and starting another, but audio already delivered to the browser may remain buffered or playing. The minimum adapter therefore needs two cancellation operations: close provider generation and immediately stop/discard client playback for the affected `line_id/context_id`. Add that distinction to Matrix B and its oracle. The official guide supports five contexts and `close_context`, but not automatic cancellation of already received playback: [ElevenLabs multi-context guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/multi-context-web-socket).

suggestion: [docs/tasks/377/research.md:212](/home/kesha/orchestra/worktrees/home-kesha-projects/dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:212) — The Orchestra consequence blurs repository evidence and legal interpretation. “Modified network-service source must be offered under AGPL” is an interpretation of license application, not merely something established by copyright headers, shortlog, or absence of a CLA. Preserve the uncontested repository facts, quote or precisely summarize the relevant license condition, and leave its application to the proposed combined/private deployment unresolved. The surrounding clean-history/provenance distinctions are otherwise appropriately cautious.

question: [docs/tasks/377/research.md:113](/home/kesha/orchestra/worktrees/home-kesha-projects/dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:113) — Does “three maps” mean three tactical square-grid board candidates, three illustrative images, or three adventure/location maps later converted into boards? The current row assumes generated assets can seed the board but does not establish the required grid metadata, traversability, token spawn points, or conversion step. This product ambiguity must be closed before the map generator boundary is architecture-ready.

## Verdict

**NEEDS WORK — no blocking findings, seven material suggestions and one architecture-affecting question.**

The central conclusion—an approval-gated durable coordinator is required—is supported. The provider research is mostly current: Deepgram documents 30-second default/3,600-second maximum temporary tokens valid only at connection time and 3–5-second keepalives; ElevenLabs documents 15-minute single-use TTS tokens, voice-specific endpoints, five multi-context streams, and plan/model-specific concurrency ([Deepgram token auth](https://developers.deepgram.com/guides/fundamentals/token-based-authentication), [Deepgram keepalive](https://developers.deepgram.com/docs/audio-keep-alive), [ElevenLabs token API](https://elevenlabs.io/docs/api-reference/tokens/create), [ElevenLabs models](https://elevenlabs.io/docs/overview/models)).

Before Phase 2, the artifact should remove non-reproducible reuse percentages, replace the five-exchange pseudo-metric, avoid assuming event sourcing, add the missing player-dice and reuse-inventory rows, and specify end-to-end audio cancellation.

## Round (2026-08-16T09:51:53Z)

## Summary

All eight Round 1 findings were materially addressed. The updated matrices satisfy the required columns and product rows, the options are comparable without invented percentages, and the provider/IP corrections are appropriately scoped.

Evidence check: the artifact states, “broker subscription precedes history read.” This is verified by `broker.subscribe(campaign)` at `backend/server.py:802`, followed by `read_current_session_events()` at lines 806–809; the duplicate-handoff claim remains supported.

Two material issues remain: persistence neutrality is not carried consistently into Matrix B, and the conclusion crosses from research into Phase 2 implementation planning.

## Findings

suggestion: [docs/tasks/377/research.md:119](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:119) — Round 1 persistence finding is only partially fixed. Lines 72–75 explicitly leave event log/checkpoints versus transactional state/deduplication/outbox open, but this row still requires every persisted event to carry causal IDs and uses “rebuild state from events and compare snapshot” as the universal oracle. That selects event sourcing for canonical recovery. Make the common oracle persistence-neutral: recover identical committed state and player projection after crash; then provide alternative event-log replay and transactional-state/outbox oracles.

suggestion: [docs/tasks/377/research.md:483](/home/kesha/orchestra/worktrees/home-kesha-projects/dnd-game-master/ai-table-architecture/docs/tasks/377/research.md:483) — “The next safe step … slices one end-to-end vertical tracer” is already a Phase 2 implementation sequence. The task explicitly limits this artifact to research and forbids planning code. Retain the identified evidence gate, but move tracer sequencing and test composition to the later plan.

No new blocking or security findings. The other prior findings are **FIXED**:

- Reuse percentages removed.
- Critical-path units made explicit and topology-aware.
- Minimum invariants made persistence-neutral at the top level.
- Player-declared physical dice added.
- `campaign_manager.py` and `entity_enhancer.py` audited.
- Provider-generation cancellation separated from browser playback cancellation.
- AGPL applicability left unresolved.
- Three-map ambiguity explicitly gated.

## Verdict

**NEEDS MINOR REVISION — 0 blocking, 2 suggestions.**

Phase 1 evidence is otherwise complete and supports the minimum observable architecture without selecting O1–O4. After the two consistency/scope corrections above, the research is ready for approval.
