# Architecture

**Analysis Date:** 2026-03-28

## Pattern Overview

**Overall:** Layered CLI system — Claude Code as AI orchestrator, Bash wrappers as interface, Python modules as domain logic, WorldGraph as unified data store.

**Key Characteristics:**
- Claude Code consumes `/commands/*.md` as skill definitions and drives all gameplay via Bash tool calls
- Every tool call follows: Claude → `tools/dm-*.sh` (Bash wrapper) → `lib/*.py` (Python domain logic) → `world.json` (WorldGraph)
- Module middleware intercepts CORE tool calls via pre/post hooks without modifying CORE code
- Context is pre-compiled and injected at prompt-time via `UserPromptSubmit` hooks

## Layers

**Claude Code Commands Layer:**
- Purpose: Define Claude's skills and behavior — what Claude does when a player types `/dm`
- Location: `.claude/commands/`
- Contains: Markdown skill files (`dm.md`, `dm-continue.md`, `new-game.md`, `import.md`, etc.)
- Depends on: CORE tools (calls them via Bash tool)
- Used by: Claude Code agent at prompt submission

**Hooks Layer (Context Injection):**
- Purpose: Pre-compile context before each DM prompt so Claude has rules + state without extra tool calls
- Location: `.claude/hooks/` (three `UserPromptSubmit` hooks + `PostToolUse` language check)
- Contains: `dm-load-rules.sh` (rules → `/tmp/dm-rules.md`), `dm-load-campaign.sh` (world state → stdout), `dm-load-session.sh` (quests/consequences/last session → stdout)
- Depends on: `dm-active-modules-rules.sh`, `dm-session.sh context`, campaign files
- Used by: Claude Code runtime (triggered on every prompt matching DM commands)

**CORE Tools Layer:**
- Purpose: Thin Bash wrappers exposing Python logic as CLI commands
- Location: `tools/`
- Contains: `dm-roll.sh`, `dm-inventory.sh`, `dm-session.sh`, `dm-player.sh`, `dm-npc.sh`, `dm-location.sh`, `dm-note.sh`, `dm-plot.sh`, `dm-consequence.sh`, `dm-time.sh`, `dm-campaign.sh`, `dm-wiki.sh`, `dm-world.sh`, `dm-search.sh`, `dm-enhance.sh`, `dm-overview.sh`
- Depends on: `lib/`, `tools/common.sh`, optionally `common-advanced.sh` for middleware dispatch
- Used by: Claude Code commands, hooks, modules

**CORE Library Layer:**
- Purpose: All domain logic in Python
- Location: `lib/`
- Key files:
  - `world_graph.py` — unified entity graph (2481 lines, primary data layer)
  - `entity_manager.py` — base class for all domain managers
  - `session_manager.py`, `player_manager.py`, `inventory_manager.py`, `dice.py`, `wiki_manager.py`, `time_manager.py`, `campaign_manager.py`, `consequence_manager.py`, `npc_manager.py`, `location_manager.py`, `plot_manager.py`
  - `currency.py` — universal currency system
  - `calendar.py` — universal calendar system
  - `entity_enhancer.py` — RAG-based entity enrichment
  - `rag/` — vector store, embedder, semantic chunker
- Depends on: `world-state/` (JSON data), `lancedb/` (vector store)
- Used by: tools/, module lib/

**Module Layer:**
- Purpose: Optional gameplay extensions that intercept or add to CORE behavior
- Location: `.claude/additional/modules/<module-id>/`
- Active modules: `custom-stats`, `world-travel`, `mass-combat`, `firearms-combat`
- Structure per module: `module.json` (manifest), `rules.md` (DM rules override), `lib/` (Python), `tools/` (module CLIs), `middleware/<tool>.sh` (pre-hook), `middleware/<tool>.sh.post` (post-hook), `tests/`
- Depends on: CORE lib/, `module-data/<module-id>.json`
- Used by: `dispatch_middleware` in Bash wrappers

**DM Rules Layer:**
- Purpose: Define gameplay rules loaded into Claude's context at session start
- Location: `.claude/additional/dm-slots/` (slot files), module `rules.md` files, `.claude/additional/narrator-styles/` (5 styles)
- Contains: 20+ `.md` slot files covering combat, narration, dice, movement, loot, social, etc.
- Loaded by: `dm-active-modules-rules.sh` — assembles all slots + module overrides → `/tmp/dm-rules.md`
- Used by: Claude via hook-injected context

**Data Layer:**
- Purpose: Per-campaign persistent state
- Location: `world-state/campaigns/<campaign-name>/`
- Contains: `world.json` (WorldGraph — all entities), `campaign-overview.json` (metadata, time, modules config), `campaign-rules.md` (campaign-specific DM rules), `session-log.md`, `saves/` (JSON snapshots), `module-data/<module-id>.json`
- Active campaign pointer: `world-state/active-campaign.txt`

## Data Flow

**Player types `/dm` command:**
1. `UserPromptSubmit` hooks fire: rules compiled to `/tmp/dm-rules.md`, campaign state injected to context, session context (quests/consequences) injected
2. Claude reads `/tmp/dm-rules.md` and injected context
3. Claude runs `tools/dm-session.sh start` (or appropriate command)
4. Bash wrapper calls `dispatch_middleware` — checks all module middleware for `dm-session.sh`
5. If module pre-hook returns 0: module handled, skip CORE. If returns 1: CORE Python runs
6. Python reads/writes `world.json` via WorldGraph
7. Post-hooks run (`dm-session.sh.post`) for any enabled modules
8. Output returned to Claude, Claude narrates

**WorldGraph write path:**
1. Python manager (`session_manager.py`, etc.) inherits `EntityManager`
2. `EntityManager` uses `CampaignManager` to find `world-state/active-campaign.txt`
3. `WorldGraph._load()` reads `world.json`, modifies nodes/edges in memory
4. `WorldGraph._save()` writes atomically via `.json.tmp` → `os.replace()`

**Module middleware dispatch:**
1. CORE Bash tool calls `dispatch_middleware "dm-session.sh" "$ACTION" "$@"`
2. `common-advanced.sh` iterates all `modules/*/middleware/dm-session.sh`
3. Checks `_module_enabled()` via `module_loader.py` against `campaign-overview.json`
4. First middleware returning exit code 0 = handled (stops chain)
5. Post-hooks via `dispatch_middleware_post` always run for all enabled modules

**Rules loading pipeline:**
1. Hook fires on `/dm*` prompts: `dm-load-rules.sh`
2. `dm-active-modules-rules.sh` reads `campaign-overview.json` → `modules` dict
3. For each enabled module: reads `module.json` for `replaces` list, loads `rules.md`
4. Slot replacement: if module replaces a slot name, module rules substitute that slot
5. Addons (no `replaces`): appended after all slots
6. Campaign-specific `campaign-rules.md` appended last
7. Narrator style loaded from `campaign-overview.json` → `narrator_style.id` → `.claude/additional/narrator-styles/<id>.md`

## Key Abstractions

**WorldGraph (`lib/world_graph.py`):**
- Purpose: Unified entity graph replacing separate JSON files (npcs.json, locations.json, etc.)
- Node ID format: `type:kebab-name` (e.g., `npc:merchant-ivan`, `location:market-square`)
- Node types: player, npc, location, item, creature, fact, quest, consequence, spell, technique, potion, material, artifact, weapon, armor, tool, book, chapter, cantrip, effect, misc
- Edge types: at, owns, connected, requires, involves, trained, sells, spawns_at, known_by, relationship, triggers, crafted_with
- Examples: `lib/world_graph.py` (primary), all managers use it
- Pattern: load-modify-save with atomic write

**EntityManager (`lib/entity_manager.py`):**
- Purpose: Base class providing campaign path resolution and JSON ops for all domain managers
- Pattern: `SessionManager`, `PlayerManager`, `InventoryManager`, etc. all extend `EntityManager`
- Resolves campaign dir via `CampaignManager` → `active-campaign.txt`

**Module Middleware Pattern:**
- Pre-hook (`middleware/<tool>.sh`): exit 0 = handled (CORE skipped), exit 1 = pass to CORE
- Post-hook (`middleware/<tool>.sh.post`): always runs after CORE, no return code semantics
- Help extension: `middleware/<tool>.sh --help` appends module commands to CORE help
- Examples: `world-travel` intercepts `dm-session.sh move`, `dm-location.sh` create

**Slot System (DM Rules):**
- Each `.md` file in `dm-slots/` has a name (filename without extension) = slot ID
- Modules declare `"replaces": ["slot-name"]` in `module.json` to override that rule block
- `_preamble.md` is always first, cannot be replaced
- Allows modules to swap out e.g. movement rules (`movement` slot) with their own travel system

## Entry Points

**`/dm` command:**
- Location: `.claude/commands/dm.md`
- Triggers: Player types `/dm` in Claude Code
- Responsibilities: Campaign selection menu, session start, routing subcommands

**`/dm-continue` command:**
- Location: `.claude/commands/dm-continue.md`
- Triggers: Resuming an existing session
- Responsibilities: Runs `dm-session.sh start`, reads `/tmp/dm-rules.md`

**`tools/dm-world.sh`:**
- Location: `tools/dm-world.sh`
- Triggers: All CORE tools route through this unified CLI
- Responsibilities: Unified WorldGraph CLI — all old tools are thin wrappers over it

**`tools/common.sh`:**
- Location: `tools/common.sh`
- Triggers: Sourced by every Bash tool via `source "$(dirname "$0")/common.sh"`
- Responsibilities: Python detection, path setup, campaign resolution, `dispatch_middleware` wiring

## Error Handling

**Strategy:** Exit codes + stderr messaging; Python tools print errors to stderr, Bash wrappers propagate exit codes; Claude reads tool output and adapts

**Patterns:**
- WorldGraph: prints to `sys.stderr`, returns `False` on failure, tools check and `exit 1`
- Campaign resolver: `sys.exit(1)` with "No active campaign" message
- Bash tools: `require_active_campaign()` guard at top, early exit with `error "..."` helper
- Module dispatch: if no middleware handles, CORE runs normally (graceful degradation)
- Atomic write: `world.json.tmp` → `os.replace()` prevents corruption on write failure

## Cross-Cutting Concerns

**Logging:** `world-state/usage/token-usage.log` via `log_token_usage()` in `common.sh` (tab-separated, campaign + command + metadata)

**Validation:** `lib/validators.py` for entity names (Cyrillic-incompatible regex — known issue); `validate_name()` in `common.sh` for Bash-side validation

**Authentication:** None — local tool, no auth layer

**Campaign isolation:** All data scoped to `world-state/campaigns/<active>/`; `active-campaign.txt` as global pointer; `require_active_campaign()` guard in all tools

**Language enforcement:** `PostToolUse` hook on Edit/Write runs `check-language-policy.sh` — rules files must be English-only

---

*Architecture analysis: 2026-03-28*
