## Summary

План хорошо соблюдает Phase 2-only scope, охватывает все десять research tracks и почти все ключевые подсистемы. Dependency graph в целом ацикличен, а путь I1→I8 действительно собирает тонкий вертикальный срез.

Проверяемая цитата из плана: «executor не получает ticket до независимой проверки RED» (строка 73). Это подтверждает, что отложенная материализация RED подкреплена реальным delivery gate, а не только намерением.

## Findings

### Blocking

1. **blocking:** [plan.md:173] Админской browser-проекции разрешены секреты (`admin payload may contain secrets`), что противоречит общей границе на строке 57, запрещающей world secrets в browser cache, и создаёт риск раскрытия кампании администратору или через скомпрометированный admin-клиент. Каноническая админка требует технического восстановления, а не доступа к сюжетной правде. Зафиксируйте минимальную operational projection без world secrets либо явно определите отдельное обоснование, поля, redaction/cache policy и security oracle.

2. **blocking:** [plan.md:368-372] Remote-VPS oracle проверяет аутентификацию ролей, но не авторизацию: нет отрицательных assertions для подмены surface/actor, table→admin privilege escalation, доступа к другой комнате, повторного использования истёкшего токена и прямой отправки typed command в обход approval coordinator. Для публично доступного authoritative backend это security gap; добавьте threat model в R8/R7 и fail-closed authorization assertions в I8.

### Suggestions

3. **suggestion:** [plan.md:220-230] R9 назван research, но его outcome — готовые карты, шесть героев, story graph, voice roster и combat-line pools — фактически production content implementation. Это размывает обязательное разделение research/implementation и позволяет создать значительную часть продукта без RED gate. Разделите R9 на research ticket, закрывающий формат, reachability, timing/balance и provenance, и implementation ticket, создающий сам campaign package после oracle-only commit.

4. **suggestion:** [plan.md:178-190] Канонические три режима сложности и запрет скрытого подкручивания результатов отсутствуют в R3, I5 и итоговом integration oracle. Добавьте вопрос о минимальной семантике режимов, deterministic fixtures для каждого режима и assertion, что режим меняет заявленные параметры, но не результаты уже сделанных бросков.

5. **suggestion:** [plan.md:263-275] I1 не проверяет полную authority boundary: outcome говорит об ordinary state-changing action, но RED assertions не требуют, чтобы мутация проходила именно через валидированную typed command и server-authoritative kernel. Добавьте assertions, что model text/client payload не мутируют state напрямую, неизвестная команда даёт zero mutation, а accepted command сохраняет actor, expected version и structured result.

6. **suggestion:** [plan.md:362-374] Админская поверхность сведена к reconnect/retry. Не покрыты обязательные controls из спецификации: start/pause/end, mic and connection check, volume, cancel stuck generation/audio и reproject last confirmed screen. Включите их в I8 browser oracle, особенно проверку, что reproject/audio retry не повторяют world mutation и что pause не оставляет coordinator в неоднозначном состоянии.

7. **suggestion:** [plan.md:291-303] Тактический срез не содержит временных стрелок и меток для совместного обсуждения, хотя это часть канонической table surface и один из механизмов продуктовой гипотезы о совместной тактике. Добавьте player-safe ephemeral overlay в I3/R7 с reconnect/expiry semantics и доказательством, что он не меняет canonical world state.

8. **suggestion:** [plan.md:347-358] Полный slice не включает обязательный путь спора с AI-судьёй: признание ошибки либо краткое объяснение правила/факта без голосования и admin override. Добавьте authored dispute beat и oracle для идемпотентной коррекции или объяснения с безопасной цитатой доступного правила/факта.

9. **suggestion:** [plan.md:192-218] R5/R6 требуют real provider comparison и controlled ElevenLabs traces, но не называют отдельный authority gate для платных API и обработки аудио внешним провайдером. `APPROVE PHASE 3` само по себе не должно молча разрешать расходы или передачу room speech. Добавьте явные `APPROVE PAID PROVIDER EXPERIMENT`/privacy gates либо бесплатные prerecorded/fake alternatives до такого разрешения.

10. **suggestion:** [plan.md:70-75] Абсолютная неизменяемость test/fixture/config после RED делает ошибочный или неоднозначный oracle неисправимым. Сохраните запрет на подгонку теста под реализацию, но определите контролируемую замену oracle-only commit: независимый review, документированная причина, повторно подтверждённый RED и запрет reuse старой implementation attempt.

## Verdict

**REQUEST CHANGES.** Phase 2 scope и отложенный RED enforcement в целом достаточны, dependency cycle не обнаружен. До исполнения нужно закрыть две security-проблемы: world-secret exposure через admin browser и отсутствие отрицательных authorization oracles для удалённого authoritative VPS. Остальные пункты — существенные улучшения полноты и исполнимости плана.

## Round (2026-08-16T12:23:34Z)

## Summary

All ten first-round findings are **FIXED**. The revised plan contains 10 research and 10 implementation tickets, preserves Phase 2-only scope, and presents an acyclic thin path through I9 to the 60–90 minute slice.

Evidence from the revised plan: “старую implementation attempt нельзя продолжать или использовать как evidence для новой” ([plan.md:79](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:79>)).

## Findings

No new blocking findings, suggestions, or material questions.

Prior findings:

1. **FIXED — admin secrets:** Admin is now operational-only and receives no world secrets; canaries cover every browser projection ([plan.md:57](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:57>), [plan.md:177](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:177>), [plan.md:390](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:390>)).

2. **FIXED — remote authorization:** R8 supplies the threat model; R7 defines capabilities; I8 rejects spoofing, escalation, cross-room access, token replay and approval bypass with zero mutation ([plan.md:119](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:119>), [plan.md:173](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:173>), [plan.md:389](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:389>)).

3. **FIXED — R9 separation:** R9 is explicitly research-only; I9 owns production campaign authoring behind a RED oracle ([plan.md:226](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:226>), [plan.md:269](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:269>)).

4. **FIXED — difficulty and immutable rolls:** R3 closes preset semantics; I5 and I7 prohibit rewriting committed physical or enemy rolls ([plan.md:187](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:187>), [plan.md:347](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:347>), [plan.md:375](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:375>)).

5. **FIXED — authority boundary in I1:** Model text, raw payloads and unknown commands cannot mutate state; accepted commands record actor, expected version and structured result ([plan.md:288](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:288>)).

6. **FIXED — admin controls:** I8 covers start/pause/end, diagnostics, volume, cancellation and safe reprojection ([plan.md:387](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:387>), [plan.md:390](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:390>)).

7. **FIXED — planning overlays:** R7 defines TTL/reconnect semantics and I3 proves zero canonical mutation ([plan.md:176](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:176>), [plan.md:319](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:319>)).

8. **FIXED — AI ruling dispute:** I7 includes an idempotent typed correction or player-visible explanation, never voting or admin override ([plan.md:372](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:372>)).

9. **FIXED — external-provider authority:** Real calls and room speech require separate approval and consent; fake/prerecorded evidence remains available beforehand ([plan.md:65](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:65>), [plan.md:204](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:204>)).

10. **FIXED — flawed RED replacement:** Immutability is scoped per attempt, with independent review, replacement oracle-only commit and a fresh RED required ([plan.md:76](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:76>)).

I9 is consistent across the dependency graph, ticket body, readiness matrix and completion gate: `I0 + R9 → I9`; downstream I4–I7 consume I9; readiness lists its research prerequisite; completion requires I0–I9 green ([plan.md:94](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:94>), [plan.md:282](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:282>), [plan.md:402](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:402>), [plan.md:430](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/plan.md:430>)).

## Verdict

**APPROVE.** The revised plan is consistent with the canonical specification and Phase 2 constraints. Its deferred RED enforcement is adequate, I9 is integrated consistently, and no new crash, corruption, or security contradiction was found.
