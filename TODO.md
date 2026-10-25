# TODO — DM System

## Generated files tracked in git break `git pull --ff-only` on the VPS (found 2026-08-03)
Deploy on the VPS is `git pull --ff-only`, and it aborts on a dirty tree. Two tracked files are
rewritten by simply RUNNING the project, so the tree is never clean for long:
- `uv.lock` — every `uv run` (including the service's own `ExecStart`, so every `systemctl restart`)
  rewrites it: VPS uv 0.11.28 logs `Resolving despite existing lockfile due to removal of global
  exclude newer` and drops the `[options] exclude-newer` block plus all `sys_platform` markers.
- `modules/registry.json` — even the read-only `dm-module.sh list` reorders and rewrites it.

Fix direction: stop tracking `modules/registry.json` (regenerate it on demand), and pin/align the
uv version — or accept the lock churn and commit it once from the VPS. Until then a deploy can die
mid-way with "Your local changes would be overwritten".

## Unified Inventory Storage (Refactor)
Move inventory data INTO entity files instead of separate module-data JSONs:
- Player inventory → `character.json` (instead of `module-data/inventory-system.json`)
- NPC party inventory → `npcs.json` per-NPC (instead of `module-data/inventory-party.json`)
- Pros: everything in one place, `dm-npc.sh status` shows inventory inline
- Cons: breaks module isolation, but upstream is dead so lib/ is ours

## Graph System — long-term
Evolve wiki.json into a full entity graph replacing npcs.json + locations.json + facts.json + wiki.json. All entities as nodes with typed edges (sells, knows, located_at, component_of, etc). Do AFTER wiki.json is battle-tested in multiple campaigns.

## Auto-DC-Mod from Inventory (deferred)
- `--skill "alchemy"` should check if items granting dc_mod are in inventory (via wiki)
- If item not in inventory → dc_mod doesn't apply
- Currently dc_mod is hardcoded in character.json skills — should be dynamic
- Do when we actually lose an item with a bonus

## CORE Encounter System on Move
Configurable encounter engine triggered by `dm-session.sh move --elapsed N`. Settings per campaign in `campaign-overview.json`:
- `encounter_chance`: base % per hour of travel (e.g. 15 = 15% per hour)
- `encounter_types`: weighted table of categories (bandits: 30, beasts: 25, undead: 20, merchants: 15, patrol: 10)
- `encounter_frequency`: min hours between encounters (e.g. 2 = max 1 encounter per 2 hours)
- `encounters_enabled`: true/false toggle
- On trigger: roll category from weighted table, create creature from wiki (if exists) or print type for DM to narrate
- Auto-lookup creature stats from wiki for instant combat setup
- Works with any campaign/setting — zombie hordes, monster hunters, road bandits

## Import without RAG is broken end to end (found 2026-10-25, War and Peace import)
Importing a book needs `sentence-transformers` + `chromadb` (several GB with torch) even though extractor agents only read chunk files:
- `tools/dm-extract.sh prepare` aborts without RAG; `lib/agent_extractor.py` `prepare_for_agents` exits too. Chunking could be a plain paragraph split.
- `.claude/agents/extractor-*.md` tell agents to use `dm-search.sh --rag-only` and carry `model: opus` (expensive). Worked around with custom Haiku prompts, one agent per ~145k-char package writing `extracted/agent-NN.json`.
- `lib/rag/__init__.py` does not export `QuoteExtractor`, so the quote step of `save` fails with `cannot import name 'QuoteExtractor'`.
- `lib/rag/embedder.py` defaults to `all-MiniLM-L6-v2`, English only: useless for Russian books. Use a multilingual model (multilingual-e5-small needs `query: `/`passage: ` prefixes).

## Import drops factions (found 2026-10-25)
`AgentExtractor.validate_and_save` saves only npcs, locations, items, plots; `factions`, `monsters`, `traps` from `merge_agent_results` are silently dropped. War and Peace factions were kept in `world-state/campaigns/war-and-peace/merged-clean.json`.

## No dedupe of the same entity across extraction packages (found 2026-10-25)
Per-package extraction produced 419 NPC keys for ~139 real characters («Пьер Безухов» x19, «Фёдор/Федор Долохов», «Бенигсен/Беннигсен»). Needed a hand-made alias map; the importer has no normalisation step.

## Two-player (couple) play is not supported natively (found 2026-10-25)
One `player:active` node plus DM-controlled party NPCs (`dm-npc.sh promote`). Second human player has to be played as a party NPC with a campaign rule that the DM never decides for them.

## Campaign rules template can never apply to a freshly created campaign (found 2026-10-25)
`dm-campaign-rules.sh apply <id>` prints `[SKIP] campaign-rules.md already exists` and only writes the metadata to `campaign-overview.json`, but `CampaignManager.init_campaign_files` (also used by import `prepare`) already creates a placeholder `campaign-rules.md`. Result: "Template set to: political-intrigue" while the file holds no template rules. Same for `dm-campaign-custom-rules.sh apply`: "already applied" is tracked in the overview, so re-applying after the file was recreated is skipped. Fix: skip only when the file contains template content, and derive "applied" from the markers in the file, not from the overview.

## Calendar has no leap years (found 2026-10-25)
`lib/calendar.py` `days_in_year` sums fixed month lengths and `_absolute_day` multiplies `year * days_in_year`, so February is always 28 days. War and Peace runs 1805-1813 on the Julian calendar (1808 and 1812 are leap years), so dates and weekdays drift by one day after each 29 February. Fix direction: optional `leap_rule` in the calendar config (every N years, which month gets the extra day).

## Imported quests crash `dm-plot.sh list` and spam the active list (found 2026-10-25)
`AgentExtractor.validate_and_save` stores extracted `plot_hooks` as `quest:*` nodes with `objectives` as plain strings and no `status`. `world_graph.py` `quest-list` (line ~2751, `o.get("done")`) assumes objective dicts `{text, done}` and raises `AttributeError: 'str' object has no attribute 'get'`. Also 201 book beats became 201 active quests, drowning the real ones. Fix direction: importer must write objectives as `{"text","done"}`, set `status`, and put non-quest scene/theme beats into `chapter`/`fact` nodes instead of quests; make `quest-list` tolerate legacy string objectives.

## Image MCP (`mcp__websearch__generate_image`) fails on every prompt (found 2026-10-25)
Workaround that works: Codex imagegen, see ~/.claude/docs/image-generation-codex.md. Three calls in a row (two cinematic prompts and a trivial "red apple" 1:1) returned `Provider returned error` for `google/gemini-nano-banana-2.1` (OpenRouter shows the model and its single provider, Google AI Studio, as listed and up). `~/.claude/mcp-servers/websearch/index.js` sends `modalities: ['image']` plus `image_config.aspect_ratio`; Gemini image models normally require `['image','text']`. Hypothesis, not yet verified. Fix direction: change the modalities array in `index.js` (global file, owner approval needed) and reconnect the MCP; otherwise retry later. The campaign needs this for cinematic scene art (`cinematic_visuals` is enabled).

## HTML play screen follow-ups (found 2026-10-25)
- [ ] **Declare Pillow** — `lib/screen/theme.py` imports PIL, which is only present transitively; add it to `pyproject.toml` dependencies together with a deliberate `uv.lock` update (see the lockfile churn note above).
- [ ] **Web-app integration** — the screen runs next to Claude Code (actions reach the Master through `dm-screen.sh listen`). A standalone mode for the FastAPI game master (`backend/game_session.py`) should read the same `inbox.jsonl` and write `turn.json`; not done.
- [ ] **Mic tuning** — VoiceType self-tunes the system microphone volume (clipping/too quiet); the screen only cleans audio with ffmpeg and relies on VoiceType's tuning of the shared source.
- [ ] **Window on top** — the app window opens through Chrome `--app`; whether KDE raises it above other windows was not verified from the sandbox.

## Full test suite has 7 failures unrelated to the screen (found 2026-10-25)
- `tests/test_wizard.py::TestWizardMCPTools` (5 tests): `mcp` is 2.x in `.venv`, where `mcp.server.fastmcp` no longer exists (`FastMCP` became `MCPServer`). Fix direction: pin `mcp<2` or migrate `backend/wizard_mcp*.py`. Fails on a clean `HEAD` checkout as well.
- `tests/test_secret_guard.py` (2 tests): `value_findings`/`pattern_findings` call `read_bytes()` on every tracked path and crash with `IsADirectoryError` on `.agents/skills/cinematic-scene` (a staged directory entry). Fix direction: skip non-regular files in the guard, and check why that path is staged as a directory.

## `dm-inventory.sh update "<name>"` can match a fact node instead of the hero (found 2026-10-25)
The fuzzy name lookup resolved `Максим Астраханцев` to `fact:npc-001` (a `dm-note` fact whose text starts with the heroes' names): `--gold 9500` was written into that fact's `data.money` and the player's purse stayed unchanged. Fix direction: resolve only `player:*` and `npc:*` nodes in `lib/inventory_manager.py` and fail loudly on any other type; until then use `dm-player.sh gold` for the player. Triggered case: War and Peace, payment for the first order.

## `/dm-save` skill calls actions that do not exist (found 2026-10-25)
`.claude/commands/dm-save.md` (and its Codex copy) runs `bash tools/dm-plot.sh threads`, which fails with `Unknown action 'threads'`. Also the orphan check compares the player's location name with location node ids, so it can report false issues. Fix direction: replace with `dm-plot.sh list --status active` and compare names or ids consistently.
