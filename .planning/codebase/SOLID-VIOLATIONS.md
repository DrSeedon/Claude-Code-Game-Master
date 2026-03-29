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
| 2 | SRP | 79-99 | `_read_module_time()` and `_read_module_date()` — reads custom-stats module data directly instead of going through a module API. Tight coupling to module internals | High |
| 3 | SRP | 169-179 | `_sync_to_module()` writes directly to `module-data/custom-stats.json` — cross-module file manipulation | High |
| 4 | SRP | 181-203 | `_print_time()` — presentation/formatting logic with ANSI colors embedded in domain class | Medium |
| 5 | OCP | 118-133 | Two branches for time advancement (with calendar vs without) — not extensible for other time systems | Medium |
| 6 | DIP | 41-42, 71-72, 119, 194 | Conditional `from lib.calendar import ...` inside methods — fragile dependency on calendar module availability | Medium |
| 7 | ISP | 20-26 | Does not inherit from `EntityManager` despite needing the same initialization pattern — duplicates campaign resolution logic | Medium |

**Magic Numbers / Hardcoded Values:**
- Line 54: `"08:00"` — default time fallback (appears 3 times: lines 54, 58, 174)
- Line 81: `"module-data" / "custom-stats.json"` — hardcoded module data path (appears 3 times: lines 81, 91, 171)
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
