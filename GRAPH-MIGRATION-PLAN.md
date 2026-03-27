# WorldGraph — Unified Entity Graph System

## What We Built

Single `lib/world_graph.py` (2500+ lines) replaces 7 separate JSON files and 6 Python managers with one unified entity graph.

### Before (old architecture)
```
character.json + inventory-system.json + inventory-party.json +
npcs.json + locations.json + facts.json + wiki.json +
consequences.json + plots.json + module-data/custom-stats.json
= 10 files, 7 managers, string-based references, no integrity
```

### After (WorldGraph)
```
world.json (one file, 218+ nodes, typed edges)
campaign-overview.json (metadata only: time, calendar, narrator)
= 2 files, 1 manager, ID-based references, full integrity
```

## Campaign Structure
```
campaigns/<name>/
  world.json              ← ALL game data (nodes + edges)
  campaign-overview.json  ← time, calendar, modules, narrator
  campaign-rules.md       ← per-campaign rules
  session-log.md          ← session history
  session-handoff.md      ← context for continuation
```

## Node Types
player, npc, location, item, creature, fact, quest, consequence, spell, technique, potion, material, artifact, weapon, armor, tool, book, chapter, cantrip, effect, misc, campaign

## Edge Types
at, owns, connected, requires, involves, trained, sells, spawns_at, known_by, relationship, triggers, crafted_with

## Node ID Format
`type:kebab-name` with Cyrillic transliteration (Эльза → npc:elza-krants)

## Features (all in world_graph.py)

### Entity CRUD
- add_node, get_node, update_node, remove_node (cascade edges)
- add_edge, get_edges, remove_edge, get_neighbors
- list_nodes (by type), search_nodes (fuzzy)

### NPC Domain
- npc_create, npc_event, npc_promote, npc_locate

### Location Domain
- location_create, location_connect (bidirectional)

### Facts
- fact_add (auto-ID: fact:lore-001)

### Quests
- quest_create, quest_objective_add/complete, quest_complete/fail

### Consequences
- consequence_add (with --hours), consequence_tick, consequence_resolve

### Inventory (embedded on nodes)
- inventory_add/remove, inventory_add_unique/remove_unique
- inventory_show, inventory_transfer, inventory_loot
- inventory_craft (recipes from requires edges), inventory_use

### Player
- player_show, player_hp, player_xp, player_gold, player_hp_max
- player_condition (add/remove/list), player_set

### Wiki (items, creatures, spells as nodes)
- wiki_add (auto-creates requires edges for recipe ingredients)
- wiki_show, wiki_list, wiki_search, wiki_remove, wiki_recipe

### Custom Stats (CORE, not module)
- custom_stat_define, custom_stat_get, custom_stat_set, custom_stat_list
- Rates, sleep_rate, min/max clamping

### Timed Effects
- timed_effect_add (rate_mod, instant, hours), timed_effect_list

### Tick Engine
- tick(elapsed_hours, sleeping) — one call does everything:
  - Custom stats decay (rate * hours, sleep_rate if sleeping)
  - Timed effects (apply rate_mod, expire finished)
  - Production (location nodes, dice rolls, consume/produce items)
  - Expenses (deduct from player money)
  - Income (dice roll, add to player money)
  - Consequences (advance timers)
  - Threshold warnings

### Economy (campaign:economy node)
- Recurring expenses, income, production, random events
- All configurable per campaign

## CLI
`tools/dm-world.sh` — 55+ subcommands. All old tools (dm-npc.sh, dm-location.sh, etc.) rewired as thin wrappers.

## Auto-Combat (in dice.py)
- `--target "creature"` — reads creature AC from world.json, auto-damage on hit
- `--defend --from "creature"` — creature attacks player from world.json stats
- `--spell "name" --target "creature"` — spell attacks and save-based spells
- `--range N` — auto-disadvantage beyond normal range
- Ammo auto-deduction from inventory

## Dashboard
`tools/dm-dashboard/renderer.py` reads exclusively from world.json + campaign-overview.json.

## What Was Deleted
- lib/npc_manager.py, location_manager.py, note_manager.py, plot_manager.py (~2300 lines)
- lib/survival_engine.py (~1350 lines), action_tracker.py (~130 lines)
- custom-stats module entirely (~1300 lines)
- Old test files
- **Total deleted: ~5000+ lines**

## What Remains (deprecated, for inactive modules)
- lib/player_manager.py — used by world-travel, firearms-combat modules
- lib/inventory_manager.py — used by world-travel module
- lib/consequence_manager.py — used by old middleware
- lib/wiki_manager.py — imported by inventory_manager
- lib/entity_manager.py + json_ops.py — base classes for above

These will be removed when deprecated modules (world-travel, firearms-combat) are migrated or deleted.

## Tests
153 passing: 42 WorldGraph core + 21 tick engine + 90 other CORE tests
