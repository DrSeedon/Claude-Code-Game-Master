# #377 — AI-стол: Phase 2 plan к 60–90-минутному MVP

**Статус:** Phase 2; только планирование

**Источник правды:** docs/tasks/377/mvp-product-spec.ru.md

**Поддерживающие доказательства:** docs/tasks/377/research.md и docs/tasks/377/codex-review-research.md
**Не разрешено этим планом:** создавать приватную репу, писать runtime-код, вызывать платные API, менять VPS/production/systemd/nginx/DNS или начинать Phase 3 без отдельного APPROVE PHASE 3.

Если старые product/research-варианты расходятся с канонической спецификацией, применяются решения владельца из mvp-product-spec.ru.md: удалённый authoritative VPS, три браузерные поверхности, один общий микрофон без speaker identification, авторские карты вместо генератора трёх карт, чистая история новой приватной репы, side phases вместо строгой индивидуальной инициативы как обратимый MVP-эксперимент.

## 1. Цель плана

Доказать и затем собрать один тонкий сквозной путь:

1. игрок явно вызывает мастера;
2. система получает final transcript и создаёт версионированную action card;
3. до подтверждения мир не меняется;
4. после подтверждения remote authority ровно один раз применяет typed game commands;
5. table, scene и admin получают согласованные, но разные безопасные проекции;
6. обычная тактика детерминирована, необычное действие ограничено typed tools;
7. authored story graph сохраняет правду мира и последствия;
8. side-phase бой показывает открытые броски мира;
9. Северин Кроу, NPC voice routing, cached lines, SFX и музыка дают подачу без LLM на каждом клике;
10. из этих срезов собирается оригинальная 60–90-минутная игра и проверяется в комнате.

План не выбирает заранее ответы, которые канонический документ оставил research-команде. Каждый такой ответ имеет отдельного decision owner, необходимое доказательство и falsification gate.

## 2. Владение решениями

| класс решения | decision owner | когда подключается владелец продукта |
|---|---|---|
| зафиксированное продуктовое решение | каноническая спецификация; команда не меняет | только если evidence открывает дорогую, scope-defining или труднообратимую развилку |
| durable backend, transport, provider route, UI mechanics | technical lead соответствующего трека | не подключается для обратимых/измеряемых выборов |
| tactical rules, side-phase start/tie-break/balance | game-systems lead | не подключается; side phases уже одобрены как обратимый эксперимент |
| story graph и authored slice | narrative/game-design lead в границах канона | только если нужно изменить 60–90-минутный scope или основную продуктовую гипотезу |
| IP, SRD, код/ассеты/голоса | technical lead совместно с qualified IP/legal reviewer | только для отдельного письменного разрешения или принятия юридического риска |
| external provider spend/data transfer | experiment lead получает отдельное письменное разрешение у budget/data authority; согласие участников даёт каждый записываемый участник | это operational authority, не пересмотр продуктового scope |
| playtest verdict | product-experiment lead по критерию из спецификации | владелец решает только дальнейшее развитие после получения результата |

На Phase 2 нет блокирующих owner questions.

## 3. Общие границы

### 3.1. License / provenance

- Новая репа имеет чистую историю, но не считается clean-room автоматически.
- Default для DnD и Orchestra — independently implement behavioral contracts.
- Любой literal source/test/doc/asset transfer требует строки в transfer manifest: source path/commit, author/provenance, governing license or written grant, dependency closure, allowed action.
- Неясное право означает avoid/rewrite, а не «скопировать пока».
- SRD 5.1 против 5.2.1, D&D branding, third-party maps, voices, music and SFX закрывает R8/R3 до включения соответствующего материала.

### 3.2. Privacy / secrets

- Long-lived Deepgram/ElevenLabs/model credentials только server-side.
- Browser получает только scoped short-lived credentials, если R5/R6 выберут browser-direct path.
- Raw room audio, voice enrollment, campaign secrets, production DB/logs и provider profiles не коммитятся.
- Любой room recording требует явного consent, срока хранения и удаления; предпочтительный oracle использует synthetic event/audio fixtures.
- Table/scene получают allowlisted player-safe projection; admin — отдельную authenticated operational projection только со стадией хода, техническими ошибками и recovery controls, но без world secrets.
- World secrets не входят в browser cache, TTS text, image prompts или client-visible replay до explicit reveal.

### 3.3. Infrastructure

- Remote VPS authority — продуктовый инвариант, не research-вариант.
- Этот Phase 2 не создаёт репу и не меняет VPS.
- Даже APPROVE PHASE 3 не означает deploy authority. I8 требует отдельного явного APPROVE STAGING и изолированного non-production service/domain/database.
- APPROVE PHASE 3 также не разрешает платные API-вызовы или передачу комнатной речи внешнему провайдеру. Любой настоящий Deepgram/ElevenLabs experiment требует отдельного `APPROVE EXTERNAL PROVIDER EXPERIMENT`; речь людей дополнительно требует зафиксированного room consent. До этих gates допустимы только official protocol evidence, fake transports и prerecorded synthetic/cleared fixtures.
- В этом плане нет production deployment ticket.

### 3.4. Oracle materialization constraint

Оркестратор явно разрешил в Phase 2 только plan.md и review artifact, а целевая приватная репа ещё не существует. Поэтому executable RED tests сейчас физически не создаются. Это не разрешение реализовывать без oracle:

- каждый implementation ticket ниже называет будущий immutable RED command и точные assertions;
- после I0 каждый implementation ticket начинается с отдельного oracle-only commit;
- named command обязан завершиться non-zero из-за отсутствующего поведения, не ImportError/collection error;
- executor не получает ticket до независимой проверки RED;
- test/fixture/config неизменяемы в рамках одной implementation attempt и не могут подгоняться под её результат;
- если RED нельзя материализовать как описано, ticket возвращается в planning closure и implementation не начинается.

Если независимая проверка доказывает, что сам oracle ошибочен или неоднозначен, текущая implementation attempt останавливается. Замена допустима только отдельным документированным oracle-only commit после независимого review и нового подтверждённого RED; старую implementation attempt нельзя продолжать или использовать как evidence для новой.

Research tickets имеют delivery/experiment oracles: их результат — decision artifact и воспроизводимое измерение, а не runtime behavior.

## 4. Dependency graph и thin integration path

Легенда: R — research/experiment, I — implementation. Стрелка означает blocked-by.

    R8 private/IP ───────────────→ I0 clean private repo
        ├→ R1 narrative ───────────────┐
        ├→ R2 typed effects → R3 rules ├→ R9 authored slice research
        └→ R3 SRD/IP                   │
    R4 durable coordinator → R7 surfaces → I1 text-only durable tracer
                           ├→ R5 one-mic ─→ I2 voice + physical roll
                           └→ R6 audio  ──────────────────────────────┐
    I0 + R9 ─────────────────────→ I9 authored package               │
    I1 + R2 + R3 ───────────────→ I3 tactical + unusual action       │
    I1 + R1 + I9 ───────────────→ I4 story/NPC scene                 │
    I3 + R3 + I9 ───────────────→ I5 side-phase combat               │
    I2 + I4 + I5 + I9 + R6 ─────→ I6 Severin/voice/SFX/music         │
    I4 + I5 + I6 + I9 ──────────→ I7 polished slice                  │
    I7 + APPROVE STAGING ────────→ I8 remote room rehearsal          │
    I8 ──────────────────────────→ R10 product/side-phase playtest ←─┘

Допустимая параллельность:

- после R8 могут параллельно идти R1 и R2;
- R4 может идти параллельно R8, потому что выбирает observable persistence contract без переноса кода;
- после R4 могут параллельно идти R7 и подготовка fake-provider failure matrix;
- после I0/R4/R7 и отдельных external-provider gates могут параллельно идти R5 и R6;
- после I0/R9 можно собирать I9 параллельно I1–I3;
- I3 и I4 могут идти параллельно только если не делят schema/projection files; иначе сериализуются.

## 5. Research tickets — десять load-bearing tracks

### R8 — Private repo, IP route и security baseline

- **Type:** RESEARCH / legal-provenance decision.
- **Question:** что можно независимо реализовать, что можно перенести literal, какой SRD/branding/asset/voice material разрешён, и какие host/access/secret guarantees обязательны до первого commit новой репы?
- **Decision owner:** technical lead + qualified IP/legal reviewer. При отсутствии доказанного права автоматически выбирается behavioral rewrite.
- **Artifacts:** docs/tasks/377/phase3/r8-ip-route.md; docs/tasks/377/phase3/r8-transfer-manifest.tsv; docs/tasks/377/phase3/r8-repo-security-baseline.md; r8-remote-authority-threat-model.md.
- **Required evidence:** current DnD/Orchestra licenses and file-add history; dependency closure для каждого candidate; official SRD 5.1/5.2.1 license texts; written grants if any; hosting private-visibility/access evidence; art/audio/voice terms; secret/data exclusion scan; threat cases for surface/actor spoofing, cross-room access, expired/replayed token, table→admin escalation and direct command submission around approval.
- **Delivery oracle:** каждая reuse-кандидатура имеет source/commit/license/owner/dependencies/action/reviewer; строки без доказанного action помечены avoid; baseline содержит clean-history, branch/access, secret scanning, backup and incident ownership; threat model maps every named attack to fail-closed authentication, authorization, audit and negative test oracle.
- **Stop/falsification:** unclear ownership, missing dependency license или несовместимый network/source obligation → literal transfer запрещён. Невозможность очистить один candidate не блокирует MVP: он переписывается behaviorally.
- **License/privacy boundary:** ни одного source file, test, campaign data, key, raw audio или generated binary не переносить во время исследования.
- **AC:** decision artifact выбирает один executable IP route для I0 и отдельный route для SRD/content/audio; transfer manifest fail-closed.
- **blocked-by:** none.
- **Blocks:** I0; literal reuse в R2; SRD decision в R3; voice/assets/content routes в R6/R9/I9.

### R4 — Durable approval coordinator и recovery semantics

- **Type:** RESEARCH / architecture experiment.
- **Question:** event log + checkpoints или transactional state + dedupe + outbox лучше обеспечивает один accepted command → одну world mutation → replayable projections при crash/reconnect/late events?
- **Decision owner:** backend/reliability lead.
- **Artifacts:** docs/tasks/377/phase3/r4-coordinator-adr.md; r4-state-machine.md; r4-command-event-schemas.json; r4-fault-matrix.md; reproducible scratch probes outside production.
- **Required evidence:** fault injection на receive, draft persist, approval, execution start, world commit, outbox publish, projection ack and audio enqueue; duplicate/out-of-order commands; stale draft; server restart; replay/live overlap; secret projection failure.
- **Experiment oracle:** обе кандидатные модели оцениваются одним harness. Common pass condition: после каждого crash/reload committed world и table projection идентичны expected; duplicate command возвращает stored result; world mutation count = 1; uncommitted stage явно recoverable.
- **Stop/falsification:** кандидат, требующий distributed transaction между provider/browser/world, silently skipping corrupt state или replaying whole turn after unknown commit, исключается. Если ни один кандидат не проходит, coordinator scope уменьшается до single authoritative DB transaction + outbox и эксперимент повторяется.
- **License/privacy boundary:** probes содержат synthetic state; Orchestra — prior art only до R8 clearance; secrets replaced with canaries.
- **AC:** выбран persistence model; зафиксированы state transitions, command/event IDs, ack semantics, recovery actions и exactly-once observable contract.
- **blocked-by:** none.
- **Blocks:** R7, R5, R6, I1.

### R1 — Narrative director и authored story graph

- **Type:** RESEARCH / narrative-system experiment.
- **Question:** какой минимальный graph сохраняет immutable truth, clues, NPC goals, threats, consequences and endings, но позволяет AI переносить hooks без invisible walls?
- **Decision owner:** narrative/game-design lead; schema constraints совместно с game-kernel lead.
- **Artifacts:** docs/tasks/377/phase3/r1-narrative-director.md; sanitized story-graph schema; adversarial scenario fixtures; evaluation rubric.
- **Required evidence:** primary/open/licensed narrative-design sources; не менее трёх adversarial traces (игроки сожгли tavern, пропустили clue, убили ключевого NPC/ушли из location); model and deterministic-director comparison; invariant checks for killer/motive/secret/dead NPC/threat clock.
- **Experiment oracle:** one seed + same accepted actions reproduce canonical facts and consequence clock; different prose may vary, immutable facts may not; player projection never exposes unrevealed secret; each mandatory clue has an authored alternative delivery route.
- **Stop/falsification:** если free-form model регулярно меняет truth или требует линейного teleport, уменьшается зона AI improvisation и transitions становятся explicit; не расширять campaign scope.
- **License/privacy boundary:** не копировать closed adventures/actual-play text; artifacts до I0 только abstract/sanitized; proprietary campaign content появляется только в I9 внутри private repo.
- **AC:** выбран schema/director boundary, набор invariants, author workflow и falsification cases для R9/I4.
- **blocked-by:** R8 for source/material policy.
- **Blocks:** R9, I4.

### R2 — World state и typed AI game tools

- **Type:** RESEARCH / contract extraction experiment.
- **Question:** какие behavioral contracts нужны для move, damage, create_effect, change_terrain, spawn, remove, reveal; можно ли узко переиспользовать WorldRepository/dice behavior или дешевле независимо реализовать kernel?
- **Decision owner:** game-kernel architect; reuse action подтверждает R8 reviewer.
- **Artifacts:** docs/tasks/377/phase3/r2-kernel-adr.md; typed-command-schema-v1.json; state/projection model; compatibility matrix current DnD vs required behavior; seeded fixtures.
- **Required evidence:** current WorldRepository/WorldGraph/dice source and tests; import/coupling graph; atomicity and idempotency probes; invalid reference/range/secret/duplicate cases; command-to-domain-event mapping.
- **Experiment oracle:** одинаковый fixture и command sequence дают byte-equivalent canonical state/player projection; invalid or unauthorized command has zero mutation; duplicate command has one result; reveal is the only path moving secret data to player projection.
- **Stop/falsification:** importing active-campaign/CLI/module/global-state coupling или unclear license → no literal extraction; implement contract independently. Если seven-command vocabulary не выражает authored scenario, расширять schema только на named semantic primitive, не давать arbitrary patch/Bash/SQL.
- **License/privacy boundary:** no world-state/source PDFs; secret canaries in fixtures; literal code only after manifest clearance.
- **AC:** v1 command vocabulary, validation order, versioning, event/result schema and reuse/rewrite decision are closed.
- **blocked-by:** R8.
- **Blocks:** R3, I3, R9.

### R7 — Three synchronized browser surfaces

- **Type:** RESEARCH / UX-transport contract.
- **Question:** какой projection/WebSocket/Pointer Events contract удерживает table, scene, operational admin and composite fallback согласованными при reconnect, не выдаёт secrets, авторизует room/surface/actor capabilities, поддерживает ephemeral planning overlays и выбирает ровно одного audio leader?
- **Decision owner:** frontend/UX lead + backend projection owner.
- **Artifacts:** docs/tasks/377/phase3/r7-surface-contract.md; projection allowlists; wireflows for table/scene/admin/composite; reconnect/cursor protocol; Pointer Events device matrix.
- **Required evidence:** three-client prototype with fake events; duplicate/drop/reorder/reconnect; render exception; table touch and ordinary mouse; fullscreen; one-screen fallback; canary secret; audio-leader loss/re-election; negative room/surface/actor capability cases from R8; start/pause/end, diagnostics, volume, cancel and reproject admin wireflows; arrow/marker overlay TTL and reconnect behavior.
- **Experiment oracle:** three clients converge to one aggregate version; replay/live duplicate renders once; cursor advances only after reducer success; no browser projection, including admin, receives unrevealed world-secret canary; unauthorized room/surface/actor actions fail with zero mutation; admin action/diagnostic fields are minimal, authenticated and audited; an overlay reconnects within its TTL, expires deterministically and never changes canonical world state; exactly one client owns playback.
- **Stop/falsification:** protocol relying on in-memory cursor/content dedupe or CSS hiding secrets is rejected. Touch-specific UI that cannot operate with mouse violates product decision.
- **License/privacy boundary:** no current frontend wholesale copy; concept PNGs are view-only references, not assets; admin browser receives operational metadata only and never gains world-secret visibility by role.
- **AC:** event/projection schemas, fail-closed capability matrix, reconnect handshake, admin controls, overlay TTL, leader semantics and interaction contract are fixed for I1/I3/I8.
- **blocked-by:** R4.
- **Blocks:** R5, R6, I1.

### R3 — Tactical engine, SRD boundary и side-phase experiment design

- **Type:** RESEARCH / rules and game-systems experiment.
- **Question:** какой minimum rules subset covers grid/movement/LOS/action economy/abilities/states/death for six level-3 heroes, какой SRD route lawful, какие явные параметры различают story/normal/hard modes без скрытого изменения бросков, и какие side-phase rules preserve tempo without unacceptable alpha strike?
- **Decision owner:** game-systems lead; SRD/license jointly with R8 reviewer.
- **Artifacts:** docs/tasks/377/phase3/r3-rules-adr.md; rules-manifest with provenance; deterministic combat fixtures; side-phase experiment protocol; classic-initiative fallback mapping.
- **Required evidence:** official SRD 5.1 and 5.2.1 texts/licenses; current dice tests only as behavioral evidence; deterministic grid/LOS/resource fixtures for all three difficulty presets; matched encounter simulation/dry runs under side phases and classic initiative; thresholds for phase duration, participation, focus fire and first-side advantage written before results.
- **Experiment oracle:** seeded combat yields exact legal cells, resources, recorded rolls, damage, death saves and states; each difficulty preset changes only its declared pre-roll parameters and never rewrites an already generated/physical roll; each hero acts at most once per player phase; world phase is deterministic given chosen AI actions; switch to classic ordering changes scheduler only, not command/state schema or committed roll facts.
- **Stop/falsification:** unclear SRD right → use independently specified D&D-like subset; side phases showing unacceptable alpha strike, exclusion of players or long optimization by predeclared thresholds → activate classic fallback, as owner already authorized.
- **License/privacy boundary:** no full rulebooks/closed class text/branding; only cleared rules manifest enters private repo.
- **AC:** rules subset, six-hero capability budget, three difficulty preset semantics, side-phase start/tie-break/duration semantics, effect-duration mapping and fallback are engineering-closed.
- **blocked-by:** R2, R8.
- **Blocks:** R9, I3, I5.

### R5 — One-mic browser capture, Master button и speech path

- **Type:** RESEARCH / real-room experiment.
- **Question:** browser-direct short-token stream или server proxy надёжнее для one-mic push-to-talk, final transcript, character binding and physical-roll declaration; нужен ли wake-word в MVP?
- **Decision owner:** audio/frontend lead with security review.
- **Artifacts:** private-repo docs/experiments/r5-room-audio-protocol.md; sanitized results; data-flow/security decision; synthetic Deepgram event fixtures. Raw recordings stay outside git and are deleted per consent.
- **Required evidence:** official protocol and prerecorded synthetic/cleared fixtures first; only after `APPROVE EXTERNAL PROVIDER EXPERIMENT` and room consent — actual room/browser/mic/network, 3–5 participants without identity diarization, noise/echo/silence, reconnect, interim rewrite/finality, ambiguous numbers, browser-direct and proxy comparison, short-token refresh; predeclared numeric thresholds before observing results.
- **Experiment oracle:** button binds character before capture; only final utterance creates draft; normal speech creates none; pending_roll accepts explicit declaration and rejects «17 arrows»; reconnect never auto-submits partial; long-lived key absent from browser/network logs.
- **Stop/falsification:** wake-word false activation/miss or complexity exceeds predeclared gate → omit wake-word; browser-direct instability/security failure → proxy; both paths fail → typed admin fallback preserves demo while audio track remains blocked.
- **License/privacy boundary:** informed consent, no voice identity model, no raw audio in repo/logs, no key output, provider retention documented.
- **AC:** selected capture/transport path, codec/finality/reconnect/token contract, wake-word yes/no and privacy policy.
- **blocked-by:** I0, R4, R7, R8; real-provider leg additionally requires `APPROVE EXTERNAL PROVIDER EXPERIMENT` and room consent.
- **Blocks:** I2.

### R6 — ElevenLabs, cached lines, SFX/music и audible cancel

- **Type:** RESEARCH / audio-routing experiment.
- **Question:** как детерминированно маршрутизировать Severin/NPC voices, cached combat reactions, SFX and music state; как обеспечить cancel, late-chunk discard and text-only degradation?
- **Decision owner:** audio director + backend/audio engineer; license review through R8.
- **Artifacts:** private-repo docs/experiments/r6-audio-routing.md; speech_line/audio event schema; voice roster; licensed asset manifest; cache policy; browser playback state machine.
- **Required evidence:** current official ElevenLabs protocol and fake/prerecorded traces first; controlled real-provider traces, TTS TTFA/completion and context close only after `APPROVE EXTERNAL PROVIDER EXPERIMENT`; per-voice connection limits; client buffer stop; one audio leader; pre-baked line repetition audit; voice/SFX/music rights.
- **Experiment oracle:** voice registry maps same entity deterministically; missing voice takes configured fallback; cancel closes provider context and stops/discards current/queued/late chunks by line_id/context_id; retry audio never calls kernel; ordinary hit/miss path works with provider offline.
- **Stop/falsification:** dynamic TTS/voice concurrency cannot meet team-owned threshold → serialize or pre-bake; provider unavailable → cached/text-only; unclear voice/asset rights → substitute cleared material.
- **License/privacy boundary:** only disclosed text goes to TTS; no world secrets; no cloning/enrollment without consent and rights; keys server-only.
- **AC:** routing, caching, pool-size policy, interruption and degradation decisions fixed for I6.
- **blocked-by:** I0, R4, R7, R8; real-provider leg additionally requires `APPROVE EXTERNAL PROVIDER EXPERIMENT`.
- **Blocks:** I6, I7.

### R9 — Original authored slice: content contract and dry-run protocol

- **Type:** RESEARCH / content format, timing and balance decision; not production content implementation.
- **Question:** какой content contract, beat budget, reachability model, encounter budget and provenance gate позволят original story graph, maps, six heroes, NPC roster, trap, battle, boss and continuation hook fit 60–90 minutes without content sprawl?
- **Decision owner:** narrative/content lead; combat balance by game-systems lead; asset provenance by R8 reviewer.
- **Artifacts:** docs/tasks/377/phase3/r9-content-contract.md; abstract/sanitized beat graph; timing and encounter-budget workbook; map/hero/NPC/voice/combat-line acceptance templates; provenance checklist; dry-run protocol. Actual maps, heroes, lines and campaign package belong to I9.
- **Required evidence:** R1 invariants; R2 commands; R3 rules and difficulty presets; original/licensed content audit method; deterministic reachability/secret checks over abstract fixtures; timing table reads; encounter simulations for 3–5 players; a defined persistent consequence/continuation-hook contract.
- **Delivery/experiment oracle:** abstract schema validates; required beats fit the predeclared 60–90-minute budget on paper/table read; every mandatory clue has an alternative route; synthetic secret canaries remain absent from player templates; every future asset/content class has a provenance acceptance rule; contract covers selection→NPC→choice→trap/research→physical roll→combat→boss→persistent consequence.
- **Stop/falsification:** beat budget exceeds 90 minutes or depends on unsupported mechanic → cut/rewrite the content contract, not expand MVP; abstract graph cannot survive adversarial path → fix R1/R9 before authoring production content.
- **License/privacy boundary:** research uses abstract/sanitized placeholders only; no copied closed adventure, proprietary campaign draft, third-party image/audio or generated binary enters the current public repo.
- **AC:** implementation-ready content contract, timing/balance envelope, acceptance templates and RED assertions for I9; no production campaign package created by R9.
- **blocked-by:** R1, R2, R3, R8.
- **Blocks:** I9.

### R10 — Room playtest и product/side-phase verdict

- **Type:** RESEARCH / human experiment; final MVP evidence gate.
- **Question:** вызывает ли slice желание назначить продолжение; создают ли Severin, story, shared tactics and side phases participation rather than boredom/alpha-strike/queueing?
- **Decision owner:** product-experiment lead applies canonical criterion; game-systems lead decides side-phase keep/revert; owner receives result for post-MVP direction.
- **Artifacts:** private-repo docs/experiments/r10-protocol.md written before play; consent form; sanitized session observations; side-phase/classic comparison; r10-verdict.md. No raw audio/video in git.
- **Required evidence:** one technical rehearsal plus a target of 2–3 complete room sessions; one valid complete session is the minimum evidence for the canonical first-play criterion, while fewer than two sessions lowers confidence and must be reported rather than waived; participant actions/speaking contribution, phase duration, phone disengagement, remembered NPC/consequences, explicit request for next date; standardized side-phase encounter compared with classic fallback; failures and interruptions included.
- **Experiment oracle:** primary criterion is recorded verbatim before play and not changed post hoc; every participant outcome and missing datum is reported; side-phase thresholds from R3 are evaluated; technical failures are separated from content/soul/repetition failures.
- **Stop/falsification:** missing consent/incomplete slice/administrator acting as DM invalidates session; no spontaneous continuation intent falsifies current MVP product hypothesis and blocks feature expansion; side-phase-only failure triggers scheduler revert, not product redesign.
- **License/privacy boundary:** pseudonymous notes, minimum retention, no raw speech, no world/provider secrets.
- **AC:** evidence-backed product verdict and separate side-phase verdict; limitations/counter-evidence explicit.
- **blocked-by:** I8.
- **Blocks:** MVP completion claim.

## 6. Implementation tickets — vertical demonstrable slices

### I0 — Bootstrap the clean private repository

- **Type:** IMPLEMENTATION / delivery; no product behavior.
- **Decision/delivery owner:** repo/platform lead исполняет закрытый R8 route; новые IP/product решения внутри ticket запрещены.
- **Outcome:** an empty private repo with clean history, approved license/provenance baseline, secret exclusions and test runner; no current application code copied.
- **Files (future repo, relative):** README.md; license/rights notice selected by R8; pyproject.toml; .gitignore; docs/provenance.md; docs/decisions/; tests/delivery/test_repo_boundary.py; CI secret/provenance checks.
- **Delivery oracle (materialize only after APPROVE PHASE 3):** test_i0_private_clean_history_and_exclusions verifies private remote metadata, one authorized initial history root, required ignored secret/data patterns, no forbidden source paths/hashes, and passing empty test runner.
- **Required evidence:** R8 signed decision + transfer manifest; repo access list; initial commit file manifest; secret scan output.
- **AC:** named delivery command green; repo private; clean status; no code/data transfer outside manifest.
- **Stop/falsification:** R8 unresolved, remote not verifiably private, secret scanner unavailable, or a public-repo file appears without cleared manifest → stop before initial product commit.
- **License/privacy boundary:** strongest gate; no source/tests/assets/world state copied by convenience.
- **blocked-by:** R8 and APPROVE PHASE 3.

### I9 — Author the original campaign package behind the content oracle

- **Type:** IMPLEMENTATION / original content delivery, not research.
- **Decision/delivery owner:** narrative/content lead implements the closed R9 contract; game-systems and provenance reviewers accept their respective manifests.
- **Outcome:** the private repo receives the authored top-down maps, six level-3 heroes, story graph, NPC/voice roster, trap, battle, boss, combat-line pools and continuation consequence needed by the slice.
- **Files (future private repo):** campaigns/mvp/; assets/maps/manifest.*; assets/audio/manifest.*; tests/content/test_i9_campaign_package.py; docs/content/provenance.md.
- **RED oracle (future immutable):** uv run pytest -q tests/content/test_i9_campaign_package.py::test_i9_campaign_package_is_complete_reachable_secret_safe_and_cleared.
- **RED assertions:** exactly six selectable level-3 heroes; authored grid maps contain collision/LOS/spawn metadata; every required clue/finale/recovery path is reachable; player assets contain no secret canary; difficulty fixtures cover 3–5 players; voice/combat-line pools have deterministic entity/event keys; every non-original asset has an accepted manifest row.
- **Required evidence:** closed R9 contract; R8 provenance route; authored package diff; schema/reachability/balance output; facilitator-free timing dry run.
- **Delivery oracle:** dry run exercises all required beats in 60–90 minutes; actual duration and pauses are recorded without changing the RED test after results.
- **AC:** named test green; dry run within envelope; manifest reviewer signs all material; package contains no copied closed adventure or uncleared binary.
- **Stop/falsification:** content misses time, reachability, balance or provenance gate → revise/cut the authored package under the same contract; do not expand runtime scope or weaken oracle.
- **License/privacy boundary:** original or explicitly licensed material only inside the private repo; no concept-reference binaries, current campaign world state, speech recordings or closed adventure text.
- **blocked-by:** I0, R9.

### I1 — Text-only durable action across table, scene and admin

- **Type:** IMPLEMENTATION / first behavioral tracer.
- **Decision/delivery owner:** backend/reliability lead; UX projection owner принимает surface behavior по R7.
- **Outcome:** fake model + typed text input support read-only question and one ordinary state-changing action through draft/approve/server-validated typed command/commit; all three surfaces reconnect to the same version.
- **Files (future repo):** src/server/turns/, src/server/projections/, src/server/transports/, src/web/table/, src/web/scene/, src/web/admin/, tests/integration/test_i1_text_turn.py.
- **RED oracle (future immutable):** uv run pytest -q tests/integration/test_i1_text_turn.py::test_i1_duplicate_approve_restart_three_surfaces.
- **RED assertions:** no world revision before approve; model text and raw client payload cannot mutate state; unknown/unauthorized typed command has zero mutation; accepted command records actor, expected state version and structured result in the server-authoritative kernel; stale draft rejected; duplicate approve returns same result and one mutation; crash after commit resumes publication not execution; table/scene/admin converge; secret canary absent from every browser projection including admin.
- **Required evidence:** R4 ADR/state machine and R7 surface contract; fake-provider trace; crash checkpoints.
- **AC:** named test green plus read-only question test proves zero mutation/no unnecessary approval.
- **Stop/falsification:** implementation needs client-trusted mutation, content dedupe, in-memory-only cursor or secret denylist → return to R4/R7.
- **License/privacy boundary:** behavioral implementation only; synthetic world; remote-authority contract even if test server is local.
- **blocked-by:** I0, R4, R7.

### I2 — One-mic Master button, action card and physical roll

- **Type:** IMPLEMENTATION / voice-input slice.
- **Decision/delivery owner:** audio/frontend lead; turn-contract изменения принадлежат R4 owner.
- **Outcome:** selected hero + push-to-talk produces final transcript/action card; shared Master action can produce one party-plan card with participant actions; pending_roll accepts one corrected physical result; ordinary room speech does nothing.
- **Files:** src/web/shared/audio-capture/, src/server/providers/stt/, src/server/turns/pending_roll.*, tests/integration/test_i2_voice_roll.py; browser test for Master button.
- **RED oracle (future immutable):** uv run pytest -q tests/integration/test_i2_voice_roll.py::test_i2_partial_reconnect_and_spoken_number_never_mutate.
- **RED assertions:** interim/late transcript ignored; character bound before audio; disconnect keeps unapproved draft; shared plan preserves named participants and requires one versioned party approval; «17 arrows» not a roll; corrected «roll 17» stored once for matching pending_roll; no diarization identity dependency.
- **Required evidence:** R5 selected path/codec/token/finality and privacy contract.
- **AC:** named test and browser capture test green; server logs contain no raw audio/key.
- **Stop/falsification:** requires constant cloud upload of room chatter, long-lived browser key or auto-approval → reject design.
- **License/privacy boundary:** short credentials only if selected; raw audio nonpersistent; synthetic fixtures in git.
- **blocked-by:** I1, R5.

### I3 — Authoritative grid, deterministic actions and typed unusual effect

- **Type:** IMPLEMENTATION / tactical-kernel slice.
- **Decision/delivery owner:** game-kernel lead; table interaction delivery owned jointly by frontend lead.
- **Outcome:** same Pointer Events UI supports mouse/touch move/attack and temporary planning arrows/markers; server validates grid/LOS/resources; one unusual action creates a typed terrain/effect change after approval.
- **Files:** src/game/kernel/, src/game/commands/, src/game/board/, src/web/table/board/, tests/integration/test_i3_board_tools.py.
- **RED oracle (future immutable):** uv run pytest -q tests/integration/test_i3_board_tools.py::test_i3_typed_unusual_action_is_validated_idempotent_and_replayed.
- **RED assertions:** illegal normal move zero mutation; legal move exact cells/resource; AI unknown/arbitrary command rejected; create_effect/change_terrain applies once; duplicate/replay same board; a player-safe arrow/marker is visible to the room after reconnect within R7 TTL, expires deterministically and never changes canonical world revision; hidden cells/tokens absent from player projection.
- **Required evidence:** R2 typed schema, R3 rules/LOS subset, R7 Pointer contract.
- **AC:** named test + mouse/touch reducer equivalence green.
- **Stop/falsification:** arbitrary JSON patch/Bash/SQL, client canonical coordinates or inability to replay effect → return R2/R3.
- **License/privacy boundary:** independently implemented kernel unless manifest says otherwise; cleared rule names/text only.
- **blocked-by:** I1, R2, R3.

### I4 — Story-graph NPC scene with off-rail consequence

- **Type:** IMPLEMENTATION / authored narrative slice.
- **Decision/delivery owner:** narrative-system lead; content truth accepted by R9 narrative owner.
- **Outcome:** one bright NPC scene exposes only discovered facts, permits an off-rail choice, advances threat/consequence and reaches the next hook without rewriting truth.
- **Files:** src/story/, src/game/campaign/, src/server/narration/, campaigns/mvp/ (private repo only), tests/integration/test_i4_story_scene.py.
- **RED oracle (future immutable):** uv run pytest -q tests/integration/test_i4_story_scene.py::test_i4_off_rail_choice_preserves_truth_and_relocates_hook.
- **RED assertions:** immutable culprit/motive unchanged; killed/absent NPC cannot speak; threat clock advances; alternative clue delivered only when condition met; unrevealed secret absent from three surfaces/TTS line.
- **Required evidence:** R1 director contract and I9 authored fixtures.
- **AC:** named test green; content trace reaches next node without invisible wall.
- **Stop/falsification:** fix requires model to mutate canonical truth or emit proprietary prompt/content client-side → return R1/R9.
- **License/privacy boundary:** campaign data private; player-safe/TTS allowlists; original/licensed content only.
- **blocked-by:** I1, R1, I9.

### I5 — One reversible side-phase combat with open world dice

- **Type:** IMPLEMENTATION / combat slice.
- **Decision/delivery owner:** game-systems lead; start-side/tie-break remain this role's engineering choice under R3.
- **Outcome:** player side chooses internal order, every hero acts once, world side is AI-selected but kernel-validated, enemy dice/outcomes public; story/normal/hard use only R3-declared parameters; classic scheduler remains selectable for experiment fallback.
- **Files:** src/game/combat/, src/game/rulesets/, src/server/enemy_ai/, src/web/table/combat/, tests/integration/test_i5_side_phase.py.
- **RED oracle (future immutable):** uv run pytest -q tests/integration/test_i5_side_phase.py::test_i5_side_phase_order_open_dice_and_classic_fallback_share_state_contract.
- **RED assertions:** acted hero cannot act twice; internal player order accepted; illegal enemy action rejected; each enemy roll includes dice/modifier/total/outcome and damage once; selected difficulty changes only R3-declared pre-roll parameters and cannot rewrite a committed enemy or physical-player roll; death saves follow R3; scheduler switch changes ordering only and preserves committed roll facts.
- **Required evidence:** R3 side-phase/rules decision, I9 balanced encounter, R2 command contract.
- **AC:** named test green; ordinary full combat trace uses no LLM/TTS provider call.
- **Stop/falsification:** scheduler leaks into state schema, cannot revert, hides enemy roll or requires model to validate standard action → redesign before I6.
- **License/privacy boundary:** cleared rules manifest; hidden enemy motive/stats remain server-side except explicitly disclosed roll modifiers.
- **blocked-by:** I3, R3, I9.

### I6 — Severin, NPC voices, cached combat lines, SFX and music

- **Type:** IMPLEMENTATION / presentation slice.
- **Decision/delivery owner:** audio lead; narrative voice/content accepted by R9 owner.
- **Outcome:** I2/I4/I5 events route to deterministic speech_line/SFX/music; common combat uses cache; important NPC/turn uses TTS; one client plays; cancel is end-to-end.
- **Files:** src/server/audio/, src/server/providers/tts/, src/web/shared/playback/, assets/audio/manifest.*, tests/integration/test_i6_audio.py.
- **RED oracle (future immutable):** uv run pytest -q tests/integration/test_i6_audio.py::test_i6_cancel_stops_provider_and_browser_without_replaying_game_action.
- **RED assertions:** correct entity voice/fallback; cache handles hit/miss offline; only leader plays; close_context + client stop/discard; late chunk ignored; retry audio leaves world revision unchanged; music_state crossfade event deterministic.
- **Required evidence:** R6 routing/cache/rights decision, I9 voice/line manifests and events from I4/I5.
- **AC:** named test + browser fake-audio test green; text-only degradation completes scene.
- **Stop/falsification:** audible cancel only provider-side, audio tied to mutation transaction, unlicensed asset/voice or multiple leaders → stop.
- **License/privacy boundary:** asset manifest mandatory; disclosed lines only; no keys/client secret; no binary from concept references.
- **blocked-by:** I2, I4, I5, I9, R6.

### I7 — Assemble the polished 60–90-minute vertical slice

- **Type:** IMPLEMENTATION / integrated content delivery.
- **Decision/delivery owner:** integration lead; narrative/game/audio owners accept only their already-closed contracts.
- **Outcome:** hero selection → Severin → NPC/choice → investigation/trap → shared plan/physical roll → explicit AI-ruling dispute → tactical battle under each declared difficulty fixture → boss/consequence runs as one resumable package.
- **Files:** campaigns/mvp/, src/app/session_flow/, tests/e2e/test_i7_vertical_slice.py; docs/rehearsal-runbook.md; asset/provenance manifest.
- **RED oracle (future immutable):** uv run pytest -q tests/e2e/test_i7_vertical_slice.py::test_i7_full_slice_fast_forward_is_restartable_secret_safe_and_provider_degradable.
- **RED assertions:** scripted fast-forward visits every canonical beat; dispute path either applies one idempotent typed correction or returns a brief explanation based only on a player-visible rule/fact, never player vote or admin override; each difficulty fixture preserves already committed roll facts; restart at each durable stage; no duplicate mutation/audio; all three projections converge; provider failures degrade per contract; persistent consequence appears in final snapshot.
- **Required evidence:** I9 package, I4/I5/I6 green, all manifests, no out-of-scope systems.
- **Delivery oracle:** facilitator-free dry run records actual duration and pauses without modifying the scripted test after results.
- **AC:** named automated test green; dry run fits canonical 60–90-minute envelope or content is cut; no camera/3D/random-map/character-builder dependency.
- **Stop/falsification:** duration miss, missing continuation consequence, administrator performs DM decisions or slice relies on undeclared manual state edit → not ready for staging.
- **License/privacy boundary:** private original campaign/assets only; no production/player data.
- **blocked-by:** I4, I5, I6, I9.

### I8 — Isolated remote-VPS room rehearsal

- **Type:** IMPLEMENTATION / non-production delivery rehearsal.
- **Decision/delivery owner:** release/reliability lead under separate staging authority; no owner/product or production decision.
- **Outcome:** the complete slice runs with remote authority and three real browser surfaces in the target room; admin can start/pause/end, inspect mic/connectivity, set volume, cancel stuck generation/audio and reproject the last confirmed state while recovering technical failures without becoming DM.
- **Files:** deployment profile and runbook in private repo; tests/e2e/test_i8_staging_room.py; no files/config in existing production.
- **RED oracle (future immutable):** uv run pytest -q tests/e2e/test_i8_staging_room.py::test_i8_three_clients_reconnect_to_remote_authority_with_one_audio_leader; harness обязан управлять тремя настоящими browser contexts, а не только HTTP/WebSocket test clients.
- **RED assertions:** authenticated and authorized table/scene/admin roles; surface/actor spoof, table→admin escalation, cross-room access, expired/replayed token and direct typed-command bypass of approval all fail closed with zero mutation; no browser including admin receives world-secret canary; browser has no long-lived keys; network reconnect restores exact versions; one audio leader; start/pause/end leave the coordinator in an explicit recoverable state; mic/connectivity checks and volume change no world state; cancel stops provider and buffered browser audio; reproject/audio retry never repeat world mutation; admin retries only an uncommitted stage; internet loss fails visibly without local split-brain.
- **Required evidence:** APPROVE STAGING; isolated service/domain/database/secrets; backups/rollback; R8 threat model and R7 capability/admin-control contract; R5/R6 real-room routes; I7 green; browser/device matrix.
- **AC:** named test and room rehearsal green; no existing production service/config changed; sanitized measurement artifact produced for R10.
- **Stop/falsification:** no isolated environment/rollback/approval, shared production DB/key, secret in client, or room path violates selected latency/reliability threshold → do not playtest.
- **License/privacy boundary:** least privilege, consent, no raw audio retention, staging-only assets/content.
- **blocked-by:** I7, R5, R6, R7, explicit APPROVE STAGING.

## 7. Implementation readiness matrix

| implementation ticket | research decisions that must be closed first | why |
|---|---|---|
| I0 | R8 | repo/license/access/transfer rules precede first commit |
| I9 | R9 | production campaign content starts only after the content/timing/provenance contract and I0 repo gate |
| I1 | R4, R7 | persistence, command IDs, projections and reconnect are its contract |
| I2 | R5 | codec/finality/direct-vs-proxy/token/privacy must be measured |
| I3 | R2, R3 | command vocabulary, rules/LOS and SRD boundary define behavior |
| I4 | R1, R9 | story invariants and content contract close before I9 supplies original fixtures |
| I5 | R3, R9 | side-phase semantics, fallback and encounter contract close before I9 supplies the battle |
| I6 | R6, R9 | voice rights/routing/cancel and content acceptance close before I9 supplies voices/lines |
| I7 | R9 plus I4–I6 | integration consumes I9 and cannot invent content or missing vertical behavior |
| I8 | R5–R7 plus separate staging approval | remote room measurement needs selected provider/UI path and external authority |

No implementation ticket may absorb an unresolved research question «temporarily». Such a discovery returns the ticket to its named R owner and preserves the RED oracle.

## 8. Migration, rollback and recovery policy

- **Migration:** MVP imports no current campaign/world/player/session data. Test fixtures are independently authored or manifest-cleared.
- **Schema:** private repo starts with versioned migrations from its first stateful commit; every migration has forward verification and a recoverable pre-migration backup in staging.
- **Side phases:** scheduler is a versioned ruleset setting; classic initiative remains behaviorally compatible fallback, not a second game kernel.
- **Speech:** direct/proxy and wake-word are adapter/config choices behind the same final-utterance contract; push-to-talk remains fallback.
- **Audio:** dynamic TTS can degrade to cached/text; sound retry is separate from game mutation.
- **Surfaces:** composite view is fallback over the same projection contract, not a divergent UI state.
- **Deployment:** I8 uses isolated staging and previous immutable release artifact for application rollback. No rollback command may restore an older world snapshot over a newer committed turn.
- **Research rollback:** falsified hypothesis selects the documented fallback; it does not silently weaken product invariants.

## 9. MVP completion gate

MVP may be called ready for the owner’s play only when:

- R1–R9 decisions/artifacts are closed and their evidence is reproducible;
- I0–I9 named commands and delivery checks are green;
- all license/provenance manifests are complete;
- raw audio/secrets/world-secret canaries are absent from forbidden outputs;
- R10 protocol is frozen before participants enter;
- admin runbook demonstrates recovery without creative DM override;
- no non-MVP dependency entered the critical path.

MVP may be called product-successful only after R10 evaluates the canonical continuation criterion. Green tests alone do not satisfy it.

## 10. Phase 3 entry and immutable RED gate

Phase 3 starts only after explicit approval. Execution order begins with R8/R4 decision work; I0 is the first repository mutation. Because this Phase 2 was constrained to plan/review artifacts, no target-repo test can exist yet.

Immediately after I0 delivery, before any I1 runtime code or executor dispatch:

1. create tests/integration/test_i1_text_turn.py in an oracle-only commit;
2. provide test doubles so collection succeeds;
3. run uv run pytest -q tests/integration/test_i1_text_turn.py::test_i1_duplicate_approve_restart_three_surfaces;
4. require exit 1 for missing idempotent durable behavior;
5. freeze the oracle path and assertions for I1.

The first required failing assertion is:

    assert recovered.world_mutation_count == 1, "duplicate approve or restart must never apply the world action twice"
