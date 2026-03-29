# SOLID Violations Audit

## Section 1: Manager Modules

---

### 1.1 EntityManager (173 LOC) — `lib/entity_manager.py`

**Overall Assessment:** Low severity. Clean base class with focused CRUD responsibilities.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DIP | 16, 48 | Hard-imports `CampaignManager`, `JsonOperations`, `Validators` — creates concrete dependencies in constructor instead of accepting abstractions via injection | Medium |
| 2 | SRP | 26-58 | Constructor has dual initialization paths (direct path vs active-campaign lookup) — mixing test-support logic with production logic | Low |
| 3 | DIP | 12 | `sys.path.insert(0, ...)` — runtime path manipulation for imports instead of proper package structure | Low |
| 4 | OCP | 60-163 | CRUD methods are tightly bound to JSON file storage via `json_ops` — cannot swap storage backend without modifying this class | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 47: `"world-state"` hardcoded default directory name
- Line 54: `"No active campaign. Run /new-game or /import first."` — UI message in domain class

---

### 1.2 PlayerManager (611 LOC) — `lib/player_manager.py`

**Overall Assessment:** High severity. Largest manager with multiple SRP violations and D&D-specific hardcoding.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | SRP | 24-45 | D&D 5e XP thresholds hardcoded as class constant — level progression logic should be externalized/configurable per game system | High |
| 2 | SRP | 60-119 | Character file I/O with legacy format support — persistence layer mixed with domain logic. Dual-path loading (single file vs `characters/` dir) is migration logic that doesn't belong here | High |
| 3 | SRP | 162-214 | `show_player()` and `show_all_players()` format display strings with currency — presentation logic mixed with domain | Medium |
| 4 | SRP | 397-464 | `modify_money()` handles: currency config loading, gold-to-money migration, string parsing ("2g 5s"), clamping, persistence, and console output — at least 3 responsibilities in one method | High |
| 5 | SRP | 466-528 | `modify_condition()` is a mini-CRUD system embedded in the player manager — conditions could be a separate concern | Medium |
| 6 | SRP | 531-694 | CLI argument parsing (~160 LOC) in the same file as domain logic | Medium |
| 7 | OCP | 24-45 | XP thresholds are a fixed list — no way to support non-D&D5e level systems without modifying this class | High |
| 8 | DIP | 16-17 | Hard-imports `currency` module functions — currency system is a concrete dependency | Low |
| 9 | OCP | 64-76 | Legacy vs new character format — branching on file existence rather than a strategy pattern | Medium |
| 10 | SRP | 278-283, 350-358 | Print statements (console output) scattered throughout domain methods — UI/presentation mixed with business logic | Medium |

**Magic Numbers / Hardcoded Values:**
- Lines 24-45: 20 hardcoded XP threshold values (D&D 5e specific)
- Line 128: `self.XP_THRESHOLDS[1]` — magic index for level 1 reset
- Line 251: `while new_level < 20` — max level hardcoded
- Line 259: `if new_level < 20` — repeated max level check
- Line 339: `max(0, min(...))` — HP floor of 0 hardcoded
- Line 358: `max_hp // 4` — bloodied threshold (25%) hardcoded
- Line 380: `new_max = 1` — minimum max HP hardcoded

---

### 1.3 SessionManager (542 LOC) — `lib/session_manager.py`

**Overall Assessment:** High severity. God-class tendencies — manages sessions, movement, saves, and context display.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | SRP | 21-571 | Class handles 4 distinct responsibilities: session lifecycle, party movement (with location management), save/restore system, and full context aggregation | High |
| 2 | SRP | 111-146 | `_ensure_location_and_connection()` — location graph management embedded in session manager. This is location manager's job | High |
| 3 | SRP | 196-231 | Save system (create/restore/list/delete) — should be a separate `SaveManager` class | High |
| 4 | SRP | 333-480 | `get_full_context()` is a 150-line method that reads campaign, character, NPCs, consequences, and rules — report generation embedded in session manager | High |
| 5 | OCP | 437-453 | Consequence format handling branches on `isinstance(consequences, dict)` vs `isinstance(consequences, list)` — fragile type checking instead of polymorphism | Medium |
| 6 | DIP | 171-184 | Direct file I/O for character.json with legacy fallback — same dual-path pattern as PlayerManager, duplicated logic | Medium |
| 7 | SRP | 225-227 | `import json` inside method body — lazy import for save operations | Low |
| 8 | OCP | 357-363 | Character loading inside context method uses raw file I/O instead of PlayerManager — bypasses existing abstractions | Medium |
| 9 | SRP | 573-668 | CLI parsing (~95 LOC) in same file as domain logic | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 323: `[-10:]` — hardcoded limit of 10 history entries
- Line 329: `limit: int` parameter with no default, but called as `_truncate(..., 180, ...)` (line 410)
- Line 399: `8` — max party members shown in compact mode
- Line 419: `[-3:]` / `[-2:]` — recent events limits
- Line 444: `cid[:4]` — consequence ID truncation length
- Line 457: `10` — max pending consequences shown
- Line 489-490: `"facts.json"` filename check for special counting logic

---

### 1.4 CampaignManager (445 LOC) — `lib/campaign_manager.py`

**Overall Assessment:** Medium severity. Cleanest of the large managers but still has SRP issues.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | SRP | 275-351 | `_init_empty_files()` creates 6 different file types with hardcoded content — file initialization is a separate concern from campaign CRUD | Medium |
| 2 | SRP | 30-75 | `list_campaigns()` reads and formats campaign metadata including character data — mixing listing with data aggregation | Medium |
| 3 | SRP | 202-261 | `get_info()` duplicates data-reading logic from `list_campaigns()` with more detail — DRY violation | Medium |
| 4 | OCP | 284-306 | Campaign overview template is hardcoded with default values (genre: "Fantasy", tone percentages) — not configurable | Medium |
| 5 | DIP | 47-55, 60-63, 226-229, 233-240, 243-254 | Repeated pattern of raw `open()` + `json.load()` instead of using a shared JSON utility | Medium |
| 6 | SRP | 353-453 | CLI parsing (~100 LOC) in same file as domain logic | Medium |
| 7 | OCP | 307-351 | Hardcoded list of state files (npcs.json, locations.json, facts.json, consequences.json) — adding a new entity type requires modifying this method | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 289: `"Fantasy"` — default genre hardcoded
- Lines 290-293: `{"horror": 30, "comedy": 30, "drama": 40}` — default tone percentages hardcoded
- Line 295: `"1st of the First Month, Year 1"` — default date hardcoded
- Line 296: `"Morning"` — default time hardcoded
- Line 403: `{'':2}{'NAME':20}{'CHARACTER':25}{'SESSIONS':10}` — column widths hardcoded
- Line 405: `"-" * 60` — separator width hardcoded

---

### 1.5 TimeManager (258 LOC) — `lib/time_manager.py`

**Overall Assessment:** Medium severity. Relatively focused but has coupling issues.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DIP | 20-26 | Creates `CampaignManager` and `JsonOperations` directly — same hard-dependency pattern as EntityManager but doesn't inherit from it (code duplication) | Medium |
| 2 | SRP | 181-203 | `_print_time()` — presentation/formatting logic with ANSI colors embedded in domain class | Medium |
| 3 | OCP | 118-133 | Two branches for time advancement (with calendar vs without) — not extensible for other time systems | Medium |
| 4 | DIP | 41-42, 71-72, 119, 194 | Conditional `from lib.calendar import ...` inside methods — fragile dependency on calendar module availability | Medium |
| 5 | ISP | 20-26 | Does not inherit from `EntityManager` despite needing the same initialization pattern — duplicates campaign resolution logic | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 54: `"08:00"` — default time fallback (appears 3 times: lines 54, 58, 174)
- Line 127: `24` — hours per day hardcoded (not calendar-aware in fallback path)
- Line 155: `24 * 60` — minutes per day hardcoded
- Line 156: `60.0` — minutes per hour hardcoded

---

## Summary: Cross-Cutting Issues

### 1. CLI in Domain Files (All 5 Managers)
Every manager bundles `main()` CLI parsing (95-160 LOC each) in the same file as domain logic. Total: ~510 LOC of CLI code mixed with domain code. This violates SRP and makes domain classes harder to test and reuse.

### 2. Console Output in Domain Methods (PlayerManager, SessionManager, CampaignManager)
`print()` calls scattered throughout business logic methods. Domain methods should return data; presentation should be handled by the CLI layer.

### 3. Hard Dependencies via Constructor (All 5 Managers)
No dependency injection — all managers create their dependencies (CampaignManager, JsonOperations) internally. This makes unit testing require filesystem setup instead of mocks.

### 4. Duplicated Legacy Format Support (PlayerManager, SessionManager)
Both managers independently implement dual-path character loading (single `character.json` vs `characters/` directory). This migration logic is duplicated and should be centralized.

### 5. Hardcoded D&D 5e Rules (PlayerManager)
XP thresholds, level cap (20), bloodied threshold (25% HP) are all D&D 5e specific. The system claims to be a general DM tool but has game-system-specific constants baked into core code.

### Severity Distribution

| Severity | Count |
|----------|-------|
| High | 10 |
| Medium | 22 |
| Low | 6 |
| **Total** | **38** |

---

## Section 2: Utility Modules

---

### 2.1 JsonOperations (284 LOC) — `lib/json_ops.py`

**Overall Assessment:** Medium severity. Repetitive nested-path navigation duplicated across 5 methods.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DRY | 74-80, 103-109, 135-141, 155-161, 178-184 | Identical nested-path navigation loop (`for key in path: current = current[key]`) copy-pasted across `update_json`, `append_to_list`, `check_exists`, `get_value`, `delete_key` — 5 copies of the same 6-line block | High |
| 2 | SRP | 211-284 | CLI `main()` with argparse (~73 LOC) bundled in same file as domain class | Medium |
| 3 | SRP | 36-41, 60, 115, 122 | `print()` error output in domain class — error reporting mixed with business logic; should raise exceptions or use logging | Medium |
| 4 | OCP | 14-19 | `JsonOperations` is hardwired to filesystem JSON via `Path` — cannot swap to in-memory or DB storage without modifying the class | Medium |
| 5 | DIP | 17-19 | Constructor creates `Path` and calls `mkdir` directly — infrastructure concern baked into domain class | Low |

**Magic Numbers / Hardcoded Values:**
- Line 62: `.tmp` suffix for atomic write temp files
- Line 17: `"world-state"` default directory name

**Refactoring Opportunity:** Extract a `_navigate_path(data, path)` helper to eliminate 5× duplicated navigation blocks (~30 LOC saved).

---

### 2.2 Validators (303 LOC) — `lib/validators.py`

**Overall Assessment:** High severity. Worst DRY violation in the codebase — 9 validation methods with identical structure.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DRY | 36-228 | **9 methods** follow identical pattern: `input.lower().strip()` → check `not in valid_list` → return error with `join()`. Methods: `validate_attitude` (36-50), `validate_damage_type` (75-91), `validate_skill` (93-111), `validate_alignment` (113-134), `validate_condition` (136-153), `validate_ability` (155-169), `validate_quest_priority` (171-183), `validate_time_of_day` (185-200), `validate_plot_type` (202-214), `validate_plot_status` (216-228) — ~150 LOC that could be 1 generic method + data | High |
| 2 | OCP | 41-44, 81-85, 99-105, 119-124, 142-147, 161, 177, 191-194, 208, 222 | Valid value lists hardcoded inside each method — adding a new attitude/condition/skill requires modifying the class. Should be data-driven (external config or class-level registry) | High |
| 3 | SRP | 230-242 | `escape_for_json()` — JSON encoding concern mixed with input validation class | Medium |
| 4 | SRP | 244-258 | `sanitize_path()` — filesystem security concern mixed with input validation class | Medium |
| 5 | SRP | 261-304 | CLI `main()` (~43 LOC) bundled in domain file | Low |
| 6 | OCP | 69-71 | `valid_die_sizes = [4, 6, 8, 10, 12, 20, 100]` hardcoded — D&D-specific, not extensible | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 25: `100` max name length
- Lines 66-67: `1-100` dice count range
- Line 69: `[4, 6, 8, 10, 12, 20, 100]` valid die sizes (D&D-specific)
- Lines 41-44: 10 hardcoded attitudes
- Lines 81-84: 13 hardcoded damage types (D&D 5e)
- Lines 99-105: 18 hardcoded skills (D&D 5e)
- Lines 142-147: 15 hardcoded conditions (D&D 5e)

**Refactoring Opportunity:** Replace 9 identical methods with `_validate_enum(value, valid_set, label)` + a `VALID_VALUES` dict. Reduces ~150 LOC to ~20 LOC.

---

### 2.3 Currency (234 LOC) — `lib/currency.py`

**Overall Assessment:** Medium severity. Two nearly-identical formatting functions are the main issue.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DRY | 50-73 vs 76-100 | `format_money()` and `format_money_long()` are near-duplicates — same algorithm, only differ in using `symbol` vs `name` field. Should be one function with a `use_long_names` parameter | High |
| 2 | SRP | 100-133 | `parse_money()` handles 3 distinct parsing strategies (int, float, regex) in one method — should be a chain of parsers | Medium |
| 3 | Error | 39-40 | `except (json.JSONDecodeError, IOError): pass` — silently swallows config load errors with no logging | Medium |
| 4 | Error | 110-117 | Two bare `except: pass` blocks that silently swallow int/float conversion failures | Medium |
| 5 | DIP | 23-41 | `load_config()` reads filesystem directly — not injectable for testing | Low |

**Magic Numbers / Hardcoded Values:**
- Lines 13-20: `DEFAULT_CONFIG` with D&D-specific cp/sp/gp denominations
- Line 121: Regex pattern `r'([\d.]+)\s*([a-zA-Z]+)'` for money parsing

**Refactoring Opportunity:** Merge `format_money` and `format_money_long` into one function with a `style` parameter (~25 LOC saved).

---

### 2.4 Calendar (258 LOC) — `lib/calendar.py`

**Overall Assessment:** Medium severity. Core algorithm is sound but `advance_days` is complex and magic numbers abound.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | SRP | 129-164 | `advance_days()` — 36-line method handling forward advancement, backward advancement, month rollover, and year rollover in one function. High cyclomatic complexity | Medium |
| 2 | OCP | 60-92 | `parse_date()` uses regex + loop to match month names — fragile string parsing that breaks with non-standard formats | Medium |
| 3 | DRY | 139-150 vs 152-163 | Forward and backward day advancement are separate code paths with mirrored logic — could be unified with a direction multiplier | Medium |
| 4 | Error | 87 | `ValueError` raised on invalid month but no handling in callers (`advance_hours` at line 172 where `parse_date` is called) | Low |

**Magic Numbers / Hardcoded Values:**
- Line 114: `0` default for `year_zero_weekday`
- Lines 175-176: `24 * 60` (minutes/day) and `60.0` (minutes/hour) not named constants
- Line 127: `24` hours per day hardcoded in fallback

---

### 2.5 Colors (314 LOC) — `lib/colors.py`

**Overall Assessment:** Low-medium severity. Presentation-only module; violations are less impactful than domain modules.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DRY | 58-72 | 4 `tag_*()` functions (`tag_success`, `tag_error`, `tag_info`, `tag_warning`) with identical structure: `f"{BOLD_X}[TAG]{RESET}"` + optional text. Should be one `_tag(color, label, text)` helper | Medium |
| 2 | OCP | 14-53 | 40+ ANSI escape codes as class attributes — not data-driven, no theme support, no `NO_COLOR` env var support | Medium |
| 3 | SRP | 90-133 | `hp_bar()` — HP visualization logic (health percentage, color thresholds, bar rendering) in a color utility class. This is a UI widget, not a color concern | Medium |
| 4 | SRP | 136-220 | Combat formatting methods (`format_roll`, `format_attack`, `format_damage`, `format_save`) — domain-specific presentation mixed with generic color utilities | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 105: `width=12` default bar width
- Line 123: `0.5` and `0.25` HP color thresholds (50%, 25%)
- Lines 179-186: Success/failure text hardcoded across multiple branches

---

### 2.6 ModuleData (80 LOC) — `.claude/additional/infrastructure/module_data.py`

**Overall Assessment:** Low severity. Small utility with minor coupling issues.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DIP | 22, 69 | Hardcoded `"module-data"` directory and `"active-campaign.txt"` filename — infrastructure paths baked in | Medium |
| 2 | Error | 48 | Generic `except Exception` with `print()` instead of logging — swallows save errors | Medium |
| 3 | Error | 37-38 | `load()` returns `{}` silently on missing file — caller cannot distinguish "empty data" from "file not found" | Low |
| 4 | DRY | 66-78 | `_find_campaign_dir()` duplicates project-root-finding logic from encounter_engine and other modules | Low |

**Magic Numbers / Hardcoded Values:**
- Line 22: `"module-data"` directory name
- Line 69: `"active-campaign.txt"` filename
- Line 70: `"world-state"` directory name

---

### 2.7 EncounterEngine (227 LOC) — `lib/encounter_engine.py`

**Overall Assessment:** High severity. God function with side effects, magic numbers, and duplicated infrastructure code.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | SRP | 115-188 | `check_encounter()` — 73-line god function handling: time tracking, probability calculation, dice rolling, encounter filtering, creature selection, and file persistence. At least 4 responsibilities | High |
| 2 | SRP | 30-41 | `_find_project_root()` and `_get_active_campaign_dir()` — duplicates campaign-finding logic from module_data.py and other modules | Medium |
| 3 | OCP | 157-165 | Encounter probability is a fixed d100 roll with hardcoded defaults — no way to plug in alternative probability systems | Medium |
| 4 | DIP | 15-27 | `sys.path.insert(0, ...)` + direct color constant assignment — runtime path manipulation and tight coupling to Colors class internals | Medium |
| 5 | SRP | 44-49 | Direct `json.load()`/`json.dump()` file I/O duplicating JsonOperations functionality | Medium |
| 6 | Error | 47-48, 63 | Silent failures returning empty dicts on file errors — no logging | Low |

**Magic Numbers / Hardcoded Values:**
- Line 136: `15` default chance_per_hour
- Line 137: `2` default min_hours_between encounters
- Line 160: `100` for d100 roll
- Line 31: `.git` directory used for project root detection

---

### 2.8 ExtractionSchemas (179 LOC) — `lib/extraction_schemas.py`

**Overall Assessment:** Medium severity. Schema definitions are repetitive; validation function violates OCP.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DRY | 7-118 | 7 schema dicts with repeated `"source": ""` field and similar structure — no base schema or schema factory | Medium |
| 2 | OCP | 135-163 | `validate_extraction()` uses if-elif chain for schema-specific validation (NPC attitude check, item rarity check) — adding a new schema type requires modifying this function | High |
| 3 | DRY | 152-156 | Attitude enum hardcoded again (duplicates `validators.py` lines 41-44) | Medium |
| 4 | DRY | 158-161 | Rarity enum hardcoded (duplicates values likely defined elsewhere) | Medium |
| 5 | SRP | 135-163 | Generic validation + schema-specific validation in one function — schema-specific rules should live with their schemas | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 153: `100` character limit for name (duplicates validators.py line 25)
- Lines 155: Attitude list duplicated from validators.py

---

### 2.9 ContentExtractor (294 LOC) — `lib/content_extractor.py`

**Overall Assessment:** Medium severity. God classes for PDF/Docx extraction with duplicated patterns.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DRY | 69-83 vs 85-103 | `_extract_pdfplumber()` and `_extract_pypdf2()` — near-identical page iteration loops differing only in library API calls | Medium |
| 2 | SRP | 13-103 | `PDFExtractor` handles library detection (21-33), dispatch (38-67), and two extraction implementations (69-103) — should be strategy pattern with one extractor per library | Medium |
| 3 | Error | 56, 65, 81, 101, 193-201 | Print-based error reporting with exception swallowing — cascading fallbacks without structured error handling | Medium |
| 4 | OCP | 247-255 | File extension → extractor mapping hardcoded in `extract_content()` — adding new format requires modifying this function | Medium |
| 5 | DIP | 21-33 | Runtime `import` with try/except in constructor — library availability becomes hidden state | Low |
| 6 | SRP | 189-201 | `_basic_extract()` is a "very basic fallback that may not work well" (comment on line 189) — acknowledged technical debt | Low |

**Magic Numbers / Hardcoded Values:**
- Line 198: Regex `r'[^\x20-\x7E\n\r\t]'` for printable char filtering (unexplained)
- Line 126: `\n{3,}` regex for whitespace normalization
- Line 174: `' | '` table cell separator
- Lines 220-232: 4 encoding attempts (`utf-8`, `latin-1`, `cp1252`, `ascii`) hardcoded

---

## Section 2 Summary: Cross-Cutting Issues

### 1. Extreme DRY Violations (Validators, JsonOperations)
`validators.py` has 9 copy-pasted validation methods (~150 LOC) that differ only in the valid-values list. `json_ops.py` has 5 copies of the same path-navigation loop. Combined: ~180 LOC of pure duplication.

### 2. Duplicated Infrastructure Patterns (EncounterEngine, ModuleData)
Project-root detection, active-campaign lookup, and raw JSON file I/O are re-implemented independently in multiple modules instead of using shared utilities.

### 3. Silent Error Swallowing (Currency, ModuleData, EncounterEngine, ContentExtractor)
`except: pass` and `except Exception: print()` patterns throughout — callers cannot distinguish errors from empty/default data.

### 4. D&D 5e Hardcoding (Validators, Currency, ExtractionSchemas)
Damage types, conditions, skills, abilities, die sizes, and currency denominations are all hardcoded D&D 5e values. The system claims game-system-agnostic design but utility modules bake in D&D assumptions.

### 5. CLI in Domain Files (JsonOperations, Validators)
Same anti-pattern as manager modules — `main()` with argparse in domain files.

### Section 2 Severity Distribution

| Severity | Count |
|----------|-------|
| High | 7 |
| Medium | 27 |
| Low | 8 |
| **Total** | **42** |

### Combined Severity (Sections 1 + 2)

| Severity | Section 1 | Section 2 | Total |
|----------|-----------|-----------|-------|
| High | 10 | 7 | 17 |
| Medium | 22 | 27 | 49 |
| Low | 6 | 8 | 14 |
| **Total** | **38** | **42** | **80** |

---

## Section 3: RAG Subsystem

Six modules in `lib/rag/` (~1,423 LOC) implementing semantic search over campaign documents. Optional dependencies: `sentence-transformers` (embedder), `chromadb` (vector store).

---

### 3.1 Embedder (176 LOC) — `lib/rag/embedder.py`

**Overall Assessment:** Medium severity. Stderr suppression is the main concern; otherwise clean with good lazy-loading.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | Error | 52-60 | `sys.stderr = io.StringIO()` — suppresses ALL stderr during model loading, including genuine errors. If `SentenceTransformer()` fails, the error message is silently discarded. Only the exception propagates without its stderr context | High |
| 2 | SRP | 15-21 | Module-level side effects: sets 3 env vars (`HF_HUB_DISABLE_PROGRESS_BARS`, `TOKENIZERS_PARALLELISM`) and configures 3 loggers at import time — affects global process state as a side effect of importing this module | Medium |
| 3 | SRP | 144-176 | `main()` test harness (~33 LOC) bundled in domain file | Low |
| 4 | OCP | 27 | `DEFAULT_MODEL = "all-MiniLM-L6-v2"` — model name hardcoded as class constant. Acceptable for a default, but no validation or fallback if model unavailable | Low |

**Magic Numbers / Hardcoded Values:**
- Line 27: `"all-MiniLM-L6-v2"` default model name
- Line 75: `batch_size: int = 32` default batch size

**Optional Dependency Handling:** Good — `is_available()` static method (lines 40-47) checks for `sentence_transformers` import. However, `_ensure_model()` (line 57) imports `SentenceTransformer` without checking `is_available()` first, so callers must check availability themselves or face an unguarded `ImportError`.

---

### 3.2 SemanticChunker (262 LOC) — `lib/rag/semantic_chunker.py`

**Overall Assessment:** Medium severity. Hardcoded threshold and tight coupling to extraction_queries.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | OCP | 19 | `DEFAULT_THRESHOLD = 0.35` — similarity threshold hardcoded. This is a tuning parameter that significantly affects categorization behavior, with no guidance on how to adjust it per corpus or model | Medium |
| 2 | DIP | 12-13 | Hard-imports `LocalEmbedder` and `EXTRACTION_QUERIES` — tightly coupled to specific embedder and query definitions. Cannot swap embedder implementation or query set without modifying this file | Medium |
| 3 | SRP | 44, 56 | `print()` calls during initialization — progress reporting mixed with domain logic. Should use logging or a callback | Medium |
| 4 | DRY | 73-78 vs 183-186 | `score_chunk()` and `categorize_chunks()` both compute category similarity via `self.embedder.similarity(chunk_emb, category_embedding)` — duplicated scoring loop | Medium |
| 5 | SRP | 81-113 | `score_chunk_detailed()` returns a complex nested dict with both summary and per-query scores — mixes summary and detailed analysis in one method | Low |
| 6 | SRP | 222-262 | `main()` test harness (~40 LOC) bundled in domain file | Low |

**Magic Numbers / Hardcoded Values:**
- Line 19: `0.35` default similarity threshold
- Line 145: `"general"` fallback category name (appears 3 times: lines 145, 178, 196)

**Coupling Note:** `SemanticChunker` creates `LocalEmbedder()` internally if none provided (line 33). Constructor accepts optional injection, which is good, but the default path creates a concrete dependency.

---

### 3.3 VectorStore (307 LOC) — `lib/rag/vector_store.py`

**Overall Assessment:** Medium severity. Clean ChromaDB wrapper with good lazy-loading, but has coupling and error handling gaps.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | DIP | 47-48 | Hard-imports `chromadb` and `chromadb.config.Settings` inside method — no abstraction layer. Cannot swap to FAISS or other vector DB without rewriting this class | Medium |
| 2 | OCP | 51-57 | ChromaDB client configuration hardcoded: `anonymized_telemetry=False`, `allow_reset=True`, `hnsw:space: "cosine"` — not configurable per use case | Medium |
| 3 | DRY | 149-153 | Result flattening pattern (`results["ids"][0] if results["ids"] else []`) repeated 4 times for ids/documents/metadatas/distances | Low |
| 4 | SRP | 216-228 | `count_by_category()` fetches ALL metadatas to count categories — inefficient for large stores, and data aggregation logic in a storage class | Medium |
| 5 | SRP | 240-248 | `persist()` is a no-op method with a comment explaining it does nothing — dead code kept "for future compatibility" | Low |
| 6 | SRP | 263-307 | `main()` test harness (~44 LOC) bundled in domain file | Low |

**Magic Numbers / Hardcoded Values:**
- Line 17: `"document_chunks"` default collection name
- Line 62: `"cosine"` hardcoded distance metric
- Line 93: `f"chunk_{current_count + i}"` — ID generation scheme hardcoded
- Line 182: `limit: int = 100` default query limit

**Optional Dependency Handling:** Good — `is_available()` static method (lines 36-42). Same gap as embedder: `_ensure_client()` imports chromadb without guarding, so callers must check `is_available()` first.

---

### 3.4 RAGExtractor (275 LOC) — `lib/rag/rag_extractor.py`

**Overall Assessment:** Medium severity. Pipeline orchestrator with excessive print statements and tight coupling.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | SRP | 71-72, 82, 84, 89, 91, 94, 100, 103, 107, 119 | 10+ `print()` calls throughout `extract_from_document()` — progress reporting mixed with extraction logic. Should use logging or a callback/observer | Medium |
| 2 | DIP | 19-20 | Hard-imports `LocalEmbedder` and `CampaignVectorStore` — pipeline is hardwired to specific implementations | Medium |
| 3 | DIP | 168 | `from lib.content_extractor import ContentExtractor` — lazy import inside method creates hidden dependency on content_extractor module | Medium |
| 4 | SRP | 173-208 | `_split_into_chunks()` — text chunking logic (regex-based header splitting + paragraph fallback) embedded in the extractor class. This is a separate responsibility that could be its own chunker | Medium |
| 5 | OCP | 178 | Header pattern regex `r'^(?:#{1,3}\s+.+|[A-Z][A-Z\s]+:|Chapter \d+|PART [IVX]+)'` hardcoded — only handles markdown/book-style headers, not extensible for other formats | Medium |
| 6 | SRP | 248-275 | `main()` CLI (~27 LOC) bundled in domain file | Low |

**Magic Numbers / Hardcoded Values:**
- Line 27: `3000` default chunk size
- Line 97: `batch_size=32` hardcoded in embed call
- Line 125: `n_results: int = 20` default query results
- Line 244: `f"doc_{i:04d}"` — ID format hardcoded

**Note:** `RAGExtractor` duplicates chunking logic that `SemanticChunker` also handles — the two classes have overlapping responsibilities with different approaches (regex splitting vs semantic scoring).

---

### 3.5 QuoteExtractor (226 LOC) — `lib/rag/quote_extractor.py`

**Overall Assessment:** Medium severity. Tight coupling to NPC file format and hardcoded similarity thresholds.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | SRP | 135-193 | `enrich_all_npcs()` reads `npcs.json`, queries vectors, merges context, deduplicates, and writes back — at least 4 responsibilities in one method | High |
| 2 | OCP | 85 | `distance > 1.3` — hardcoded distance threshold for filtering results. This cosine distance cutoff is model-specific and not configurable | Medium |
| 3 | OCP | 80 | `doc[:200].lower()` — deduplication key uses first 200 chars, a magic number that affects dedup accuracy | Medium |
| 4 | OCP | 99 | `passages[:10]` — hardcoded limit of 10 passages per NPC | Medium |
| 5 | OCP | 180 | `all_context[:15]` — hardcoded limit of 15 total context entries per NPC | Medium |
| 6 | DIP | 40-41 | Lazy import of `CampaignVectorStore` and `LocalEmbedder` — same hidden dependency pattern as other RAG modules | Low |
| 7 | SRP | 127-133 | `extract_voice_for_npc()` legacy compatibility wrapper — dead API surface adding maintenance burden | Low |
| 8 | SRP | 196-226 | `main()` CLI (~30 LOC) bundled in domain file | Low |

**Magic Numbers / Hardcoded Values:**
- Line 46: `n_results: int = 15` default results per query
- Line 80: `200` chars for deduplication key
- Line 85: `1.3` distance threshold
- Line 99: `10` max passages returned
- Line 101: `max_length: int = 500` passage cap
- Line 119: `max_length // 2` minimum break point for truncation
- Line 172: `100` chars for merge deduplication key
- Line 180: `15` max total context entries

---

### 3.6 ExtractionQueries (177 LOC) — `lib/rag/extraction_queries.py`

**Overall Assessment:** Low severity. Pure data module with minimal logic. Main issue is hardcoded D&D/fantasy-specific query templates.

| # | Principle | Lines | Violation | Severity |
|---|-----------|-------|-----------|----------|
| 1 | OCP | 14-125 | `EXTRACTION_QUERIES` dict with 5 content types and ~60 query strings hardcoded — not configurable per campaign genre (all queries assume fantasy/D&D setting: "dungeon", "castle", "AC HP hit points", "gp sp cp") | Medium |
| 2 | OCP | 128-156 | Utility functions (`get_queries_for_type`, `get_all_types`, `get_combined_queries`) operate on the module-level constant — no way to pass custom queries without modifying this file | Medium |
| 3 | SRP | 159-177 | `main()` display function (~18 LOC) bundled in domain file | Low |

**Magic Numbers / Hardcoded Values:**
- Lines 14-125: 5 content type categories with ~60 query templates (all D&D/fantasy themed)
- Line 166: `queries[:3]` — display limit of 3 queries in main()

---

## Section 3 Summary: Cross-Cutting Issues

### 1. Stderr/Output Suppression (Embedder)
`sys.stderr` replacement (embedder.py lines 52-60) is the highest-severity issue. It silently discards all stderr output during model loading, hiding genuine errors. Module-level env var and logger manipulation (lines 15-21) also affects global state at import time.

### 2. Hardcoded Thresholds Without Guidance
- Similarity threshold `0.35` (semantic_chunker.py line 19)
- Distance threshold `1.3` (quote_extractor.py line 85)
- Dedup key length `200` chars (quote_extractor.py line 80)
- Various passage limits (`10`, `15`, `500` chars)

These are model-specific tuning parameters with no documentation on how they were derived or how to adjust them for different models or corpora.

### 3. Optional Dependency Pattern: Consistent but Incomplete
All modules with optional deps (`embedder`, `vector_store`) provide `is_available()` static methods, which is good. However, the internal `_ensure_*` methods do NOT check availability before importing — they will raise raw `ImportError` if the dependency is missing. There's a gap between the public "check if available" API and the internal "just import and hope" pattern.

### 4. Print-Based Progress Reporting (All 6 Modules)
Every module uses `print()` for progress output, including the domain-layer classes. The `rag_extractor.py` is worst with 10+ print calls in `extract_from_document()`. Should use `logging` or a progress callback.

### 5. CLI in Domain Files (All 6 Modules)
Every module has a `main()` function with CLI code. Total: ~192 LOC of test/CLI code in domain files.

### 6. D&D/Fantasy Hardcoding (ExtractionQueries)
All 60 query templates assume fantasy RPG content (dungeons, castles, AC/HP, gold/silver). Not usable for sci-fi, modern, or other genres without modifying the module.

### 7. Coupling Between RAG Components
`RAGExtractor` → `LocalEmbedder` + `CampaignVectorStore` + `ContentExtractor` (3 hard deps)
`SemanticChunker` → `LocalEmbedder` + `EXTRACTION_QUERIES` (2 hard deps)
`QuoteExtractor` → `CampaignVectorStore` + `LocalEmbedder` (2 hard deps, lazy)

No interfaces or abstractions — swapping any component requires modifying its dependents.

### Section 3 Severity Distribution

| Severity | Count |
|----------|-------|
| High | 2 |
| Medium | 20 |
| Low | 10 |
| **Total** | **32** |

### Combined Severity (Sections 1 + 2 + 3)

| Severity | Section 1 | Section 2 | Section 3 | Total |
|----------|-----------|-----------|-----------|-------|
| High | 10 | 7 | 2 | 19 |
| Medium | 22 | 27 | 20 | 69 |
| Low | 6 | 8 | 10 | 24 |
| **Total** | **38** | **42** | **32** | **112** |

---

## Section 4: Optional Modules

**Scope:** 3 optional gameplay modules totaling ~6,909 LOC across 15 lib files, 2 middleware scripts, 4 tool scripts, and 6 test files.

---

### 4.1 World-Travel Module (~5,024 LOC, 13 lib files)

**Overall Assessment:** Medium severity. Well-architected multi-component module with clear internal separation. Main issues are campaign-language leaks (Russian compass names) and fragile middleware output parsing.

#### Campaign-Agnosticism Violations

| # | File | Lines | Violation | Severity |
|---|------|-------|-----------|----------|
| 1 | lib/pathfinding.py | 24-39 | `COMPASS_DIRECTIONS` hardcodes Russian compass names: `"Север"`, `"Восток"`, `"Юг"`, `"Запад"` etc. — violates CLAUDE.md rule that module code must be campaign-agnostic. English abbreviations ("N", "E") exist but Russian names are primary display values | High |

#### SOLID Violations

| # | Principle | File | Lines | Violation | Severity |
|---|-----------|------|-------|-----------|----------|
| 2 | DIP | lib/vehicle_manager.py | 19-27 | Hard-imports `HierarchyManager` — vehicle system silently requires hierarchy component; no graceful fallback if removed | Medium |
| 3 | DIP | lib/navigation_manager.py | 31-32 | Concrete imports of `PathFinder` and `PathManager` — tight coupling chain: NavigationManager → PathManager → PathFinder | Medium |
| 4 | SRP | middleware/dm-session.sh | 70-97 | Extracts structured data (distance_meters, terrain) from navigation output via regex on stdout — fragile coupling between tool output format and middleware parsing | Medium |
| 5 | SRP | middleware/dm-session.sh | 99-118 | Middleware reads campaign JSON directly (`campaign-overview.json`) to get `previous_location` — bypasses CORE tools, duplicates state-reading logic | Medium |
| 6 | OCP | lib/encounter_engine.py | 70-86 | Time-of-day DC modifiers keyed by fixed strings ("Morning", "Day", "Evening", "Night") — not extensible for alternative time systems | Low |
| 7 | OCP | lib/force_layout.py | 6 | Global `_cache` dict for layout positions with no invalidation strategy — stale layouts persist if locations change | Low |
| 8 | DIP | All 13 lib files | — | Every class creates `CampaignManager` / `JsonOperations` directly — same hard-dependency pattern as CORE managers | Medium |

**Middleware Correctness:**
- `dm-location.sh`: Clean routing, no state mutations, correctly exits 1 to pass unhandled actions to CORE ✓
- `dm-session.sh`: Correctly chains hierarchy → vehicle → navigation → encounter ✓
  - **Issue:** Line 67: `[ $NAV_RC -eq 0 ] || exit 0` — navigation errors are masked. Exit 0 signals "handled" to CORE even on failure, preventing error propagation
  - **Issue:** Lines 70-97: Regex extraction of JSON from stdout is fragile — any change to navigation output format breaks encounter auto-check

**Inter-Module Dependencies:** Internal only (vehicle → hierarchy → pathfinding). No cross-module dependencies to mass-combat or firearms-combat ✓

---

### 4.2 Mass-Combat Module (~1,201 LOC, 1 lib file)

**Overall Assessment:** Low-medium severity. Standalone module with no middleware — cleanest isolation. Main issue is Russian faction name aliases.

#### Campaign-Agnosticism Violations

| # | File | Lines | Violation | Severity |
|---|------|-------|-----------|----------|
| 1 | lib/mass_combat_engine.py | 50-52 | `faction_color()` hardcodes Russian faction aliases: `"враги"` (enemies), `"союзники"` (allies) — language-specific strings in module code violates campaign-agnosticism rule | Medium |
| 2 | tests/test_mass_combat.py | 65, 83 | Test uses Russian unit name `"Хантер"` — campaign-language assumption in test data | Low |

#### SOLID Violations

| # | Principle | File | Lines | Violation | Severity |
|---|-----------|------|-------|-----------|----------|
| 3 | SRP | lib/mass_combat_engine.py | 95-99 | `_save()` writes JSON directly without atomic write (no temp file + rename) — data integrity concern under process interruption | Low |
| 4 | DIP | lib/mass_combat_engine.py | 87-93 | `_load()` does raw file I/O without structure validation — corrupted state file causes unhandled exceptions | Medium |
| 5 | OCP | lib/mass_combat_engine.py | 48-54 | Faction color mapping is a closed if-chain — cannot add new factions (neutral, hostile, civilian) without modifying the method | Low |
| 6 | DIP | lib/mass_combat_engine.py | 56-62 | Creates `CampaignManager` and `ModuleDataManager` directly in constructor — same hard-dependency pattern | Medium |

**Middleware Correctness:** N/A — module declares `"middleware": []` and has no middleware directory. Fully standalone tool ✓

**Inter-Module Dependencies:** None. Only depends on CORE (`CampaignManager`, `ModuleDataManager`) ✓

---

### 4.3 Firearms-Combat Module (~684 LOC, 1 lib file)

**Overall Assessment:** High severity due to campaign-specific content leak. Hardcoded Russian subclass name `"Стрелок"` in production code directly violates the mandatory campaign-agnosticism rule.

#### Campaign-Agnosticism Violations

| # | File | Lines | Violation | Severity |
|---|------|-------|-----------|----------|
| 1 | lib/firearms_resolver.py | 90 | **Critical:** `if self.character.get("subclass") == "Стрелок"` — hardcoded Russian subclass name ("Sharpshooter") in production resolver. Grants +2 attack bonus only to this specific campaign's subclass name | **High** |
| 2 | lib/firearms_resolver.py | 96-97 | `_is_sharpshooter()` method: `return self.character.get("subclass") == "Стрелок"` — same hardcoded check as a dedicated method | **High** |
| 3 | lib/firearms_resolver.py | 549 | Display string includes `"(Стрелок subclass)"` — Russian in user-facing output | Medium |
| 4 | tests/test_firearms_resolver.py | 30 | Test fixture uses `"subclass": "Стрелок"`, `"class": "Сталкер"` — STALKER-campaign-specific test data | Medium |
| 5 | creation-rules.md | 127 | Documentation hardcodes `char['subclass'] = 'Стрелок'` | Low |

#### SOLID Violations

| # | Principle | File | Lines | Violation | Severity |
|---|-----------|------|-------|-----------|----------|
| 6 | OCP | lib/firearms_resolver.py | 88-91 | Subclass bonus is a hardcoded if-check — no way to define other subclass bonuses without modifying the class | High |
| 7 | SRP | lib/firearms_resolver.py | 98-108 | Attack bonus always uses DEX modifier — no configuration for STR-based or WIS-based firearms | Medium |
| 8 | OCP | lib/firearms_resolver.py | 142-148 | Penetration vs protection scaling (full / half / quarter damage) hardcoded — cannot adjust balance per campaign | Medium |
| 9 | DIP | lib/firearms_resolver.py | 16-24 | `PROJECT_ROOT` discovery via `.git` parent traversal + `sys.path.insert` — fragile import mechanism shared with all modules | Low |

**Middleware Correctness:** N/A — no middleware directory, no middleware declared. Standalone tool called explicitly by DM ✓

**Inter-Module Dependencies:** None. Only depends on CORE (`JsonOperations`, `PlayerManager`, `CampaignManager`, `ModuleDataManager`) ✓

---

### Section 4 Summary

#### Campaign-Agnosticism Report

| Module | Violations | Worst Severity | Primary Issue |
|--------|-----------|----------------|---------------|
| world-travel | 1 | High | Russian compass direction names in pathfinding.py |
| mass-combat | 2 | Medium | Russian faction aliases in engine, Russian test data |
| firearms-combat | 5 | **High** | Hardcoded `"Стрелок"` subclass in production resolver |

**Total campaign-specific leaks: 8** — firearms-combat is the worst offender with production logic gated on a Russian string.

#### Middleware Correctness Report

| Module | Middleware Files | Pre-hook Semantics | Post-hook Semantics | Issues |
|--------|------------------|--------------------|---------------------|--------|
| world-travel | dm-session.sh, dm-location.sh | exit 0 = handled, exit 1 = pass to CORE | N/A (no .post files) | Regex stdout parsing fragile; errors masked by exit 0 |
| mass-combat | None | N/A | N/A | Clean — standalone tool |
| firearms-combat | None | N/A | N/A | Clean — standalone tool |

#### Inter-Module Dependency Report

No cross-module dependencies exist between the 3 optional modules. Each module depends only on CORE libraries. Within world-travel, internal dependencies form a clean DAG: vehicle → hierarchy → pathfinding ← navigation.

#### Severity Distribution (Section 4)

| Severity | Count |
|----------|-------|
| High | 5 |
| Medium | 12 |
| Low | 6 |
| **Total** | **23** |

### Combined Severity (Sections 1 + 2 + 3 + 4)

| Severity | Section 1 | Section 2 | Section 3 | Section 4 | Total |
|----------|-----------|-----------|-----------|-----------|-------|
| High | 10 | 7 | 2 | 5 | 24 |
| Medium | 22 | 27 | 20 | 12 | 81 |
| Low | 6 | 8 | 10 | 6 | 30 |
| **Total** | **38** | **42** | **32** | **23** | **135** |
