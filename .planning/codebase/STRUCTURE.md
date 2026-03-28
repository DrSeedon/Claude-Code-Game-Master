# Codebase Structure

**Analysis Date:** 2026-03-28

## Directory Layout

```
Claude-Code-Game-Master/
├── lib/                          # CORE Python domain logic
│   ├── world_graph.py            # Unified entity graph (primary data layer)
│   ├── entity_manager.py         # Base class for all managers
│   ├── session_manager.py        # Session lifecycle, saves, party movement
│   ├── player_manager.py         # XP, HP, conditions, custom stats
│   ├── inventory_manager.py      # Items, weight, currency transfers
│   ├── dice.py                   # Dice engine with DC/AC/skill auto-lookup
│   ├── wiki_manager.py           # Structured knowledge base
│   ├── time_manager.py           # Game clock, auto-tick
│   ├── campaign_manager.py       # Campaign creation/switching
│   ├── consequence_manager.py    # Timed events
│   ├── currency.py               # Universal currency system
│   ├── calendar.py               # Universal calendar system
│   ├── entity_enhancer.py        # RAG-based entity enrichment
│   ├── encounter_engine.py       # Random encounter logic
│   ├── search.py                 # Hybrid search (world-state + RAG)
│   ├── agent_extractor.py        # Claude agent extraction orchestration
│   ├── content_extractor.py      # Source material text extraction
│   ├── extraction_schemas.py     # Pydantic schemas for extraction
│   ├── json_ops.py               # Atomic JSON read/write helpers
│   ├── validators.py             # Input validation
│   ├── colors.py                 # Terminal color constants
│   ├── world_stats.py            # World statistics aggregation
│   └── rag/                      # RAG subsystem
│       ├── embedder.py           # Embedding generation
│       ├── vector_store.py       # LanceDB vector store
│       ├── semantic_chunker.py   # Text chunking
│       ├── quote_extractor.py    # Quote extraction
│       ├── extraction_queries.py # Predefined extraction queries
│       └── rag_extractor.py      # Full RAG extraction pipeline
├── tools/                        # CORE Bash wrapper CLIs
│   ├── common.sh                 # Shared: Python detection, paths, middleware wiring
│   ├── dm-roll.sh                # Dice (→ dice.py)
│   ├── dm-inventory.sh           # Inventory (→ inventory_manager.py)
│   ├── dm-status.sh              # Compact inventory status
│   ├── dm-session.sh             # Session lifecycle (→ session_manager.py)
│   ├── dm-player.sh              # Player state (→ player_manager.py)
│   ├── dm-npc.sh                 # NPCs (→ world_graph.py npc nodes)
│   ├── dm-location.sh            # Locations (→ world_graph.py location nodes)
│   ├── dm-note.sh                # World facts (→ world_graph.py fact nodes)
│   ├── dm-plot.sh                # Quests (→ plot_manager.py)
│   ├── dm-consequence.sh         # Timed events (→ consequence_manager.py)
│   ├── dm-time.sh                # Game clock (→ time_manager.py)
│   ├── dm-campaign.sh            # Campaign management (→ campaign_manager.py)
│   ├── dm-wiki.sh                # Knowledge base (→ wiki_manager.py)
│   ├── dm-world.sh               # Unified WorldGraph CLI (primary)
│   ├── dm-search.sh              # Hybrid search (→ entity_enhancer.py)
│   ├── dm-enhance.sh             # RAG enhancement (→ entity_enhancer.py)
│   ├── dm-condition.sh           # Conditions (→ player_manager.py condition)
│   ├── dm-overview.sh            # World state overview (multi-tool)
│   ├── dm-extract.sh             # Source material extraction
│   └── dm-dashboard/             # Terminal dashboard (standalone)
├── .claude/
│   ├── settings.json             # Hook configuration (UserPromptSubmit, PostToolUse)
│   ├── commands/                 # Claude Code skill definitions
│   │   ├── dm.md                 # Primary DM command (campaign select + session start)
│   │   ├── dm-continue.md        # Resume session
│   │   ├── new-game.md           # New campaign creation
│   │   ├── import.md             # Import source material
│   │   ├── dm-save.md            # Save system
│   │   ├── create-character.md   # Character creation
│   │   ├── setup.md              # First-time setup
│   │   ├── reset.md              # Campaign reset
│   │   ├── enhance.md            # RAG enhancement
│   │   ├── help.md               # Help
│   │   └── world-check.md        # World state checker
│   ├── hooks/                    # UserPromptSubmit + PostToolUse hooks
│   │   ├── dm-hook-common.sh     # Shared preamble (filters non-DM prompts)
│   │   ├── dm-load-rules.sh      # Hook 1: compile rules → /tmp/dm-rules.md
│   │   ├── dm-load-campaign.sh   # Hook 2: campaign state → context
│   │   ├── dm-load-session.sh    # Hook 3: quests/consequences/log → context
│   │   └── check-language-policy.sh  # PostToolUse: enforce English in rules files
│   ├── agents/                   # Specialist sub-agents (Claude Code agent definitions)
│   │   ├── monster-manual.md     # D&D 5e API monster stats fetcher
│   │   ├── npc-builder.md        # NPC backstory/personality
│   │   ├── loot-dropper.md       # Loot generation
│   │   ├── world-builder.md      # World building
│   │   ├── dungeon-architect.md  # Dungeon design
│   │   ├── rules-master.md       # Rules adjudication
│   │   ├── spell-caster.md       # Spell mechanics
│   │   ├── gear-master.md        # Equipment management
│   │   ├── create-character.md   # Character creation agent
│   │   └── extractor-*.md        # Source material extractors (items/locations/npcs/plots)
│   └── additional/
│       ├── dm-slots/             # DM rules slot files (loaded into context)
│       │   ├── _preamble.md      # Always first, cannot be replaced
│       │   ├── combat.md         # Combat rules
│       │   ├── narration.md      # Narration style
│       │   ├── movement.md       # Movement (replaceable by world-travel)
│       │   └── *.md              # 20+ additional slots
│       ├── narrator-styles/      # Narrator style definitions
│       │   ├── sarcastic-puns.md
│       │   ├── serious-cinematic.md
│       │   ├── horror-atmospheric.md
│       │   ├── epic-heroic.md
│       │   └── cognitive-rendering.md
│       ├── modules/              # Optional gameplay modules
│       │   ├── custom-stats/     # Character stat tracking (survival, stamina, etc.)
│       │   ├── world-travel/     # Navigation, maps, encounters (replaces movement slot)
│       │   ├── mass-combat/      # Large-scale battle resolution
│       │   └── firearms-combat/  # Modern/STALKER firearms system
│       ├── infrastructure/       # Module system loader scripts
│       │   ├── common-module.sh  # find_project_root() utility
│       │   ├── common-advanced.sh # dispatch_middleware() + dispatch_middleware_post()
│       │   ├── module_data.py    # ModuleDataManager Python class
│       │   ├── dm-active-modules-rules.sh  # Rules assembler (slots + module overrides)
│       │   ├── dm-campaign-rules.sh        # Campaign-specific rule loader
│       │   ├── dm-narrator.sh              # Narrator style loader
│       │   └── tools/
│       │       ├── dm-module.sh            # Module enable/disable/list CLI
│       │       └── dm-module-status.sh     # Module status display
│       └── campaign-rules-templates/  # Starter templates for new campaigns
├── world-state/
│   ├── active-campaign.txt       # Single line: active campaign name
│   ├── usage/
│   │   └── token-usage.log       # Tab-separated token usage log
│   └── campaigns/
│       └── <campaign-name>/      # One directory per campaign
│           ├── world.json        # WorldGraph (ALL game entities — primary data)
│           ├── campaign-overview.json  # Metadata: time, date, modules, narrator, genre
│           ├── campaign-rules.md # Campaign-specific DM rules (appended to /tmp/dm-rules.md)
│           ├── session-log.md    # Append-only session history
│           ├── session-handoff.md # Optional: cross-session handoff note
│           ├── saves/            # Named JSON snapshots of world.json
│           ├── extracted/        # RAG-extracted source material
│           ├── module-data/      # Per-module JSON state files
│           │   ├── custom-stats.json
│           │   ├── inventory-system.json
│           │   └── *.json
│           └── vectors/          # LanceDB vector store (if RAG enabled)
├── tests/                        # pytest test suite
│   ├── conftest.py
│   ├── test_world_graph.py
│   ├── test_session_manager.py
│   ├── test_player_manager.py
│   ├── test_dice_combat.py
│   ├── test_consequence_manager.py
│   ├── test_encounter_engine.py
│   └── test_tick_engine.py
├── features/                     # Standalone feature scripts (character creation, loot, etc.)
│   ├── character-creation/
│   ├── dnd-api/
│   ├── gear/
│   ├── loot/
│   ├── rules/
│   └── spells/
├── lancedb/                      # Global LanceDB vector index (shared across campaigns)
├── source-material/              # Raw source books/PDFs for RAG extraction
├── docs/                         # Production documentation
├── pyproject.toml                # Python package config (uv managed)
├── uv.lock                       # Locked dependencies
└── CLAUDE.md                     # Dev rules (this project's CLAUDE.md)
```

## Directory Purposes

**`lib/` (CORE Python):**
- Purpose: All domain logic — no UI, no Bash, pure Python
- Contains: Manager classes (one per domain), utilities, RAG subsystem
- Key files: `world_graph.py` (data layer), `entity_manager.py` (base class for all managers)
- Naming: `snake_case.py`

**`tools/` (CORE Bash):**
- Purpose: CLI wrappers exposing `lib/` to Claude Code and terminal
- Contains: One `.sh` per domain tool + `common.sh` shared utilities
- Pattern: Source `common.sh`, call `dispatch_middleware`, then invoke Python, then `dispatch_middleware_post`
- Naming: `dm-<domain>.sh`

**`.claude/commands/` (Claude Code Skills):**
- Purpose: Define what Claude does when player types `/command`
- Contains: Markdown files — each is a complete prompt template with instructions, examples, tool call sequences
- Naming: `<command-name>.md` matching the slash command

**`.claude/hooks/` (Context Injection):**
- Purpose: Automatically inject DM rules and campaign state before each DM prompt
- Contains: Three `UserPromptSubmit` hooks + one `PostToolUse` hook
- Pattern: Filter by prompt content (`dm-hook-common.sh`), then emit to stdout (→ context) or `/tmp/` file

**`.claude/agents/` (Specialist Sub-agents):**
- Purpose: Specialist Claude sub-agents invoked by DM for domain tasks (monster stats, loot, NPCs)
- Contains: YAML-frontmatter agent definitions with system prompts
- Pattern: `name:`, `description:`, `tools:`, `color:`, then markdown prompt body

**`.claude/additional/modules/<name>/` (Module):**
- Purpose: Optional gameplay extension, self-contained
- Required files: `module.json` (manifest with `id`, `replaces`, `middleware`, `features`), `rules.md` (DM rules)
- Optional: `lib/` (Python), `tools/` (CLIs), `middleware/<tool>.sh` (pre-hook), `middleware/<tool>.sh.post` (post-hook), `tests/`

**`.claude/additional/dm-slots/` (DM Rules Slots):**
- Purpose: Modular DM rules — each file = one topic area, replaceable by modules
- Naming: `<slot-id>.md` (slot ID matches what modules declare in `"replaces"`)
- Special: `_preamble.md` always loads first, never replaceable

**`world-state/campaigns/<name>/` (Campaign Data):**
- Purpose: All persistent state for one campaign
- Primary file: `world.json` (WorldGraph — all entities and relationships)
- Secondary: `campaign-overview.json` (metadata and module toggles)
- Do not add new top-level JSON files — put new entity types as nodes in `world.json`

## Key File Locations

**Entry Points:**
- `.claude/commands/dm.md`: Primary player-facing DM command
- `.claude/commands/dm-continue.md`: Session resume command
- `.claude/settings.json`: Hook wiring configuration

**Configuration:**
- `world-state/active-campaign.txt`: Active campaign pointer (one line)
- `world-state/campaigns/<name>/campaign-overview.json`: Campaign metadata + module toggles
- `world-state/campaigns/<name>/campaign-rules.md`: Campaign-specific DM rules
- `pyproject.toml`: Python dependencies and package config

**Core Logic:**
- `lib/world_graph.py`: WorldGraph — read this to understand the data model
- `lib/entity_manager.py`: Base class — read before creating new managers
- `tools/common.sh`: Shared Bash utilities — source of truth for path resolution
- `.claude/additional/infrastructure/common-advanced.sh`: Middleware dispatch — how modules intercept CORE

**Testing:**
- `tests/` — pytest, run via `uv run pytest`
- Module tests: `.claude/additional/modules/<name>/tests/`

## Naming Conventions

**Files:**
- Python libs: `snake_case.py` (e.g., `world_graph.py`, `inventory_manager.py`)
- Bash tools: `dm-<domain>.sh` (e.g., `dm-roll.sh`, `dm-session.sh`)
- Claude commands: `<command-name>.md` matching slash command
- DM slots: `<slot-id>.md` (kebab-case)
- Module manifests: `module.json`

**Directories:**
- Modules: kebab-case IDs matching `module.json` `"id"` field (e.g., `world-travel`, `firearms-combat`)
- Campaigns: kebab-case (e.g., `blood-arena`, `clone-wars`)

**WorldGraph Node IDs:**
- Format: `type:kebab-name` (e.g., `npc:merchant-ivan`, `location:market-square`, `player:main`)
- Type must be in `NODE_TYPES` list in `lib/world_graph.py`
- Name part: lowercase, alphanumeric, hyphens only

## Where to Add New Code

**New domain manager (e.g., "trap system"):**
- Implementation: `lib/trap_manager.py` (extend `EntityManager`)
- Bash wrapper: `tools/dm-trap.sh` (source `common.sh`, call dispatch, invoke Python)
- Expose in `tools/dm-world.sh` if using WorldGraph nodes
- Tests: `tests/test_trap_manager.py`

**New optional feature:**
- Create module: `.claude/additional/modules/<module-id>/`
- Required: `module.json`, `rules.md`
- Python: `.claude/additional/modules/<module-id>/lib/`
- Middleware: `.claude/additional/modules/<module-id>/middleware/dm-<tool>.sh`
- Module data: `world-state/campaigns/<name>/module-data/<module-id>.json`

**New Claude Code command:**
- Implementation: `.claude/commands/<command-name>.md`
- Follow pattern of existing commands: step-by-step instructions + bash tool call sequences

**New DM rule block:**
- Standalone: `.claude/additional/dm-slots/<slot-id>.md`
- Override existing: create module with `"replaces": ["<slot-id>"]` in `module.json`

**New entity type in WorldGraph:**
- Add type string to `NODE_TYPES` in `lib/world_graph.py`
- Optionally add edge type to `EDGE_TYPES`
- Add color entry to `TYPE_COLORS` dict

**New specialist agent:**
- Implementation: `.claude/agents/<agent-name>.md`
- YAML frontmatter: `name`, `description`, `tools`, `color`

## Special Directories

**`lancedb/`:**
- Purpose: Global LanceDB vector index for RAG
- Generated: Yes (by `dm-extract.sh` / `lib/rag/vector_store.py`)
- Committed: No (in `.gitignore`)

**`world-state/campaigns/<name>/vectors/`:**
- Purpose: Per-campaign vector embeddings
- Generated: Yes
- Committed: No

**`world-state/campaigns/<name>/saves/`:**
- Purpose: Named JSON snapshots of `world.json` for save/restore
- Generated: Yes (by `dm-session.sh save`)
- Committed: Yes (player progress)

**`world-state/campaigns/<name>/extracted/`:**
- Purpose: Raw extracted text from source material before RAG indexing
- Generated: Yes
- Committed: Campaign-dependent

**`features/`:**
- Purpose: Standalone experimental scripts (character creation API, loot tables, D&D API integration)
- Not integrated into CORE tools — exploratory/reference code

**`.planning/`:**
- Purpose: GSD planning documents and codebase analysis
- Committed: Yes

---

*Structure analysis: 2026-03-28*
