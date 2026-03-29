# Codebase Concerns

**Analysis Date:** 2026-03-29 (post WorldGraph migration)

---

## Tech Debt

**`time_manager.py` reads module-data via hardcoded path:**
- Issue: `Path(self.campaign_dir) / "module-data" / "custom-stats.json"` instead of `ModuleDataManager` API.
- Files: `lib/time_manager.py` lines 81, 91, 171
- Impact: If module-data location changes, time ticking silently stops decaying custom stats.
- Fix: Use `ModuleDataManager` API.

**`module_data.py` exists in two places:**
- Issue: `lib/module_data.py` (canonical) and `.claude/additional/infrastructure/module_data.py` (original). All imports now point to `lib/`, but the original file still exists.
- Fix: Delete `.claude/additional/infrastructure/module_data.py` once confirmed no external consumer.

**`common.sh` still exports legacy file path variables:**
- Issue: `NPCS_FILE`, `LOCATIONS_FILE`, `FACTS_FILE`, `CONSEQUENCES_FILE`, `CHARACTER_FILE` set in common.sh.
- Used by: `dm-reset.sh` (legacy cleanup of old flat files if they exist), `benchmark-hybrid.sh`
- Impact: Cosmetic — reinforces false assumption that flat files are canonical.

**`agent_extractor.py` reads agent output flat files (by design):**
- Issue: `_collect_and_merge_results()` reads `agent-npcs.json`, `npcs.json`, etc. from `extracted/` directory.
- Not a bug: These are **agent output files**, not campaign state. Agents produce flat JSON as extraction output, extractor parses and writes to WorldGraph.
- No fix needed — this is the correct data flow.

**`session_manager.py` restore has backward compat for old saves:**
- Issue: `restore_save()` handles old save format (flat file snapshots) for campaigns saved before migration.
- Impact: Dead code path once all campaigns re-save. Low priority cleanup.

---

## Known Bugs

**Test runner collision on `test_encounter_engine.py`:**
- Symptoms: `uv run pytest` (without path) crashes with `import file mismatch` — two files with same module name at `tests/` and `.claude/additional/modules/world-travel/tests/`.
- Workaround: `uv run pytest --ignore=.claude/additional/modules/world-travel/tests/`
- Fix: Rename one of the test files to be unique.

---

## Security Considerations

**Shell injection via unquoted user input in `dm-npc.sh`:**
- Risk: `attitude` and `hp` commands build JSON strings with raw shell variables. A value with `$(...)` or backticks could execute arbitrary commands.
- Files: `tools/dm-npc.sh` lines 137, 153
- Fix: Use `escape_json()` or pass values as separate arguments to `world_graph.py`.

**Python inline code in shell scripts with interpolated variables:**
- Risk: `dm-npc.sh` runs inline Python with `$1` interpolated directly into `$PYTHON_CMD -c "..."`. NPC name with single quote breaks syntax; malicious names enable code execution.
- Files: `tools/dm-npc.sh` lines 113–118, 129–134, 145–150, `tools/dm-location.sh` lines 67–68
- Fix: Pass NPC name as argv argument, not string interpolation.

---

## Performance Bottlenecks

**`world_graph.py` does full load+save on every single write:**
- Problem: Every `add_node`, `update_node`, `inventory_add`, etc. loads entire `world.json`, mutates, writes back.
- Impact: For campaigns with hundreds of nodes, every tool call triggers full serialize/deserialize.
- Mitigation: Acceptable for CLI usage. Add in-memory cache with dirty-flag if performance becomes issue.

---

## Fragile Areas

**`lib/time_manager.py` hardcoded module-data path:**
- Reads `module-data/custom-stats.json` directly instead of using `ModuleDataManager`.
- If module-data location changes, time ticking silently stops.

**Inline Python in bash with `$LIB_DIR` interpolation:**
- Files: `tools/dm-npc.sh`, `tools/dm-location.sh`
- `LIB_DIR` with space = break. Single-quote NPC names break Python syntax.
- Rule: Never add new inline Python blocks. Always call proper Python script as subprocess.

---

## Scaling Limits

**`world.json` single-file design:**
- Current capacity: Functional up to a few thousand nodes
- Limit: Full load+save on every write; 5000+ nodes with large data blobs = noticeable latency
- Scaling path: Split into per-type shards, or add optional SQLite backend

**RAG vector store:**
- ChromaDB local with disk persistence — acceptable for this use case
- Large source documents (500+ pages) may cause OOM on low-RAM systems

---

## Test Coverage Gaps

**`inventory_manager.py` — no dedicated test file:**
- Craft/use/loot/transfer tested only via CLI (no unit tests)
- Priority: Medium

**`entity_enhancer.py` — no dedicated test file:**
- find_entity, apply_enhancements tested only via dm-enhance.sh
- Priority: Medium

**Shell injection in bash tools — no security tests:**
- Priority: Low (local tool, no external input)

---

*Concerns audit: 2026-03-29*
