# Test Coverage Gap Analysis

## Current State

**Tested:** 4/19 core modules (21%), 0/7 RAG modules (0%)
**Total test files:** 5 + conftest.py
**Existing test cases:** ~65

### Tested Modules

| Module | Test File | Cases | Quality |
|--------|-----------|-------|---------|
| player_manager.py | test_player_manager.py | 17 | Good: HP/gold/XP CRUD, clamping, persistence, auto-detect |
| dice.py (partial) | test_dice_combat.py | 13 | Good: fuzzy matching, missing creatures, profession scaling |
| session_manager.py | test_session_manager.py | 15 | Fair: lacks corrupted JSON, error conditions |
| encounter_engine.py | test_encounter_engine.py | 20 | Excellent: statistical validation, cooldown, edge cases |

---

## Untested Modules — Prioritized by Risk

### Priority 1: Critical (High complexity, high usage, data-mutating)

#### 1. inventory_manager.py — 1,559 LOC, 19 public methods
- **Risk:** Highest LOC in codebase; manages all item/gold/weight operations
- **Testability:** Medium — needs campaign dir + inventory JSON + wiki JSON fixtures
- **Proposed tests (~200 LOC):**
  - `test_add_item` / `test_remove_item` — basic CRUD
  - `test_add_item_stacking` — quantity merging
  - `test_weight_calculation` — encumbrance
  - `test_use_item_consumable` — wiki lookup + consumption
  - `test_craft_item` — recipe validation, ingredient removal, DC check
  - `test_transfer_item` — between player and NPC
  - `test_gold_operations` — currency integration
  - `test_item_not_found` — error handling
  - `test_inventory_persistence` — file write verification
  - `test_party_inventory` — separate inventory file

#### 2. time_manager.py — 258 LOC, 9 public methods
- **Risk:** Drives game clock; incorrect time breaks consequences, encounters, session flow
- **Testability:** Easy — pure logic with campaign-overview.json
- **Proposed tests (~120 LOC):**
  - `test_advance_time_minutes` / `test_advance_time_hours`
  - `test_time_wraps_midnight` — day rollover
  - `test_time_of_day_labels` — Morning/Day/Evening/Night transitions
  - `test_elapsed_with_sleeping` — sleeping flag behavior
  - `test_date_advancement` — calendar integration
  - `test_ensure_precise_time` — legacy data migration
  - `test_get_current_time` — read-only

#### 3. campaign_manager.py — 445 LOC, 19 public methods
- **Risk:** Creates/deletes campaign directories; data loss possible
- **Testability:** Easy — filesystem operations on tmp_path
- **Proposed tests (~150 LOC):**
  - `test_create_campaign` — directory structure, default files
  - `test_list_campaigns` — empty and populated
  - `test_switch_campaign` — active-campaign.txt update
  - `test_delete_campaign` — cleanup verification
  - `test_create_duplicate_name` — error handling
  - `test_get_active_campaign` — resolution logic
  - `test_campaign_overview_defaults` — schema validation

### Priority 2: Important (Medium complexity, frequently used)

#### 4. dice.py (untested portions) — 778 LOC total
- **Risk:** Core mechanic; tested for combat but not base rolling
- **Testability:** Easy — pure functions
- **Proposed additional tests (~80 LOC):**
  - `test_simple_roll` — 1d20, 3d6+2
  - `test_advantage_disadvantage` — 2d20kh1/kl1
  - `test_invalid_notation` — error handling
  - `test_dc_check` — pass/fail threshold
  - `test_skill_check` — modifier lookup from character
  - `test_save_check` — ability save modifier

#### 5. calendar.py — 258 LOC, 10 public methods
- **Risk:** Date display; campaign-specific configs
- **Testability:** Easy — pure logic
- **Proposed tests (~80 LOC):**
  - `test_load_default_config` — gregorian defaults
  - `test_load_custom_config` — campaign override
  - `test_weekday_calculation`
  - `test_month_lengths` — including leap year if supported
  - `test_date_formatting`

#### 6. currency.py — 234 LOC, 10 public methods
- **Risk:** Money conversion errors cause gameplay issues
- **Testability:** Easy — pure functions
- **Proposed tests (~70 LOC):**
  - `test_format_money` — 2537 → "25g 3s 7c"
  - `test_parse_money` — "2gp 5sp" → 250
  - `test_custom_denominations` — campaign config
  - `test_compact_format`
  - `test_zero_amount` / `test_negative_amount`

### Priority 3: Lower Risk (Utility/support modules)

#### 7. json_ops.py — 285 LOC, 17 public methods
- **Risk:** Data persistence layer; corruption = data loss
- **Testability:** Easy — file I/O
- **Proposed tests (~90 LOC):**
  - `test_load_json` / `test_save_json`
  - `test_load_missing_file` — returns default
  - `test_load_corrupted_json` — error handling
  - `test_atomic_write` — no partial writes
  - `test_ensure_ascii_false` — unicode preservation

#### 8. validators.py — 304 LOC, 29 public methods
- **Risk:** Low — input validation; failures are safe
- **Testability:** Very easy — pure static methods
- **Proposed tests (~60 LOC):**
  - `test_validate_name_valid` / `test_validate_name_too_long`
  - `test_validate_name_special_chars`
  - `test_validate_attitude_valid` / `test_validate_attitude_invalid`

#### 9. entity_manager.py — 172 LOC, 4 public methods
- **Risk:** Low — base class; tested indirectly via subclasses
- **Testability:** Easy
- **Proposed tests (~40 LOC):**
  - `test_init_creates_paths`
  - `test_require_active_campaign`

#### 10. colors.py — ~50 LOC
- **Risk:** None — constants only
- **Testability:** Trivial
- **Proposed tests:** Not recommended (no logic)

### Priority 4: RAG Modules (External dependencies)

All RAG modules require `sentence-transformers` and `chromadb`. Tests should mock these.

#### 11. entity_enhancer.py — 877 LOC, 21 public methods
- **Testability:** Hard — heavy RAG integration
- **Proposed tests (~100 LOC):**
  - `test_enhance_npc` — mock vector store, verify query construction
  - `test_enhance_location` — mock results
  - `test_no_rag_available` — graceful degradation
  - `test_search_hybrid` — world state + RAG merge

#### 12. rag/vector_store.py
- **Testability:** Hard — chromadb dependency
- **Proposed tests (~60 LOC):** Mock chromadb client; test add/query/delete

#### 13. rag/semantic_chunker.py
- **Testability:** Medium — text processing
- **Proposed tests (~50 LOC):** Test chunk boundaries, overlap, empty input

#### 14. rag/embedder.py
- **Testability:** Hard — model loading
- **Proposed tests (~40 LOC):** Mock model; test embed shape/type

#### 15. rag/quote_extractor.py
- **Testability:** Easy — text processing
- **Proposed tests (~40 LOC):** Test quote extraction patterns

#### 16. rag/rag_extractor.py
- **Testability:** Hard — orchestrates RAG pipeline
- **Proposed tests (~60 LOC):** Mock all deps; test extraction flow

#### 17. rag/extraction_queries.py + extraction_schemas.py + content_extractor.py + agent_extractor.py
- **Testability:** Medium-Hard — schema validation, PDF deps
- **Proposed tests (~80 LOC):** Schema structure validation, mock PDF

---

## Existing Test Quality Assessment

### Strengths
- **Consistent pattern:** All tests use `tmp_path` fixture with helper functions to build world state
- **Persistence verification:** Most tests verify data written to disk, not just return values
- **Good isolation:** Each test creates fresh state; no shared mutable fixtures
- **Statistical testing:** encounter_engine tests use 2000-trial distributions

### Weaknesses
- **No error/corruption tests:** No test verifies behavior with corrupted JSON, missing fields, or disk errors
- **No concurrent access tests:** Multiple managers writing same files untested
- **Limited mocking:** Only dice_combat and encounter_engine use mocks; other tests do full I/O
- **No integration tests:** No test exercises tool→manager→file round-trip
- **Missing edge cases per module:**
  - session_manager: no test for corrupted session files, concurrent sessions
  - player_manager: no test for missing character.json mid-operation

### Fixture Assessment
- **Adequate** for current tests — minimal but sufficient
- **Missing:** Shared "rich campaign" fixture with NPCs, locations, plots, inventory, wiki all populated
- **conftest.py** has `stalker_campaign` but only used by encounter tests; could be generalized

---

## Summary Table

| Priority | Module | LOC | Est. Test LOC | Risk Level |
|----------|--------|-----|---------------|------------|
| P1 | inventory_manager | 1,559 | 200 | Critical |
| P1 | time_manager | 258 | 120 | Critical |
| P1 | campaign_manager | 445 | 150 | Critical |
| P2 | dice.py (gaps) | 778 | 80 | High |
| P2 | calendar | 258 | 80 | Medium |
| P2 | currency | 234 | 70 | Medium |
| P3 | json_ops | 285 | 90 | Medium |
| P3 | validators | 304 | 60 | Low |
| P3 | entity_manager | 172 | 40 | Low |
| P3 | colors | 50 | 0 | None |
| P4 | entity_enhancer | 877 | 100 | Medium |
| P4 | rag/* (6 modules) | ~600 | 330 | Medium |
| **Total** | | **~5,820** | **~1,320** | |

**Recommended implementation order:** P1 modules first (inventory, time, campaign), then P2 (dice gaps, calendar, currency). P3/P4 as capacity allows.
