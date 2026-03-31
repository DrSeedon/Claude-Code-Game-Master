# Technical Debt Report

> Master consolidation of all architecture and code quality findings for the DM System codebase.
> Generated: 2026-03-29

---

## Executive Summary: Top 10 Findings

| # | Finding | Severity | Category | Detail Document |
|---|---------|----------|----------|-----------------|
| 1 | **WorldGraph is a 2,481-LOC god class** with 87 methods spanning 11 responsibility groups — tick engine alone is 580 LOC with 3x duplicated helper closures | Critical | God Class | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| 2 | **32% test coverage** — only 6/19 core modules tested, 0/6 RAG modules; highest-risk untested module is `inventory_manager.py` (1,559 LOC, 19 public methods); 144 test cases, 1,498 LOC | Critical | Testing | [TEST-COVERAGE-GAPS.md](TEST-COVERAGE-GAPS.md) |
| 3 | **Zero dependency injection** — every manager constructs its own `CampaignManager` + `JsonOperations`, duplicating bootstrap logic ~6 times with no interfaces/protocols | High | DI | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| 4 | **D&D 5e rules hardcoded throughout** — XP thresholds, proficiency bonus (duplicated 3x, one copy buggy at `dice.py:369`), die sizes, AC defaults baked into core code | High | Config | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| 5 | **22 broad `except Exception` catches** silently swallowing errors — `content_extractor.py` (7), `time_manager.py` (5), `agent_extractor.py` (4) | High | Error Handling | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 6 | **38 SOLID violations across 5 core managers** — 10 High severity, including CLI parsing mixed with domain logic in every manager (~510 LOC total) | High | SOLID | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |
| 7 | **~130 magic values** across 22 files with no centralized config — file paths duplicated in 3+ files each, ~50 display truncation constants scattered arbitrarily | Medium | Config | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| 8 | **118 `sys.exit()` calls in library code** — makes modules untestable; spread across all managers and world_graph.py | Medium | Error Handling | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| 9 | **Validators module has 9 identical methods** (~150 LOC) that could be 1 generic method + data dictionary — worst DRY violation in codebase | Medium | SOLID | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |
| 10 | **Russian strings in production code** — `inventory_manager.py` lines 47-62 has hardcoded Russian keywords for item classification, violating module design principles | Medium | Config | [CONFIG-DEBT.md](CONFIG-DEBT.md) |

---

## Quality Scorecard

| Category | Current Score | Target Score | Gap | Key Metric |
|----------|:------------:|:------------:|:---:|------------|
| **Test Coverage** | 3/10 | 7/10 | -4 | 32% modules tested (6/19 core, 0/6 RAG), 144 test cases |
| **SOLID Compliance** | 4/10 | 7/10 | -3 | 38 violations (10 High, 22 Medium, 6 Low) |
| **God Class Health** | 2/10 | 7/10 | -5 | 1 god class (2,481 LOC), 3 large managers (500-950 LOC) |
| **Error Handling** | 3/10 | 7/10 | -4 | 29 broad catches, 118 sys.exit(), 60+ print errors, 0 exception hierarchy |
| **Dependency Injection** | 1/10 | 6/10 | -5 | 0 protocols, 0 injected deps, ~6 duplicated bootstrap sequences |
| **Config Centralization** | 2/10 | 7/10 | -5 | ~130 magic values, 0 constants files, 11 duplicated file paths |
| **Architecture** | 6/10 | 8/10 | -2 | Clean 4-layer design, good middleware system, but god class undermines it |
| **Code Organization** | 5/10 | 8/10 | -3 | Clear module boundaries exist but CLI mixed with domain in all managers |
| **Overall** | **3.2/10** | **7.1/10** | **-3.9** | |

---

## SOLID Violations Summary

### By Severity

| Severity | Count | Key Examples |
|----------|:-----:|-------------|
| **High** | 10 | D&D 5e XP hardcoded in PlayerManager; SessionManager handles 4 responsibilities; TimeManager writes directly to other module's data files |
| **Medium** | 22 | CLI in domain files (all 5 managers); print() in business logic; legacy format branching; hardcoded campaign defaults |
| **Low** | 6 | Lazy imports; `sys.path` manipulation; minor ISP violations |
| **Total** | **38** | |

### By Principle

| Principle | Violations | Worst Offender |
|-----------|:----------:|----------------|
| SRP (Single Responsibility) | 22 | SessionManager — session lifecycle + movement + saves + context aggregation |
| OCP (Open/Closed) | 8 | PlayerManager — D&D 5e XP thresholds as fixed list |
| DIP (Dependency Inversion) | 6 | EntityManager — hard-constructs all dependencies |
| ISP (Interface Segregation) | 1 | TimeManager — duplicates EntityManager pattern without inheriting |
| DRY (Don't Repeat Yourself) | 1 | Validators — 9 identical validation methods |

### Cross-Cutting Issues

1. **CLI in Domain Files** — All 5 managers bundle `main()` CLI parsing (95-160 LOC each), totaling ~510 LOC of CLI code mixed with domain code
2. **Console Output in Domain Methods** — `print()` calls scattered throughout business logic in PlayerManager, SessionManager, CampaignManager
3. **Hard Dependencies via Constructor** — No DI; all managers create CampaignManager + JsonOperations internally
4. **Duplicated Legacy Format Support** — PlayerManager and SessionManager both independently implement dual-path character loading

---

## God Class Status

| Class | LOC | Methods | Responsibility Groups | Severity |
|-------|:---:|:-------:|:---------------------:|----------|
| **WorldGraph** | 2,481 | 87 | 11 (Infrastructure, Node CRUD, Edge CRUD, Display, ID Resolution, Facts, Quest, Inventory, Player, Tick Engine, CLI) | **Critical** |
| InventoryManager | 1,559 | 19 | 4 (item CRUD, weight/encumbrance, crafting, display) | High |
| PlayerManager | 611 | ~15 | 4 (stats, conditions, money, display) | Medium |
| SessionManager | 542 | ~12 | 4 (lifecycle, movement, saves, context) | Medium |

### WorldGraph Decomposition Priority

The tick engine (Group N: 580 LOC, 13 methods, 5 duplicated closures) is the highest-priority extraction target. It has clear boundaries and heavy internal coupling that doesn't need to be in the main class.

---

## Error Handling Score

| Metric | Count |
|--------|:-----:|
| Broad `except Exception` catches | 29 |
| Bare `except:` catches | 0 |
| `sys.exit()` in library code | 118 |
| Print-based error reporting | 60+ |
| Specific exception catches | 33 |
| Custom exception classes | 0 |
| Structured error hierarchy | None |

### Modules Needing Most Work (Ranked)

1. **content_extractor.py** — 7 broad catches, all silent
2. **time_manager.py** — 5 broad catches returning silent defaults
3. **inventory_manager.py** — 2 broad catches + 15 print-based errors
4. **agent_extractor.py** — 4 broad catches in JSON/LLM pipeline
5. **json_ops.py** — 2 broad catches + 6 sys.exit() (core utility)

### Proposed Fix

Create `lib/exceptions.py` with typed hierarchy: `DMError` → `EntityNotFoundError`, `ValidationError`, `ConfigError`, `FileError`, `RAGError`, `CurrencyError`, `DuplicateEntityError`. Migrate `sys.exit()` to CLI boundary only.

---

## Dependency Injection Assessment

| Metric | Value |
|--------|-------|
| Protocol/interface definitions | 0 |
| Classes using constructor injection | 0 |
| Classes with hardcoded dependencies | 8 |
| Duplicated bootstrap sequences | ~6 |
| Cross-manager hidden coupling | 1 (InventoryManager→ModuleDataManager direct coupling) |

### Current Dependency Graph

```
CampaignManager (standalone)
    │
    ▼
EntityManager ──► JsonOperations, Validators, CampaignManager
    │
    ├── PlayerManager ──► SessionManager (lazy)
    └── SessionManager

TimeManager,
EntityEnhancer, AgentExtractor ──► CampaignManager + JsonOperations (each creates own)

InventoryManager ──► ModuleDataManager (direct)
```

### Proposed Fix

Introduce `CampaignContext` factory that resolves once, shared by all managers. Add `JsonStore` and `CampaignResolver` protocols for testability.

---

## Configuration Debt Score

| Category | Magic Values | Risk Level |
|----------|:-----------:|:----------:|
| XP / Level Progression | 6 instances | **High** — D&D 5e lock-in, proficiency bug |
| HP / Health Thresholds | 6 instances (3 files) | **Medium** — duplicated |
| File Paths / Names | 11 filenames × 3+ files each | **High** — rename = multi-file hunt |
| Display Truncation | ~50 constants (5 files) | **Medium** — arbitrary, untested |
| Search/Similarity Thresholds | 5 instances | **Low** — tuning requires code changes |
| Encounter Rates / Dice | 8 instances | **Medium** — game-system lock-in |
| Validation Limits | 5 instances | **Low** |
| Default Campaign Values | 10 instances | **Medium** |
| Russian Strings in Code | 1 file (inventory_manager.py) | **Medium** — violates language policy |
| **Total** | **~130** | |

### Implementation Priority

1. **HIGH** — Create `lib/constants.py` for file paths (30 min)
2. **HIGH** — Fix proficiency bonus bug in `dice.py:369` (5 min)
3. **HIGH** — Extract Russian `ITEM_CATEGORIES` to data file (30 min)
4. **MEDIUM** — Game system config section in campaign-overview.json (2 hrs)
5. **MEDIUM** — Centralize display truncation constants (1 hr)

---

## Test Coverage Score

| Metric | Value |
|--------|-------|
| Core modules tested | 6/19 (32%) |
| RAG modules tested | 0/6 (0%) |
| Total test cases | 144 |
| Test LOC | 1,498 |
| Test files | 6 + conftest.py |
| Estimated LOC to reach 70% | ~900 |

### Priority 1 (Critical — Untested, High Risk)

| Module | LOC | Public Methods | Estimated Test LOC |
|--------|:---:|:--------------:|:------------------:|
| inventory_manager.py | 1,559 | 19 | ~200 |
| time_manager.py | 258 | 9 | ~120 |
| campaign_manager.py | 445 | 19 | ~150 |

### Priority 2 (Important — Untested, Medium Risk)

| Module | LOC | Public Methods | Estimated Test LOC |
|--------|:---:|:--------------:|:------------------:|
| dice.py (untested portions) | 778 | — | ~80 |
| calendar.py | 258 | 10 | ~80 |
| currency.py | 234 | 10 | ~70 |

---

## Refactoring Roadmap

### Phase 1: Quick Wins (1-2 days)

| Task | Impact | Effort | Document |
|------|--------|--------|----------|
| Fix proficiency bonus bug in `dice.py:369` | High | 5 min | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| Create `lib/constants.py` for file paths | High | 30 min | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| Extract Russian strings to data file | Medium | 30 min | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| Refactor Validators to generic `_validate_enum()` | Medium | 30 min | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |
| Extract `_navigate_path()` helper in JsonOperations | Low | 15 min | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |

### Phase 2: Error Handling Foundation (2-3 days)

| Task | Impact | Effort | Document |
|------|--------|--------|----------|
| Create `lib/exceptions.py` hierarchy | High | 1 hr | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| Migrate `json_ops.py` from sys.exit() to exceptions | High | 2 hrs | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| Migrate remaining managers from sys.exit() | Medium | 4 hrs | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |
| Replace broad catches in extractors with specific | Medium | 3 hrs | [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) |

### Phase 3: Test Coverage Push (3-5 days)

| Task | Impact | Effort | Document |
|------|--------|--------|----------|
| Tests for inventory_manager.py | Critical | 4 hrs | [TEST-COVERAGE-GAPS.md](TEST-COVERAGE-GAPS.md) |
| Tests for time_manager.py | High | 2 hrs | [TEST-COVERAGE-GAPS.md](TEST-COVERAGE-GAPS.md) |
| Tests for campaign_manager.py | High | 3 hrs | [TEST-COVERAGE-GAPS.md](TEST-COVERAGE-GAPS.md) |
| Tests for dice.py, calendar.py, currency.py | Medium | 4 hrs | [TEST-COVERAGE-GAPS.md](TEST-COVERAGE-GAPS.md) |

### Phase 4: Dependency Injection (3-5 days)

| Task | Impact | Effort | Document |
|------|--------|--------|----------|
| Create `lib/protocols.py` (JsonStore, CampaignResolver) | High | 1 hr | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| Create `CampaignContext` factory | High | 2 hrs | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| Refactor EntityManager to accept injected deps | High | 3 hrs | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |
| Refactor standalone managers | Medium | 4 hrs | [DI-ASSESSMENT.md](DI-ASSESSMENT.md) |

### Phase 5: God Class Decomposition (5-8 days)

| Task | Impact | Effort | Document |
|------|--------|--------|----------|
| Extract TickEngine from WorldGraph | Critical | 8 hrs | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| Extract domain facades (Quest, Inventory, Player, etc.) | High | 8 hrs | [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) |
| Separate CLI from domain in all managers | Medium | 6 hrs | [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) |

### Phase 6: Config Externalization (2-3 days)

| Task | Impact | Effort | Document |
|------|--------|--------|----------|
| Game system config in campaign-overview.json | Medium | 2 hrs | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| Centralize display truncation constants | Low | 1 hr | [CONFIG-DEBT.md](CONFIG-DEBT.md) |
| Per-location encounter rate overrides | Low | 1 hr | [CONFIG-DEBT.md](CONFIG-DEBT.md) |

---

## Related Documents

| Document | Focus |
|----------|-------|
| [ARCHITECTURE-MAP.md](ARCHITECTURE-MAP.md) | 4-layer architecture, data flow, dependency graph |
| [GOD-CLASS-DECOMPOSITION.md](GOD-CLASS-DECOMPOSITION.md) | WorldGraph 87-method analysis with decomposition proposals |
| [SOLID-VIOLATIONS.md](SOLID-VIOLATIONS.md) | 38 violations across managers and utilities |
| [ERROR-HANDLING-AUDIT.md](ERROR-HANDLING-AUDIT.md) | File-by-file error pattern catalog with exception hierarchy proposal |
| [DI-ASSESSMENT.md](DI-ASSESSMENT.md) | Dependency graph, DI strategy with protocols and CampaignContext |
| [CONFIG-DEBT.md](CONFIG-DEBT.md) | 130 magic values cataloged across 9 categories |
| [TEST-COVERAGE-GAPS.md](TEST-COVERAGE-GAPS.md) | Module-by-module test proposals with LOC estimates |
