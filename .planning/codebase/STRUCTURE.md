# Codebase Structure

**Analysis Date:** 2026-03-29 (post WorldGraph migration)

## Directory Layout

```
Claude-Code-Game-Master/
├── lib/                          # CORE Python domain logic
│   ├── world_graph.py            # Unified entity graph (primary data layer, 2481 lines)
│   ├── entity_manager.py         # Base class for all managers
│   ├── session_manager.py        # Session lifecycle, saves (world.json snapshots), movement
│   ├── player_manager.py         # XP, HP, conditions (WorldGraph player node)
│   ├── inventory_manager.py      # Items, weight, currency, craft/use (WorldGraph)
│   ├── dice.py                   # Dice engine with auto-lookup from WorldGraph
│   ├── time_manager.py           # Game clock, auto-tick
│   ├── campaign_manager.py       # Campaign creation/switching (inits world.json)
│   ├── entity_enhancer.py        # RAG-based entity enrichment (WorldGraph)
│   ├── encounter_engine.py       # Random encounter logic (creatures from world.json)
│   ├── agent_extractor.py        # Source material extraction pipeline (→ WorldGraph)
│   ├── content_extractor.py      # PDF/DOCX text extraction
│   ├── extraction_schemas.py     # Pydantic schemas for extraction
│   ├── module_data.py            # ModuleDataManager (per-module JSON config)
│   ├── json_ops.py               # Atomic JSON read/write helpers
│   ├── currency.py               # Universal currency system
│   ├── calendar.py               # Universal calendar system
│   ├── validators.py             # Input validation
│   ├── colors.py                 # Terminal color constants
│   └── rag/                      # RAG subsystem
│       ├── embedder.py           # Embedding generation (sentence-transformers)
│       ├── vector_store.py       # ChromaDB vector store
│       ├── semantic_chunker.py   # Text chunking
│       ├── quote_extractor.py    # Quote extraction
│       ├── extraction_queries.py # Predefined extraction queries
│       └── rag_extractor.py      # Full RAG extraction pipeline
├── tools/                        # CORE Bash wrapper CLIs
│   ├── common.sh                 # Shared: Python detection, paths, middleware wiring
│   ├── dm-world.sh               # Unified WorldGraph CLI (primary)
│   ├── dm-roll.sh                # Dice (→ dice.py)
│   ├── dm-inventory.sh           # Inventory (→ inventory_manager.py)
│   ├── dm-status.sh              # Compact inventory status
│   ├── dm-session.sh             # Session lifecycle (→ session_manager.py)
│   ├── dm-player.sh              # Player state (→ world_graph.py player node)
│   ├── dm-npc.sh                 # NPCs (→ world_graph.py npc nodes)
│   ├── dm-location.sh            # Locations (→ world_graph.py location nodes)
│   ├── dm-note.sh                # World facts (→ world_graph.py fact nodes)
│   ├── dm-plot.sh                # Quests (→ world_graph.py quest nodes)
│   ├── dm-consequence.sh         # Timed events (→ world_graph.py consequence nodes)
│   ├── dm-time.sh                # Game clock (→ time_manager.py)
│   ├── dm-campaign.sh            # Campaign management (→ campaign_manager.py)
│   ├── dm-wiki.sh                # Knowledge base (→ world_graph.py wiki methods)
│   ├── dm-search.sh              # Hybrid search (→ world_graph.py search + entity_enhancer RAG)
│   ├── dm-enhance.sh             # RAG enhancement (→ entity_enhancer.py)
│   ├── dm-condition.sh           # Conditions (→ world_graph.py player conditions)
│   ├── dm-overview.sh            # World state overview (→ world_graph.py stats)
│   ├── dm-extract.sh             # Source material extraction
│   └── dm-dashboard/             # Web dashboard (standalone HTTP server)
│       ├── __main__.py
│       ├── server.py
│       ├── renderer.py           # Reads world.json for wiki/dashboard
│       ├── shell.html
│       └── style.css
├── .claude/
│   ├── settings.json             # Hook configuration
│   ├── commands/                 # Claude Code skill definitions
│   │   ├── dm.md                 # Primary DM command (campaign select → /dm-continue)
│   │   ├── dm-continue.md        # Resume session (full startup checklist)
│   │   ├── new-game.md           # Campaign creation (modules, narrator, rules, currency, calendar)
│   │   ├── import.md             # Import source material
│   │   ├── create-character.md   # Character creation
│   │   └── *.md                  # save, setup, reset, enhance, help, world-check
│   ├── hooks/                    # UserPromptSubmit + PostToolUse hooks
│   │   ├── dm-hook-common.sh     # Shared preamble (filters non-DM prompts)
│   │   ├── dm-load-rules.sh      # Hook 1: compile rules → /tmp/dm-rules.md
│   │   ├── dm-load-campaign.sh   # Hook 2: campaign state → context
│   │   ├── dm-load-session.sh    # Hook 3: quests/consequences/log → context
│   │   └── check-language-policy.sh  # PostToolUse: enforce English in rules files
│   ├── agents/                   # Specialist sub-agents
│   └── additional/
│       ├── dm-slots/             # DM rules slot files (20+, loaded into context)
│       ├── narrator-styles/      # 5 narrator style definitions
│       ├── campaign-rules-templates/  # Starter templates (zombie, survival, political, etc.)
│       ├── campaign-custom-rules/     # Stackable custom rules (realistic-progression, russian-language)
│       ├── modules/              # Optional gameplay modules
│       │   ├── custom-stats/     # Character stat tracking
│       │   ├── world-travel/     # Navigation, maps, encounters
│       │   ├── mass-combat/      # Large-scale battle resolution
│       │   └── firearms-combat/  # Modern firearms system
│       └── infrastructure/       # Module system loader scripts
│           ├── common-module.sh, common-advanced.sh
│           ├── dm-active-modules-rules.sh
│           ├── dm-campaign-rules.sh
│           ├── dm-campaign-custom-rules.sh
│           ├── dm-narrator.sh
│           └── tools/dm-module.sh
├── world-state/
│   ├── active-campaign.txt       # Active campaign pointer
│   └── campaigns/
│       └── <campaign-name>/
│           ├── world.json        # WorldGraph (ALL game entities — primary data)
│           ├── campaign-overview.json  # Metadata: time, modules, narrator, currency, calendar
│           ├── campaign-rules.md # Campaign-specific + custom rules
│           ├── session-log.md    # Session history
│           ├── saves/            # JSON snapshots of world.json
│           ├── module-data/      # Per-module config (fire_modes, combat_rules — NOT reference data)
│           └── vectors/          # ChromaDB vector store (if RAG enabled)
├── tests/                        # pytest test suite
│   ├── conftest.py
│   ├── test_world_graph.py
│   ├── test_tick_engine.py
│   ├── test_session_manager.py
│   ├── test_player_manager.py
│   ├── test_dice_combat.py
│   └── test_encounter_engine.py
├── features/                     # Standalone feature scripts (D&D API, character creation, loot)
├── pyproject.toml
└── CLAUDE.md                     # Dev rules
```

## Key Rules

**Data in world.json ONLY:**
- All entities (NPCs, locations, items, creatures, weapons, armor, quests, facts, consequences) are nodes in world.json
- No flat JSON files (npcs.json, locations.json, etc.) for campaign state
- Module config (fire_modes, combat_rules) goes in `module-data/<id>.json`
- Reference data (weapon stats, armor stats, creature stats) goes in world.json as nodes

**Where to add new code:**
- New domain logic: `lib/<name>.py` (extend EntityManager)
- New CLI: `tools/dm-<name>.sh` (source common.sh, dispatch middleware)
- New entity type: add to `NODE_TYPES` in `lib/world_graph.py`
- New module: `.claude/additional/modules/<id>/` with `module.json` + `rules.md`
- New custom rule: `.claude/additional/campaign-custom-rules/<id>.md`
- New narrator style: `.claude/additional/narrator-styles/<id>.md`

---

*Structure analysis: 2026-03-29*
