# Codebase Concerns

**Analysis Date:** 2026-03-28

---

## Tech Debt

**Incomplete WorldGraph migration — dual data architecture:**
- Issue: The stated architecture is "all data in world.json via WorldGraph," but most lib/ modules still read/write the old flat JSON files directly. The migration is ~50% done — tools delegate to `world_graph.py`, but lib-level classes (`SessionManager`, `ConsequenceManager`, `InventoryManager`, `search.py`, `world_stats.py`, `entity_enhancer.py`) bypass WorldGraph entirely and read `npcs.json`, `locations.json`, `facts.json`, `consequences.json`, `character.json` directly.
- Files: `lib/session_manager.py` (lines 62–64, 100–102, 116, 146, 172–174, 209–265, 394), `lib/search.py` (all methods), `lib/world_stats.py` (all methods), `lib/entity_enhancer.py` (find_entity, apply_enhancements, list_unenhanced, count_dungeon_rooms)
- Impact: Two parallel data sources. Any data written via `world_graph.py` will not be visible to `session_manager.py` context/saves. Session saves (`dm-session.sh save`) snapshot the old flat files — they will silently miss everything stored in `world.json`. `dm-search.sh` reads only old flat files; `dm-overview.sh` reads only old flat files.
- Fix approach: Migrate `session_manager.py`, `search.py`, `world_stats.py` to read from WorldGraph. Or, as a shorter path, make `world_graph.py` populate compatibility shims to the flat files.

**`session_manager.py` save/restore is WorldGraph-unaware:**
- Issue: `create_save()` snapshots `npcs.json`, `locations.json`, `facts.json`, `consequences.json`, `character.json`. `restore_save()` writes those same files. No mention of `world.json`.
- Files: `lib/session_manager.py` lines 206–265
- Impact: Save/restore is a data-loss trap for campaigns fully migrated to WorldGraph.
- Fix approach: Include `world.json` in snapshot. Either serialize the full graph or use a WorldGraph export method.

**`campaign_manager.py` creates legacy flat files on new campaign init:**
- Issue: `_init_empty_files()` creates `npcs.json`, `locations.json`, `facts.json` for every new campaign. The WorldGraph migration doc says these are obsolete.
- Files: `lib/campaign_manager.py` lines 307–323
- Impact: New campaigns start with both old and new structures, perpetuating the split.
- Fix approach: Remove flat file creation; init only `world.json` and `campaign-overview.json`.

**`dm-reset.sh` resets only legacy flat files:**
- Issue: `reset_world` in `dm-reset.sh` writes `{}` to `npcs.json`, `locations.json`, `facts.json`, `consequences.json`. `world.json` is never touched.
- Files: `tools/dm-reset.sh` lines 68–81
- Impact: `dm-reset.sh world` does nothing to WorldGraph data. Player thinks campaign is wiped; it isn't.
- Fix approach: Add `rm -f "$WORLD_STATE_DIR/world.json"` to reset_world. Or call `world_graph.py reset`.

**`entity_enhancer.py` fully operates on dead files:**
- Issue: `find_entity()`, `apply_enhancements()`, `list_unenhanced()`, `count_dungeon_rooms()`, `get_dungeon_info()` all read/write `npcs.json`, `locations.json`, `items.json`, `plots.json`. These files are not created by WorldGraph.
- Files: `lib/entity_enhancer.py` lines 128–133, 393–398, 466–495, 597–606
- Impact: `dm-enhance.sh apply`, `dm-enhance.sh list-unenhanced`, `dm-enhance.sh dungeon-check` silently find nothing and write to nonexistent files in WorldGraph campaigns.
- Fix approach: Rewrite `find_entity()` to use `WorldGraph.search_nodes()`. Rewrite `apply_enhancements()` to use `WorldGraph.update_node()`.

**`wiki_manager.py` duplicates wiki functionality already in `world_graph.py`:**
- Issue: `wiki_manager.py` is a 442-line standalone class that reads/writes `wiki.json`. `world_graph.py` has a full wiki implementation (`wiki_add`, `wiki_show`, `wiki_list`, `wiki_search`, `wiki_recipe`) backed by `world.json`. `dm-wiki.sh` delegates to `world_graph.py`. The only consumer of `wiki_manager.py` is `inventory_manager.py` for `use` and `craft` subcommands.
- Files: `lib/wiki_manager.py`, `lib/inventory_manager.py` lines 1314–1323
- Impact: `dm-inventory.sh craft` and `dm-inventory.sh use` read from `wiki.json`; `dm-wiki.sh add` writes to `world.json`. A potion added via `dm-wiki.sh` is invisible to `dm-inventory.sh craft`.
- Fix approach: Remove `wiki_manager.py`. Rewrite `_craft_item()` and `_use_consumable()` in `inventory_manager.py` to read wiki nodes from `world.json`.

**`consequences.json` still used by `consequence_manager.py`, `session_manager.py`, `search.py`:**
- Issue: `consequence_manager.py` reads/writes `consequences.json`. `dm-consequence.sh` correctly delegates to `world_graph.py` (WorldGraph-native). Two separate consequence stores exist: consequences added via the tool go to `world.json`; anything using `ConsequenceManager` class goes to `consequences.json`.
- Files: `lib/consequence_manager.py` (all methods), `lib/session_manager.py` lines 437–461
- Impact: Session context output reads from `consequences.json`; actual consequences are in `world.json`. Session start will show "no pending consequences" even when there are some.
- Fix approach: Delete `consequence_manager.py`. Update `session_manager.py` to call WorldGraph for consequences.

**`search.py` and `world_stats.py` are dead-end legacy modules:**
- Issue: `search.py` (`WorldSearcher`) reads all data from flat JSON files. `world_stats.py` (`WorldStats`) counts entities from flat JSON files. Both are called directly from bash tools (`dm-search.sh`, `dm-overview.sh`, `dm-reset.sh`).
- Files: `lib/search.py`, `lib/world_stats.py`
- Impact: `dm-search.sh --world-only` returns empty results in WorldGraph campaigns. `dm-overview.sh` shows zero NPCs and locations.
- Fix approach: Rewrite both against WorldGraph or inline their logic into `world_graph.py` subcommands.

**`player_manager.py` and `session_manager.py` maintain dead legacy code paths:**
- Issue: Both classes contain full legacy `characters/` directory support. `_is_using_single_character()`, `_get_character_path()`, and several multi-branch load/save methods have entire else-branches for `characters/` directory. No known campaigns use `characters/` anymore (merged to `character.json`, now superseded by WorldGraph player node).
- Files: `lib/player_manager.py` lines 64–76, 110–200, `lib/session_manager.py` lines 37–41, 170–184
- Impact: Dead code adds maintenance burden and confusion.
- Fix approach: Remove `characters/` branches. Eventually migrate `player_manager.py` to WorldGraph.

**`common.sh` exports unused legacy file variables:**
- Issue: `tools/common.sh` sets `NPCS_FILE`, `LOCATIONS_FILE`, `FACTS_FILE`, `CONSEQUENCES_FILE`, `CHARACTER_FILE`. The only users of these are `dm-reset.sh` (which should use WorldGraph) and `benchmark-hybrid.sh`.
- Files: `tools/common.sh` lines 80–95
- Impact: Cosmetic — but reinforces false assumption that these files are canonical.

---

## Known Bugs

**`dm-reset.sh` leaves `world.json` intact:**
- Symptoms: Running `dm-reset.sh world` clears flat files but `dm-world.sh` still shows old data.
- Files: `tools/dm-reset.sh` lines 63–128
- Trigger: `dm-reset.sh world`
- Workaround: Manually `rm world-state/campaigns/<name>/world.json`

**Session context shows zero party members in WorldGraph campaigns:**
- Symptoms: `dm-session.sh context` shows `(none)` for party members even when NPCs exist.
- Files: `lib/session_manager.py` lines 394–432 — reads `npcs.json`, not `world.json`
- Trigger: Any WorldGraph campaign where party members are managed via `dm-npc.sh`
- Workaround: None at tool level

**`dm-search.sh` returns empty world-state results in WorldGraph campaigns:**
- Symptoms: `dm-search.sh "NPC name"` finds nothing in world state section.
- Files: `lib/search.py` — reads `npcs.json`, `locations.json`, `facts.json`, none of which exist in WorldGraph campaigns
- Trigger: All WorldGraph campaigns
- Workaround: Use `dm-world.sh search <query>` directly

**`dm-inventory.sh craft` silently fails in WorldGraph campaigns:**
- Symptoms: `dm-inventory.sh craft <item>` prints `[ERROR] '<item>' not found in wiki` even when the item was added via `dm-wiki.sh`.
- Files: `lib/inventory_manager.py` lines 1315–1322 — calls `WikiManager(wiki.json)`, but items are in `world.json`
- Trigger: Any wiki item added via `dm-wiki.sh` (which uses WorldGraph)
- Workaround: None at tool level

**Test runner collision on `test_encounter_engine.py`:**
- Symptoms: `uv run pytest` (without path argument) crashes at collection with `import file mismatch` error — two files with the same module name exist at `tests/` and `.claude/additional/modules/world-travel/tests/`.
- Files: `tests/test_encounter_engine.py`, `.claude/additional/modules/world-travel/tests/test_encounter_engine.py`
- Trigger: Running `uv run pytest` from project root without specifying `tests/`
- Workaround: Always run `uv run pytest tests/`

---

## Security Considerations

**Shell injection via unquoted user input in `dm-npc.sh`:**
- Risk: `attitude` and `hp` commands build JSON strings with raw shell variables: `"{\"attitude\": \"$2\"}"` and `"{\"hp_delta\": $2}"`. A value like `"friendly","evil":true` would produce invalid JSON; a value with `$(...)` or backticks could execute arbitrary commands.
- Files: `tools/dm-npc.sh` lines 137, 153
- Current mitigation: None
- Recommendations: Use `escape_json()` from `common.sh` for string values, or pass values as separate arguments to `world_graph.py` rather than building JSON inline.

**Python inline code in shell scripts with interpolated variables:**
- Risk: `dm-npc.sh` runs inline Python with `$1` and `$LIB_DIR` interpolated directly into `$PYTHON_CMD -c "... g._resolve_id('$1', 'npc') ..."`. An NPC name containing a single quote breaks Python syntax; names with `;import os;os.system(...)` execute arbitrary code.
- Files: `tools/dm-npc.sh` lines 113–118, 129–134, 145–150, `tools/dm-location.sh` lines 67–68
- Current mitigation: None
- Recommendations: Pass NPC name as an argv argument rather than string-interpolating into Python source code.

---

## Performance Bottlenecks

**`entity_enhancer.py` loads each entity file N times per search:**
- Problem: `find_entity()` iterates over up to 4 files in 3 passes (exact, substring, fuzzy). Each pass reloads the same JSON files via `json_ops.load_json()`. For large campaigns this is 12 file reads per `dm-enhance.sh find` call.
- Files: `lib/entity_enhancer.py` lines 128–197
- Cause: No caching, no single-pass search
- Improvement path: Cache loaded files in `__init__`, or delegate to `WorldGraph.search_nodes()` which loads once.

**`world_graph.py` does full load+save on every single write:**
- Problem: Every `add_node`, `update_node`, `inventory_add`, etc. loads the entire `world.json`, mutates it, and writes the whole file back. For a large campaign world.json with hundreds of nodes, every dice roll that writes player HP triggers a full serialize/deserialize cycle.
- Files: `lib/world_graph.py` — `_load()` and `_save()` called in every mutating method
- Cause: Simple design choice — no in-memory cache
- Improvement path: Add an in-memory cache with dirty-flag. Or accept current performance as fine for CLI usage.

---

## Fragile Areas

**`module_data.py` is in `.claude/additional/infrastructure/`, not `lib/`:**
- Files: `.claude/additional/infrastructure/module_data.py`
- Why fragile: `inventory_manager.py` hard-codes a relative path `../../.claude/additional/infrastructure` to add to `sys.path`. If directory layout changes or `.claude/` is reorganized, the import silently fails. The `.claude/` directory is a Claude-specific config area, not a Python package location.
- Safe modification: When adding new imports to `inventory_manager.py` or modules, always check that `_infra_dir` resolution is working first.
- Test coverage: Tests mock this away via fixture, so the path issue may not surface in CI.

**`lib/time_manager.py` reads `module-data/custom-stats.json` via hardcoded path:**
- Files: `lib/time_manager.py` lines 81, 91, 171
- Why fragile: Accesses `Path(self.campaign_dir) / "module-data" / "custom-stats.json"` directly, bypassing `ModuleDataManager`. If module-data location changes, time ticking silently stops decaying custom stats.
- Safe modification: Use `ModuleDataManager` API instead of raw path.

**`lib/dice.py` loads `character.json` directly for skill/save lookups:**
- Files: `lib/dice.py` lines 283–294
- Why fragile: `_load_character()` opens `character.json` directly. If the campaign migrates player data fully to `world.json`, all `--skill`, `--save`, `--attack` auto-lookups silently fail with "no character found."
- Safe modification: After WorldGraph migration, add a fallback to read from the player node in `world.json`.

**`lib/encounter_engine.py` reads from `wiki.json` for creature lookup:**
- Files: `lib/encounter_engine.py` lines 58–63, 84–103
- Why fragile: Random encounter creature resolution reads `wiki.json`. If all creatures are in `world.json`, encounters will never find a creature and always return `None` for creature details.
- Safe modification: Add a WorldGraph node lookup fallback in `_find_creature_by_type()`.

**Inline Python in bash with `$LIB_DIR` interpolation:**
- Files: `tools/dm-npc.sh` lines 113–118, 129–134, 145–150, `tools/dm-location.sh` lines 67–68
- Why fragile: `sys.path.insert(0,'$LIB_DIR')` — if `LIB_DIR` contains a space, this breaks. Single-quote NPC names break Python syntax silently (the `-c` block returns empty string, treated as "not found").
- Safe modification: Never add new inline Python blocks. Always call a proper Python script as subprocess.

---

## Scaling Limits

**`world.json` single-file design:**
- Current capacity: Functional up to a few thousand nodes
- Limit: Full load+save on every write; with 5000+ nodes and large `data` blobs, startup latency for every tool invocation becomes noticeable
- Scaling path: Split into per-type shard files, or add optional SQLite backend

**RAG vector store:**
- Current capacity: ChromaDB local, unbounded in theory
- Limit: All passages embedded in memory at query time; large source documents (500+ pages) may cause OOM on low-RAM systems
- Scaling path: Already using local ChromaDB with disk persistence — acceptable for this use case

---

## Dependencies at Risk

**`module_data.py` not a proper Python package:**
- Risk: Lives in `.claude/additional/infrastructure/` — this is a config/prompt directory, not a code directory. The file is imported by manipulating `sys.path` with a hardcoded relative path.
- Impact: Any refactor of `.claude/` layout breaks `inventory_manager.py` and all module libs at import time.
- Migration plan: Move `module_data.py` to `lib/module_data.py` and update the single `sys.path` hack in `inventory_manager.py`.

---

## Missing Critical Features

**No WorldGraph save/restore:**
- Problem: `dm-session.sh save/restore` snapshots only legacy flat files. There is no mechanism to snapshot and restore `world.json`.
- Blocks: Reliable save points for WorldGraph campaigns.

**No WorldGraph reset:**
- Problem: `dm-reset.sh` does not touch `world.json`. No tool provides `world.json` reset.
- Blocks: Clean campaign resets without manual file deletion.

**`dm-overview.sh` is blind to WorldGraph:**
- Problem: `world_stats.py` counts NPCs, locations, facts, plots from legacy flat files. In WorldGraph campaigns, it reports everything as zero.
- Blocks: Useful session summary at `dm-session.sh start`.

---

## Test Coverage Gaps

**Session manager save/restore with WorldGraph data:**
- What's not tested: No test verifies that `create_save()` + `restore_save()` preserves `world.json`
- Files: `tests/test_session_manager.py`, `lib/session_manager.py`
- Risk: Silent data loss on session restore in WorldGraph campaigns
- Priority: High

**`entity_enhancer.py` apply/list-unenhanced against WorldGraph:**
- What's not tested: `apply_enhancements()`, `list_unenhanced()`, `find_entity()` are only tested against legacy flat files (via conftest fixtures that create `character.json`, `locations.json`)
- Files: `tests/` (no test file for entity_enhancer), `lib/entity_enhancer.py`
- Risk: These functions silently no-op in WorldGraph campaigns
- Priority: High

**`dm-reset.sh` does not reset world.json:**
- What's not tested: No test verifies post-reset state of `world.json`
- Files: `tools/dm-reset.sh`
- Risk: Misleading reset behavior goes unnoticed
- Priority: Medium

**`wiki_manager.py` vs `world_graph.py` wiki feature split:**
- What's not tested: No integration test verifies that items added via `dm-wiki.sh` are visible to `dm-inventory.sh craft`
- Files: `lib/wiki_manager.py`, `lib/inventory_manager.py`, `tests/`
- Risk: Craft silently fails for all wiki items added via the main tool
- Priority: High

---

*Concerns audit: 2026-03-28*
