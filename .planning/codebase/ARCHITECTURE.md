# Architecture

**Analysis Date:** 2026-03-29 (post WorldGraph migration)

## Pattern Overview

**Overall:** Layered CLI system — Claude Code as AI orchestrator, Bash wrappers as interface, Python modules as domain logic, WorldGraph as unified data store.

**Key Characteristics:**
- Claude Code consumes `/commands/*.md` as skill definitions and drives all gameplay via Bash tool calls
- Every tool call follows: Claude → `tools/dm-*.sh` (Bash wrapper) → `lib/*.py` (Python domain logic) → `world.json` (WorldGraph)
- Module middleware intercepts CORE tool calls via pre/post hooks without modifying CORE code
- Context is pre-compiled and injected at prompt-time via `UserPromptSubmit` hooks
- **ALL data lives in `world.json`** — no flat JSON files (npcs.json, locations.json, etc.) used for campaign state

## Layers

**Claude Code Commands Layer:**
- Location: `.claude/commands/`
- Contains: Markdown skill files (`dm.md`, `dm-continue.md`, `new-game.md`, `import.md`, etc.)
- Depends on: CORE tools (calls them via Bash tool)

**Hooks Layer (Context Injection):**
- Location: `.claude/hooks/`
- Contains: `dm-load-rules.sh` (rules → `/tmp/dm-rules.md`), `dm-load-campaign.sh` (world state → stdout), `dm-load-session.sh` (quests/consequences/last session → stdout)
- Triggered on every prompt matching DM commands

**CORE Tools Layer:**
- Location: `tools/`
- Contains: `dm-roll.sh`, `dm-inventory.sh`, `dm-session.sh`, `dm-player.sh`, `dm-npc.sh`, `dm-location.sh`, `dm-note.sh`, `dm-plot.sh`, `dm-consequence.sh`, `dm-time.sh`, `dm-campaign.sh`, `dm-wiki.sh`, `dm-world.sh`, `dm-search.sh`, `dm-enhance.sh`, `dm-overview.sh`
- Pattern: Source `common.sh`, dispatch middleware, invoke Python, dispatch post-hooks

**CORE Library Layer:**
- Location: `lib/`
- Key files:
  - `world_graph.py` — unified entity graph (2481 lines, primary data layer)
  - `entity_manager.py` — base class for all domain managers
  - `session_manager.py` — session lifecycle, saves (world.json snapshots), party movement
  - `player_manager.py` — XP, HP, conditions (reads/writes WorldGraph player node)
  - `inventory_manager.py` — items, weight, currency, craft/use (WorldGraph for char + wiki)
  - `dice.py` — dice engine with auto-lookup from WorldGraph player/creature nodes
  - `time_manager.py` — game clock, auto-tick
  - `campaign_manager.py` — campaign creation/switching (inits world.json)
  - `entity_enhancer.py` — RAG-based entity enrichment (reads/writes WorldGraph)
  - `agent_extractor.py` — source material extraction pipeline (writes to WorldGraph)
  - `encounter_engine.py` — random encounters (creatures from world.json)
  - `module_data.py` — per-module JSON config storage
  - `currency.py`, `calendar.py` — universal systems
  - `rag/` — vector store, embedder, semantic chunker

**Module Layer:**
- Location: `.claude/additional/modules/<module-id>/`
- Active modules: `custom-stats`, `world-travel`, `mass-combat`, `firearms-combat`
- Structure per module: `module.json`, `rules.md`, `lib/`, `tools/`, `middleware/`, `tests/`
- Reference data (weapons, armor, creatures) stored in world.json as nodes, config in `module-data/<id>.json`

**DM Rules Layer:**
- Location: `.claude/additional/dm-slots/`, module `rules.md` files, `.claude/additional/narrator-styles/`
- Loaded by: `dm-active-modules-rules.sh` → `/tmp/dm-rules.md`

**Campaign Custom Rules Layer:**
- Location: `.claude/additional/campaign-custom-rules/`
- Contains: Stackable rule templates (e.g. `realistic-progression.md`, `russian-language.md`)
- Applied via: `dm-campaign-custom-rules.sh apply <id>` → appended to `campaign-rules.md`

**Data Layer:**
- Location: `world-state/campaigns/<campaign-name>/`
- Primary: `world.json` (WorldGraph — ALL entities: player, NPCs, locations, items, creatures, weapons, armor, quests, consequences, facts, wiki)
- Metadata: `campaign-overview.json` (time, date, modules config, narrator style, genre, currency, calendar)
- Rules: `campaign-rules.md` (campaign-specific + custom rules)
- Saves: `saves/` (JSON snapshots of world.json)
- Module config: `module-data/<module-id>.json` (fire_modes, combat_rules, NOT reference data)

## Data Flow

**Player types `/dm` command:**
1. `UserPromptSubmit` hooks fire: rules → `/tmp/dm-rules.md`, campaign state → context
2. Claude reads rules and context
3. Claude runs tools (dm-session.sh, dm-roll.sh, etc.)
4. Bash wrapper dispatches middleware → Python reads/writes world.json → post-hooks
5. Output returned to Claude for narration

**WorldGraph write path:**
1. Python manager creates `WorldGraph(campaign_dir)`
2. `WorldGraph._load()` reads world.json
3. Mutation (add_node, update_node, etc.)
4. `WorldGraph._save()` writes atomically via `.json.tmp` → `os.replace()`

**Module middleware dispatch:**
1. CORE Bash calls `dispatch_middleware "dm-session.sh" "$ACTION" "$@"`
2. `common-advanced.sh` iterates enabled modules' middleware
3. Pre-hook exit 0 = handled (CORE skipped), exit 1 = pass to CORE
4. Post-hooks always run for all enabled modules

## Key Abstractions

**WorldGraph (`lib/world_graph.py`):**
- Unified entity graph: nodes + edges in single JSON file
- Node ID format: `type:kebab-name` (e.g., `npc:merchant-ivan`, `weapon:ak-74`)
- Node types: player, npc, location, item, creature, fact, quest, consequence, spell, technique, potion, material, artifact, weapon, armor, tool, book, chapter, cantrip, effect, misc
- Edge types: at, owns, connected, requires, involves, trained, sells, spawns_at, known_by, relationship, triggers, crafted_with
- Pattern: load-modify-save with atomic write

**EntityManager (`lib/entity_manager.py`):**
- Base class for SessionManager, PlayerManager, etc.
- Resolves campaign dir via CampaignManager → `active-campaign.txt`

**Module Middleware Pattern:**
- Pre-hook: exit 0 = handled, exit 1 = pass to CORE
- Post-hook: always runs after CORE
- Slot System: modules declare `"replaces": ["slot-name"]` to override DM rules

## Entry Points

- `/dm` → `.claude/commands/dm.md` → campaign selection, always routes to `/dm-continue`
- `/dm-continue` → `.claude/commands/dm-continue.md` → session start with full context
- `/new-game` → `.claude/commands/new-game.md` → campaign creation with modules, narrator, rules, currency, calendar
- `tools/dm-world.sh` → unified WorldGraph CLI (all old tools are thin wrappers)

## Error Handling

- WorldGraph: prints to stderr, returns False on failure, atomic writes prevent corruption
- Bash tools: `require_active_campaign()` guard, early exit with error helper
- Module dispatch: graceful degradation if no middleware handles

---

*Architecture analysis: 2026-03-29*
