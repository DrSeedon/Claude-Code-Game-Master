# Refactoring Roadmap

> Phased, prioritized plan for addressing technical debt in the DM System codebase.
> Generated: 2026-03-29 | Based on: [TECHNICAL-DEBT-REPORT.md](TECHNICAL-DEBT-REPORT.md)

---

## Timeline Overview

| Phase | Name | Effort | Risk | Dependencies |
|:-----:|------|:------:|:----:|:------------:|
| 1 | Quick Wins | 1-2 days | Low | None |
| 2 | DI & Testability | 3-5 days | Medium | Phase 1 |
| 3 | God Class Decomposition | 5-10 days | High | Phase 2 |
| 4 | Test Coverage | Ongoing | Low | Phase 1; benefits from Phase 2-3 |
| 5 | Error Handling Overhaul | 3-5 days | Medium | Phase 2 |

**Total estimated effort:** 15-27 days (single developer)

---

## Dependency Graph

```
Phase 1: Quick Wins
    │
    ├──────────────────┐
    ▼                  ▼
Phase 2: DI        Phase 4: Test Coverage (can start after Phase 1)
    │                  ▲
    ├──────────┐       │ (benefits from DI + decomposition)
    ▼          ▼       │
Phase 3:    Phase 5:   │
God Class   Error      │
Decomp.     Handling ──┘
```

Phase 4 (Test Coverage) is intentionally parallel — tests can begin after Phase 1 but become significantly easier after Phase 2 introduces DI. Phase 5 can run concurrently with Phase 3.

---

## Phase 1: Quick Wins

**Effort:** 1-2 days | **Risk:** Low | **Dependencies:** None

Low-effort, high-impact changes that improve code quality without architectural risk.

### Tasks

| # | Task | Effort | Impact | Reference |
|---|------|:------:|:------:|-----------|
| 1.1 | Fix proficiency bonus bug in `dice.py:369` | 5 min | High | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| 1.2 | Create `lib/constants.py` — centralize 11 file path constants duplicated across 3+ files each | 30 min | High | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| 1.3 | Extract Russian `ITEM_CATEGORIES` from `inventory_manager.py:47-62` to a data/config file | 30 min | Medium | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| 1.4 | Refactor `Validators` — replace 9 identical methods (~150 LOC) with 1 generic `_validate_enum()` + data dict | 30 min | Medium | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |
| 1.5 | Extract `_navigate_path()` helper in `JsonOperations` to eliminate duplicated path traversal | 15 min | Low | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |
| 1.6 | Centralize display truncation constants (~50 magic numbers across 5 files) | 1 hr | Medium | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| 1.7 | Add basic logging infrastructure — replace key `print()` error calls with `logging.error()` | 2 hrs | Medium | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |

### Success Criteria

- [ ] `uv run pytest` passes with no regressions
- [ ] `lib/constants.py` exists and is imported by all modules that previously hardcoded file paths
- [ ] Zero Russian strings remain in Python source files
- [ ] `Validators` class has exactly 1 generic validation method + data dictionary
- [ ] Proficiency bonus returns correct value for all 20 levels

### Rollback Strategy

Each task is an independent commit. Revert any single commit without affecting others. No schema changes, no API changes — purely internal refactoring.

---

## Phase 2: DI & Testability

**Effort:** 3-5 days | **Risk:** Medium | **Dependencies:** Phase 1 (constants must exist first)

Introduce Protocol-based interfaces and constructor injection so managers can be tested in isolation.

### Tasks

| # | Task | Effort | Impact | Reference |
|---|------|:------:|:------:|-----------|
| 2.1 | Create `lib/protocols.py` — define `JsonStore`, `CampaignResolver`, `EntityStore` protocols | 1 hr | High | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| 2.2 | Create `CampaignContext` factory — single bootstrap point replacing ~10 duplicated sequences | 2 hrs | High | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| 2.3 | Refactor `EntityManager` to accept injected `JsonOperations` + `CampaignManager` via constructor | 3 hrs | High | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| 2.4 | Refactor standalone managers (`TimeManager`, `InventoryManager`, `CalendarManager`, etc.) to accept deps | 4 hrs | Medium | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| 2.5 | Separate CLI `main()` from domain logic in all 5 managers (~510 LOC total to extract) | 4 hrs | Medium | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |
| 2.6 | Remove `sys.exit()` from library code — migrate 29 calls to raise exceptions, catch at CLI boundary | 3 hrs | High | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |

### Success Criteria

- [ ] `lib/protocols.py` defines at least 3 Protocol classes
- [ ] All managers accept dependencies via constructor (no internal `CampaignManager()` calls)
- [ ] `CampaignContext` is the single entry point for manager construction
- [ ] Zero `sys.exit()` calls remain in `lib/` (only in `tools/` CLI scripts or `main()` functions)
- [ ] Each manager can be instantiated in tests with mock dependencies
- [ ] `uv run pytest` passes — existing tests updated to use new constructors

### Risk Mitigation

- **Backward compatibility:** Keep `main()` functions as CLI entry points that construct `CampaignContext` internally — bash wrappers unchanged
- **Incremental migration:** Refactor one manager at a time, run full test suite after each
- **Fallback constructors:** Managers can retain zero-arg constructors that create defaults (deprecated, for transition period)

### Rollback Strategy

Revert to pre-Phase-2 branch. CLI wrappers are unchanged, so no downstream impact. Managers revert to self-constructing dependencies.

---

## Phase 3: God Class Decomposition

**Effort:** 5-10 days | **Risk:** High | **Dependencies:** Phase 2 (DI required for clean extraction)

Break WorldGraph (2,481 LOC, 87 methods, 16 responsibility groups) into focused, testable components.

### Tasks

| # | Task | Effort | Impact | Reference |
|---|------|:------:|:------:|-----------|
| 3.1 | Extract `TickEngine` from WorldGraph (580 LOC, 13 methods, 5 duplicated closures) | 8 hrs | Critical | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| 3.2 | Extract domain facades — `NPCFacade`, `LocationFacade`, `QuestFacade`, `FactsFacade` | 12 hrs | High | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| 3.3 | Extract `WorldGraphDisplay` — all display/formatting methods into presentation layer | 4 hrs | Medium | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| 3.4 | Refactor `InventoryManager` — separate crafting subsystem (recipe resolution, material checks) | 6 hrs | Medium | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| 3.5 | Deduplicate tick engine helper closures (3x duplicated across tick methods) | 2 hrs | Medium | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| 3.6 | Make `WorldGraph` a thin coordinator — delegates to extracted components | 4 hrs | High | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |

### Success Criteria

- [ ] `WorldGraph` is under 800 LOC (down from 2,481)
- [ ] `TickEngine` is a standalone class with its own test file
- [ ] Domain facades each have < 300 LOC and single responsibility
- [ ] `InventoryManager` core is under 800 LOC (crafting extracted)
- [ ] Zero duplicated helper closures in tick engine code
- [ ] All existing `dm-*.sh` tools work identically (integration test)
- [ ] `uv run pytest` passes with no regressions

### Risk Mitigation

- **Feature flags:** WorldGraph can delegate to new components or use old code paths via a flag during transition
- **Integration tests first:** Before decomposing, write integration tests for key WorldGraph workflows (tick, move, NPC interaction) to catch regressions
- **One extraction at a time:** Never extract two components simultaneously — merge and test between each

### Rollback Strategy

Each extraction is a separate branch. If a facade breaks integration, revert that branch only. WorldGraph retains all original methods as thin delegators, so reverting a facade means re-inlining that group only.

---

## Phase 4: Test Coverage

**Effort:** Ongoing (initial push ~5-8 days) | **Risk:** Low | **Dependencies:** Phase 1 minimum; Phase 2-3 make testing far easier

Raise test coverage from the current baseline toward 70%+ target.

### Tasks — Priority Order

| # | Module | LOC | Est. Test LOC | Priority | Depends On |
|---|--------|:---:|:------------:|:--------:|:----------:|
| 4.1 | `inventory_manager.py` | 1,559 | ~200 | Critical | Phase 2.4 (DI) |
| 4.2 | `time_manager.py` | 258 | ~120 | High | Phase 2.4 |
| 4.3 | `campaign_manager.py` | 445 | ~150 | High | Phase 2.2 |
| 4.4 | `calendar.py` | 258 | ~80 | Medium | None |
| 4.5 | `currency.py` | 234 | ~70 | Medium | None |
| 4.6 | `dice.py` (untested portions) | 778 | ~80 | Medium | None |
| 4.7 | RAG modules (7 files) | ~2,000 | ~300 | Low | Phase 2.4 |

**Note:** Tasks 4.4-4.6 have no DI dependency and can start immediately after Phase 1.

### Success Criteria

- [ ] Core module coverage ≥ 70% (target: majority of remaining modules with tests)
- [ ] All Priority 1 modules (inventory, time, campaign) have tests
- [ ] Total test count ≥ 200 (up from ~93)
- [ ] No untested public method in any Priority 1 module
- [ ] CI-compatible test suite (all tests pass with `uv run pytest`)

### Rollback Strategy

Tests are additive — no rollback needed. If a test is flaky, skip with `@pytest.mark.skip` and file a fix task.

---

## Phase 5: Error Handling Overhaul

**Effort:** 3-5 days | **Risk:** Medium | **Dependencies:** Phase 2 (DI + sys.exit removal)

Replace ad-hoc error handling with a structured exception hierarchy.

### Tasks

| # | Task | Effort | Impact | Reference |
|---|------|:------:|:------:|-----------|
| 5.1 | Create `lib/exceptions.py` — `DMError` base → `EntityNotFoundError`, `ValidationError`, `ConfigError`, `FileError`, `RAGError`, `CurrencyError`, `DuplicateEntityError` | 1 hr | High | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 5.2 | Migrate `content_extractor.py` — replace 7 broad `except Exception` with specific catches | 2 hrs | High | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 5.3 | Migrate `time_manager.py` — replace 5 broad catches returning silent defaults | 2 hrs | High | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 5.4 | Migrate `inventory_manager.py` — replace 2 broad catches + 15 print-based errors | 3 hrs | Medium | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 5.5 | Migrate `agent_extractor.py` — replace 4 broad catches in JSON/LLM pipeline | 2 hrs | Medium | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 5.6 | Migrate remaining managers — replace print-based error reporting with exceptions | 4 hrs | Medium | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 5.7 | Add error context enrichment — include entity IDs, file paths, operation names in exceptions | 2 hrs | Low | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |

### Success Criteria

- [ ] `lib/exceptions.py` exists with typed hierarchy (7+ exception classes)
- [ ] Zero broad `except Exception` catches remain (down from 22)
- [ ] Zero `print()`-based error reporting in business logic (down from 60+)
- [ ] All exceptions include actionable context (entity ID, operation, file path)
- [ ] CLI boundary (`main()` functions) is the only place that catches `DMError` and prints user-friendly messages
- [ ] `uv run pytest` passes — error paths tested

### Risk Mitigation

- **Catch-all safety net:** Keep a single `except DMError` at CLI boundary so no exception escapes to user as a stack trace
- **Incremental migration:** One module at a time, with tests validating error paths
- **Logging fallback:** Any replaced `print()` also logs to `logging.warning()` during transition

### Rollback Strategy

Exception hierarchy is additive. If a module migration causes issues, revert that module's commit — the base `lib/exceptions.py` remains valid. Other migrated modules are unaffected.

---

## Quality Scorecard Targets

| Category | Current | After Phase 1 | After Phase 2 | After Phase 3 | After Phase 5 | Target |
|----------|:-------:|:-------------:|:-------------:|:-------------:|:-------------:|:------:|
| Test Coverage | 2/10 | 2/10 | 3/10 | 4/10 | 5/10 | 7/10 |
| SOLID Compliance | 4/10 | 5/10 | 6/10 | 7/10 | 7/10 | 7/10 |
| God Class Health | 2/10 | 2/10 | 2/10 | 7/10 | 7/10 | 7/10 |
| Error Handling | 3/10 | 3/10 | 5/10 | 5/10 | 7/10 | 7/10 |
| Dependency Injection | 1/10 | 1/10 | 6/10 | 7/10 | 7/10 | 6/10 |
| Config Centralization | 2/10 | 5/10 | 5/10 | 5/10 | 6/10 | 7/10 |
| **Overall** | **3.1** | **3.8** | **4.8** | **5.8** | **6.5** | **7.1** |

---

## Implementation Guidelines

### Commit Strategy

- One commit per task (e.g., `1.2`, `2.3`, `3.1`)
- Commit message format: `refactor(phase-N): task description`
- Run `uv run pytest` before every commit
- Never combine tasks from different phases in one commit

### Branch Strategy

- `refactor/phase-1-quick-wins`
- `refactor/phase-2-di-testability`
- `refactor/phase-3-god-class-decomposition`
- `refactor/phase-4-test-coverage`
- `refactor/phase-5-error-handling`

Each phase branch merges to `main` only after all tasks pass CI.

### Definition of Done (per phase)

1. All tasks completed and committed
2. `uv run pytest` passes with zero failures
3. All bash tool wrappers (`dm-*.sh`) function identically
4. No new `print()` debugging statements
5. Phase success criteria checklist fully satisfied

---

## Related Documents

| Document | Focus |
|----------|-------|
| [TECHNICAL-DEBT-REPORT.md](TECHNICAL-DEBT-REPORT.md) | Master consolidation — top 10 findings, quality scorecard |
| [ARCHITECTURE-MAP.md](ARCHITECTURE-MAP.md) | 4-layer architecture, data flow, dependency graph |
| [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) | WorldGraph 87-method analysis with decomposition proposals |
| [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) | 38 violations across managers and utilities |
| [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) | File-by-file error pattern catalog with exception hierarchy proposal |
| [DI-ASSESSMENT.md](DI-ASSESSMENT.md) | Dependency graph, DI strategy with protocols and CampaignContext |
| [CONFIG-DEBT.md](CONFIG-DEBT.md) | 130 magic values cataloged across 9 categories |
| [TEST-COVERAGE-GAPS.md](TEST-COVERAGE-GAPS.md) | Module-by-module test proposals with LOC estimates |
