# Architecture Map

> Comprehensive architecture documentation for Claude-Code-Game-Master (DM System)

## Table of Contents

1. [Four Architectural Layers](#four-architectural-layers)
2. [Tool-to-Lib Mapping](#tool-to-lib-mapping)
3. [Core Python Modules](#core-python-modules)
4. [Module Dependency Graph](#module-dependency-graph)
5. [Middleware Dispatch System](#middleware-dispatch-system)
6. [Optional Modules](#optional-modules)
7. [Data Flow Traces](#data-flow-traces)
8. [Data Storage Layout](#data-storage-layout)
9. [Key Architectural Patterns](#key-architectural-patterns)


---

## Four Architectural Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 1: Claude Code Interface                                      │
│ .claude/commands/*.md (slash commands), hooks, settings              │
│ User issues commands like /dm-session, /dm-npc, /help               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ invokes bash tool
┌──────────────────────────▼──────────────────────────────────────────┐
│ LAYER 2: Bash Wrappers (tools/)                                     │
│ Thin CLI scripts: argument parsing, dispatch_middleware, delegation  │
│ common.sh provides shared setup + middleware dispatch functions      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ dispatch_middleware (pre-hook)
                           ├──→ Module middleware intercepts (optional)
                           │    Returns 0 = handled, 1 = pass to CORE
                           │
                           │ uv run python lib/*.py
┌──────────────────────────▼──────────────────────────────────────────┐
│ LAYER 3: Python Library (lib/)                                      │
│ Business logic: world_graph.py (central), managers, dice, currency  │
│ RAG subsystem: lib/rag/ (vector store, embedder, chunker)           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ dispatch_middleware_post (post-hook)
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│ LAYER 4: Data Storage (world-state/)                                │
│ world.json (graph DB), campaign-overview.json, session-log.md       │
│ module-data/*.json, vectors/ (Chroma), saves/                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer 1: Claude Code Interface

- `.claude/commands/*.md` - Slash commands (create-character, reset, dm-save, help, setup, dm-continue, enhance, dm, new-game, world-check, import)
- `.claude/settings.local.json` - Permissions for bash tool execution
- `.claude/additional/infrastructure/` - Rule loaders (dm-active-modules-rules.sh, dm-campaign-rules.sh, dm-narrator.sh)
- `.claude/additional/dm-slots/` - DM gameplay rules compiled into `/tmp/dm-rules.md` at session start

### Layer 2: Bash Wrappers

All tools live in `tools/`. Each is a thin wrapper that:
1. Sources `common.sh` for shared utilities (Python detection, campaign paths, middleware)
2. Parses CLI arguments
3. Calls `dispatch_middleware` pre-hook (if applicable)
4. Delegates to Python lib via `uv run python lib/<module>.py <subcommand> <args>`
5. Calls `dispatch_middleware_post` post-hook

### Layer 3: Python Library

Central hub is `world_graph.py` (~103KB) - a unified graph database with 20+ node types and 12+ edge types. Most tools delegate to it directly. Specialized managers (session, time, campaign, entity_enhancer) handle cross-cutting concerns.

### Layer 4: Data Storage

Per-campaign data in `world-state/campaigns/{name}/`. Primary store is `world.json` (graph with nodes + edges). Campaign metadata in `campaign-overview.json`. Active campaign tracked in `world-state/active-campaign.txt`.

---

## Tool-to-Lib Mapping

All 23 bash tools and their Python delegations:

| # | Bash Tool | Primary Python Lib | Secondary Libs | Purpose |
|---|-----------|-------------------|----------------|---------|
| 1 | `dm-campaign.sh` | `campaign_manager.py` | `world_graph.py`, `colors.py` | Multi-campaign CRUD |
| 2 | `dm-session.sh` | `session_manager.py` | `world_graph.py`, `entity_enhancer.py`, `currency.py` | Session lifecycle, movement |
| 3 | `dm-player.sh` | `world_graph.py` | `player_manager.py`, `currency.py` | Player stats (XP, HP, gold, conditions) |
| 4 | `dm-npc.sh` | `world_graph.py` | `entity_enhancer.py` | NPC management |
| 5 | `dm-location.sh` | `world_graph.py` | (middleware) | Location management |
| 6 | `dm-plot.sh` | `world_graph.py` | (middleware) | Quest/plot tracking |
| 7 | `dm-inventory.sh` | `world_graph.py` | `inventory_manager.py`, `dice.py`, `currency.py` | Items, equipment, crafting |
| 8 | `dm-time.sh` | `time_manager.py` | `world_graph.py` | Game clock, date advancement |
| 9 | `dm-condition.sh` | `world_graph.py` | - | Condition add/remove/check |
| 10 | `dm-consequence.sh` | `world_graph.py` | (middleware) | Timed event triggers |
| 11 | `dm-note.sh` | `world_graph.py` | - | World facts/notes |
| 12 | `dm-wiki.sh` | `world_graph.py` | - | Structured knowledge base |
| 13 | `dm-roll.sh` | `dice.py` | `world_graph.py` | Dice rolling with auto-lookup |
| 14 | `dm-status.sh` | `world_graph.py` | - | Character sheet display |
| 15 | `dm-overview.sh` | `world_graph.py` | - | World state statistics |
| 16 | `dm-world.sh` | `world_graph.py` | - | Direct graph CLI passthrough |
| 17 | `dm-search.sh` | `world_graph.py` + `entity_enhancer.py` | - | Hybrid state + RAG search |
| 18 | `dm-enhance.sh` | `entity_enhancer.py` | `campaign_manager.py`, `world_graph.py` | RAG entity enhancement |
| 19 | `dm-extract.sh` | `agent_extractor.py` | `json_ops.py`, `validators.py`, `campaign_manager.py` | PDF/document extraction |
| 20 | `dm-reset.sh` | `world_graph.py` | `campaign_manager.py` | World state reset/archive |
| 21 | `dm-migrate-campaigns.sh` | (inline) | - | Data format migration |
| 22 | `common.sh` | (N/A - bash utility) | - | Shared setup, middleware dispatch |
| 23 | `benchmark-hybrid.sh` | `entity_enhancer.py` | - | Performance benchmarking |

Tools with middleware dispatch (pre+post hooks): `dm-session.sh`, `dm-inventory.sh`, `dm-npc.sh`, `dm-location.sh`, `dm-consequence.sh`, `dm-plot.sh`, `dm-time.sh`.

---

## Core Python Modules

### 19 Core Modules in `lib/`

| # | Module | Size | Purpose | Reads | Writes |
|---|--------|------|---------|-------|--------|
| 1 | `world_graph.py` | 103KB | Unified graph DB, 87 methods, 80+ subcommands | `world.json` | `world.json` |
| 2 | `campaign_manager.py` | 32KB | Multi-campaign management | `campaign-overview.json`, `active-campaign.txt` | Both |
| 3 | `session_manager.py` | 21KB | Session lifecycle, saves | `campaign-overview.json`, `world.json` | `session-log.md`, `saves/` |
| 4 | `player_manager.py` | 21KB | Player character operations | `world.json` (player node) | `world.json` |
| 5 | `inventory_manager.py` | 66KB | Items, equipment, crafting | `world.json`, `module-data/` | `world.json` |
| 6 | `entity_enhancer.py` | 31KB | RAG entity enhancement | `world.json`, `vectors/` | `world.json` |
| 7 | `agent_extractor.py` | 32KB | PDF extraction pipeline | PDFs, documents | `extracted/`, `merged-results.json` |
| 8 | `entity_manager.py` | 6KB | Base class for entity managers | `world.json` | `world.json` |
| 9 | `time_manager.py` | 9KB | Game clock and dates | `campaign-overview.json` | `campaign-overview.json` |
| 10 | `dice.py` | 31KB | Dice engine (2d6+3, advantage, etc.) | `world.json` (for auto-lookup) | - |
| 11 | `currency.py` | 7KB | Money formatting/parsing | `campaign-overview.json` (currency config) | - |
| 12 | `calendar.py` | 8KB | Fantasy calendar system | `campaign-overview.json` (calendar config) | - |
| 13 | `json_ops.py` | 9KB | JSON file I/O, merge, validate | Any JSON | Any JSON |
| 14 | `colors.py` | 9KB | ANSI terminal colors/formatting | - | stdout |
| 15 | `validators.py` | 10KB | Name/schema validation | - | - |
| 16 | `extraction_schemas.py` | 6KB | Pydantic models for extraction | - | - |
| 17 | `content_extractor.py` | 8KB | Text/PDF parsing, chunking | PDFs | - |
| 18 | `module_data.py` | 2KB | Module-specific JSON data | `module-data/*.json` | `module-data/*.json` |
| 19 | `encounter_engine.py` | 8KB | Encounter generation | - | - |

### RAG Subsystem (`lib/rag/`)

| Module | Purpose |
|--------|---------|
| `vector_store.py` | Chroma vector store interface |
| `embedder.py` | sentence-transformers local embedding |
| `semantic_chunker.py` | Intelligent document chunking |
| `rag_extractor.py` | Full RAG pipeline (extract -> chunk -> embed -> store) |
| `quote_extractor.py` | Quoted passage extraction |
| `extraction_queries.py` | Query templates per entity type |

---

## Module Dependency Graph

```
world_graph.py ◄──────────────────────────────────────────────────┐
  ├── json (stdlib)                                                │
  ├── pathlib (stdlib)                                             │
  └── colors.py                                                    │
                                                                   │
campaign_manager.py ◄──────────────────────┐                       │
  ├── world_graph.py ─────────────────────►│                       │
  └── colors.py                            │                       │
                                           │                       │
session_manager.py                         │                       │
  ├── entity_manager.py                    │                       │
  │   ├── json_ops.py                      │                       │
  │   ├── validators.py                    │                       │
  │   └── campaign_manager.py ─────────────┘                       │
  ├── world_graph.py ──────────────────────────────────────────────┘
  ├── currency.py
  └── colors.py

player_manager.py
  ├── entity_manager.py
  ├── currency.py
  ├── world_graph.py
  └── colors.py

inventory_manager.py
  ├── module_data.py
  ├── currency.py
  ├── dice.py
  ├── world_graph.py
  └── colors.py

entity_enhancer.py
  ├── campaign_manager.py
  ├── json_ops.py
  ├── world_graph.py
  ├── colors.py
  └── rag/ (lazy-loaded)
      ├── vector_store.py
      └── embedder.py

agent_extractor.py
  ├── extraction_schemas.py
  ├── json_ops.py
  ├── validators.py
  ├── campaign_manager.py
  └── rag/ (optional)

time_manager.py
  ├── campaign_manager.py
  ├── json_ops.py
  └── colors.py

dice.py
  └── (standalone, no lib deps)

currency.py
  └── campaign_manager.py (for config)

calendar.py
  └── (standalone, reads config passed in)
```

**Central nodes**: `world_graph.py` (imported by 8+ modules), `colors.py` (imported by all display modules), `campaign_manager.py` (imported by 5+ modules).

---

## Middleware Dispatch System

### Architecture

Defined in `tools/common.sh` (with advanced dispatch in `.claude/additional/infrastructure/common-advanced.sh`):

```
dispatch_middleware("dm-session.sh", "move", args...)
  │
  ├── For each module in .claude/additional/modules/*/
  │   ├── Check module enabled: _module_enabled(module-id)
  │   │   └── Python: module_loader.is_module_enabled()
  │   │       └── Reads campaign-overview.json → campaign_rules.modules
  │   │
  │   ├── If middleware file exists: modules/{id}/middleware/dm-session.sh
  │   │   ├── Execute middleware script with args
  │   │   ├── If exit 0 → HANDLED, skip CORE, return 0
  │   │   └── If exit 1 → NOT HANDLED, continue
  │   └── Next module
  │
  └── All modules checked, none handled → return 1 → CORE runs

dispatch_middleware_post("dm-session.sh", "move", args...)
  │
  └── For each enabled module with .post file:
      └── Execute modules/{id}/middleware/dm-session.sh.post || true
          (Always runs, errors ignored)
```

### Execution Pattern in Tools

```bash
# Typical tool pattern (e.g., dm-session.sh)
source common.sh

ACTION="$1"; shift
dispatch_middleware "dm-session.sh" "$ACTION" "$@" && exit $?

# CORE logic here (only runs if middleware didn't handle)
case "$ACTION" in
  move) $PYTHON_CMD lib/session_manager.py move "$@" ;;
  ...
esac

dispatch_middleware_post "dm-session.sh" "$ACTION" "$@"
```

### Tools Using Middleware Dispatch

All 10 CORE tools that invoke `dispatch_middleware` or `dispatch_middleware_post`:

| # | Tool | Pre-hook | Post-hook | Module Pre-Interceptors | Module Post-Interceptors |
|---|------|----------|-----------|-------------------------|--------------------------|
| 1 | `dm-session.sh` | ✅ | ✅ | world-travel (move: pathfinding + encounters) | — |
| 2 | `dm-location.sh` | ✅ | ✅ | world-travel (add: coordinates, connect: terrain/distance) | — |
| 3 | `dm-player.sh` | ✅ | ✅ | — | — |
| 4 | `dm-npc.sh` | ✅ | ✅ | — | — |
| 5 | `dm-plot.sh` | ✅ | ✅ | — | — |
| 6 | `dm-consequence.sh` | ✅ | ✅ | — | — |
| 7 | `dm-note.sh` | ✅ | ✅ | — | — |
| 8 | `dm-time.sh` | ✅ | ✅ | — | — |
| 9 | `dm-roll.sh` | ❌ | ✅ | — | — |
| 10 | `dm-inventory.sh` | ❌ | ✅ | — | — |

**Note**: `dm-roll.sh` and `dm-inventory.sh` only use post-hooks (no pre-hook dispatch). The remaining 8 tools use both pre and post dispatch.

### Middleware Dispatch Chain Detail

```
Tool invoked (e.g., dm-session.sh move "Town" --elapsed 2)
  │
  ├─[1] dispatch_middleware "dm-session.sh" "move" "Town" "--elapsed" "2"
  │     │
  │     ├── Iterate: .claude/additional/modules/*/middleware/dm-session.sh
  │     │   └── world-travel/middleware/dm-session.sh → EXISTS
  │     │       ├── _module_enabled("world-travel") → checks campaign-overview.json
  │     │       │   └── campaign_rules.modules["world-travel"] == true?
  │     │       ├── If enabled: execute, handles "move" action
  │     │       │   ├── BFS pathfinding, distance calc
  │     │       │   ├── Encounter checks per segment
  │     │       │   ├── Update player location
  │     │       │   └── exit 0 → HANDLED
  │     │       └── If disabled: skip
  │     │
  │     └── Return 0 → CORE skipped (exit $?)
  │
  ├─[2] CORE logic (only if pre-hook returned 1)
  │     └── uv run python lib/session_manager.py move "Town" --elapsed 2
  │
  └─[3] dispatch_middleware_post "dm-session.sh" "move" "Town" "--elapsed" "2"
        └── world-travel/middleware/dm-session.sh.post → does NOT exist
```

### Module Enable/Disable Lifecycle

```
1. Campaign creation or module toggle:
   → campaign-overview.json.campaign_rules.modules["module-id"] = true/false

2. Every dispatch_middleware call:
   → _module_enabled(module-id) calls Python:
     ModuleLoader().is_module_enabled(module-id)
       → Reads campaign-overview.json
       → Returns campaign_rules.modules[module-id] (default: module.json.enabled_by_default)

3. Module enable: set modules["id"] = true → middleware files start executing
4. Module disable: set modules["id"] = false → middleware files silently skipped
5. No initialization/teardown hooks — modules are stateless middleware only
6. Module data persists in module-data/*.json regardless of enable state
```

### Conflict Risks

| Risk | Description | Severity |
|------|-------------|----------|
| **Pre-hook ordering** | Modules iterated by filesystem glob order (`*/middleware/`). If two modules both pre-hook the same tool, first match wins. | Medium |
| **Post-hook cascade** | All enabled post-hooks run. If a post-hook on dm-time.sh fails, error is swallowed (`|| true`). Silent data loss possible. | Low |
| **No dependency enforcement** | `module.json.dependencies` is declared but NOT enforced at runtime. A module with missing deps will silently fail. | Medium |
| **Shared data mutation** | Multiple post-hooks could write to same JSON file (e.g., world.json) without coordination. | Low (currently no overlap) |

---

## Optional Modules

Located in `.claude/additional/modules/` (3 modules total):

### world-travel
- **ID**: `world-travel`
- **Purpose**: Coordinate-based navigation, pathfinding, maps, vehicle system, and automatic encounter checks
- **Enabled by default**: No
- **Category**: travel-mechanics
- **Tools**: `dm-navigation.sh`, `dm-map.sh`, `dm-encounter.sh`, `dm-vehicle.sh`
- **Middleware (pre-hooks)**: `dm-location.sh` (intercepts add --from, connect, decide, routes, block, unblock), `dm-session.sh` (intercepts move: distance calc, hierarchy, vehicles, auto-encounters)
- **Middleware (post-hooks)**: None
- **Total middleware files**: 2 (2 pre + 0 post)
- **Data**: Extends location nodes in `world.json` with coordinates/connections, `campaign-overview.json` with path_preferences and encounter_system
- **Replaces slots**: `movement`

### mass-combat
- **ID**: `mass-combat`
- **Purpose**: Individual unit tracking for large-scale battles (30+ combatants)
- **Enabled by default**: No
- **Category**: combat
- **Tools**: `dm-mass-combat.sh` (init, add, round, attack, aoe, damage, heal, kill, cover, status, next-round, end)
- **Middleware**: None (standalone module, no CORE tool interception)
- **Total middleware files**: 0
- **Data**: `combat-state.json` (temporary, deleted on battle end)
- **Replaces slots**: None

### firearms-combat
- **ID**: `firearms-combat`
- **Purpose**: Automated firearms combat with penetration mechanics, RPM simulation, fire modes
- **Enabled by default**: No
- **Category**: combat
- **Tools**: `dm-combat.sh` (resolve)
- **Middleware**: None (standalone module, no CORE tool interception)
- **Total middleware files**: 0
- **Data**: Weapon/fire-mode config in `campaign-overview.json.campaign_rules.firearms_system`
- **Replaces slots**: None

### Module Middleware Coverage Matrix

```
                    world-travel    mass-combat    firearms-combat
dm-session.sh       PRE             —              —
dm-location.sh      PRE             —              —
dm-player.sh        —               —              —
dm-npc.sh           —               —              —
dm-plot.sh          —               —              —
dm-consequence.sh   —               —              —
dm-note.sh          —               —              —
dm-time.sh          —               —              —
dm-roll.sh          —               —              —
dm-inventory.sh     —               —              —

Legend: PRE = pre-hook (can intercept), .post = post-hook (augments after CORE)
```

---

## Data Flow Traces

### Trace 1: Session Start

```
User: /dm-session start
  │
  ▼
[Layer 1] Claude Code invokes: bash tools/dm-session.sh start
  │
  ▼
[Layer 2] dm-session.sh
  ├── source common.sh (resolve campaign dir)
  ├── dispatch_middleware "dm-session.sh" "start" → no handler → returns 1
  ├── uv run python lib/session_manager.py start
  │   │
  │   ▼
  │ [Layer 3] session_manager.py.start_session()
  │   ├── Reads campaign-overview.json (current_location, session_count)
  │   ├── Reads world.json (count entities for summary)
  │   ├── Increments session_count
  │   ├── Writes campaign-overview.json
  │   ├── Appends "## Session N" to session-log.md
  │   └── Returns session context summary
  │         │
  │         ▼
  │       [Layer 4] world.json READ, campaign-overview.json READ+WRITE, session-log.md APPEND
  │
  ├── dispatch_middleware_post "dm-session.sh" "start"
  └── Auto-calls: dm-enhance.sh scene <current_location> (RAG context)
```

### Trace 2: Player Attacks Creature

```
User: /dm-roll --attack "longsword" --target "goblin"
  │
  ▼
[Layer 1] Claude Code invokes: bash tools/dm-roll.sh --attack "longsword" --target "goblin"
  │
  ▼
[Layer 2] dm-roll.sh
  ├── source common.sh
  ├── uv run python lib/dice.py --attack "longsword" --target "goblin"
  │   │
  │   ▼
  │ [Layer 3] dice.py
  │   ├── Reads world.json → player node → find weapon "longsword" in inventory
  │   ├── Gets attack bonus from character stats
  │   ├── Looks up "goblin" AC (from wiki or world.json creature node)
  │   ├── Rolls d20 + attack bonus vs AC
  │   ├── If hit: auto-rolls damage dice for weapon
  │   └── Returns formatted result (hit/miss, damage)
  │         │
  │         ▼
  │       [Layer 4] world.json READ (player stats + weapon + target AC)
  │
  └── No middleware dispatch (dm-roll.sh doesn't use middleware)
```

### Trace 3: NPC Creation with Module Middleware

```
User: /dm-npc create "Grimjaw" "A scarred orc blacksmith" "neutral"
  │
  ▼
[Layer 1] Claude Code invokes: bash tools/dm-npc.sh create "Grimjaw" "A scarred orc blacksmith" "neutral"
  │
  ▼
[Layer 2] dm-npc.sh
  ├── source common.sh
  ├── dispatch_middleware "dm-npc.sh" "create" args...
  │   └── No module handles npc-create → returns 1
  ├── uv run python lib/world_graph.py npc-create "Grimjaw" --description "A scarred orc blacksmith" --attitude "neutral"
  │   │
  │   ▼
  │ [Layer 3] world_graph.py.npc_create()
  │   ├── Validates name (validators.py)
  │   ├── Reads world.json
  │   ├── Creates node: "npc:grimjaw" {type: "npc", name: "Grimjaw", data: {...}}
  │   ├── Creates edge: "npc:grimjaw" → current_location (type: "at")
  │   ├── Writes world.json
  │   └── Returns success + NPC summary
  │         │
  │         ▼
  │       [Layer 4] world.json READ+WRITE (add node + edge)
  │
  └── dispatch_middleware_post "dm-npc.sh" "create" args...
      └── (no post-hooks registered)
```

### Trace 4: Movement with World-Travel Module

```
User: /dm-session move "Volcano Temple" --elapsed 4
  │
  ▼
[Layer 2] dm-session.sh
  ├── dispatch_middleware "dm-session.sh" "move" "Volcano Temple" "--elapsed" "4"
  │   └── world-travel module IS enabled
  │       └── Execute modules/world-travel/middleware/dm-session.sh "move" args...
  │           ├── Calculate distance via BFS pathfinding
  │           ├── Roll encounter checks per distance segment
  │           ├── Update player location
  │           ├── Return 0 (HANDLED)
  │           │
  │           ▼ [Layer 4] world.json READ+WRITE
  │
  ├── exit $? (0 = handled, CORE skipped)
  │
  └── dispatch_middleware_post "dm-session.sh" "move" args...
      └── (no post-hooks registered)
```

### Trace 5: Document Extraction to World State

```
dm-extract.sh prepare "dungeon.pdf" "campaign-name"
  → agent_extractor.py.prepare()
    → Reads PDF via content_extractor.py
    → Chunks text via semantic_chunker.py
    → Stores chunks in campaigns/{name}/chunks/
    → Embeds chunks via embedder.py → vectors/ (Chroma)

dm-extract.sh merge "campaign-name"
  → agent_extractor.py.merge()
    → Reads extracted/*.json (from Claude extraction agents)
    → Validates with extraction_schemas.py
    → Combines into merged-results.json

dm-extract.sh save "campaign-name"
  → agent_extractor.py.save()
    → Reads merged-results.json
    → Creates nodes in world.json (NPCs, locations, items, etc.)
    → Creates edges (relationships between entities)
    → world.json is now populated with extracted content
```

---

## Data Storage Layout

```
world-state/
├── active-campaign.txt                    # Name of active campaign
└── campaigns/{campaign-name}/
    ├── world.json                         # PRIMARY: unified graph (nodes + edges)
    ├── campaign-overview.json             # Metadata: name, date, time, rules, modules
    ├── session-log.md                     # Session history (append-only)
    ├── module-data/                       # Per-module persistent state
    │   ├── world-travel.json
    │   └── mass-combat.json
    ├── saves/                             # Named save points
    │   └── {timestamp}-{name}.json
    ├── vectors/                           # Chroma vector store (RAG)
    ├── extracted/                         # Agent extraction output
    └── chunks/                            # Prepared document chunks
```

### world.json Schema (Graph Database)

```json
{
  "meta": {"version": 2, "schema": "graph"},
  "nodes": {
    "{type}:{id}": {
      "type": "player|npc|location|item|creature|fact|quest|consequence|...",
      "name": "Display Name",
      "data": { /* type-specific fields */ }
    }
  },
  "edges": [
    {"from": "node-id", "to": "node-id", "type": "at|owns|connected|requires|...", "data": {}}
  ]
}
```

**Node types** (20+): player, npc, location, item, creature, fact, quest, consequence, spell, technique, potion, material, artifact, weapon, armor, tool, book, chapter, cantrip, effect, misc

**Edge types** (12+): at, owns, connected, requires, involves, trained, sells, spawns_at, known_by, relationship, triggers, crafted_with

### campaign-overview.json Schema

```json
{
  "campaign_name": "string",
  "genre": "string",
  "tone": {"horror": 0, "comedy": 0, "drama": 0},
  "narrator_style": "string",
  "current_date": "string",
  "time_of_day": "string",
  "precise_time": "HH:MM",
  "game_date": "string",
  "player_position": {"current_location": "string", "previous_location": "string|null"},
  "current_character": "player:active",
  "session_count": 0,
  "currency": { /* denomination config */ },
  "calendar": { /* months, weekdays, epoch */ },
  "campaign_rules": {
    "modules": {"module-id": true|false}
  }
}
```

---

## Key Architectural Patterns

### Pattern 1: Thin Bash Wrapper + Python Delegate

Every tool follows the same structure: source common.sh, parse args, delegate to Python. No business logic lives in bash.

### Pattern 2: Pre/Post Middleware Hooks

Modules can intercept any tool call before CORE runs (pre-hook, return 0 to handle) or augment after CORE runs (post-hook, always executes). This enables extensibility without modifying core tools.

### Pattern 3: Graph-First Storage

All game entities are nodes in a unified graph (`world.json`). Relationships are edges. This replaces the legacy flat-file approach (npcs.json, locations.json, etc.) with a single queryable structure.

### Pattern 4: Lazy RAG Loading

The RAG subsystem (vector store, embedder) is expensive to initialize. `entity_enhancer.py` lazy-loads it only when first needed, with graceful fallback if dependencies are missing.

### Pattern 5: Campaign Isolation

Each campaign gets its own directory under `world-state/campaigns/`. Module enablement, data files, and saves are all per-campaign. The active campaign is tracked in `active-campaign.txt`.

### Pattern 6: Module Agnosticism

Modules must be campaign-agnostic (no character names, setting-specific rules). Campaign-specific configuration goes in `campaign-overview.json` only; fact nodes live in `world.json`.
