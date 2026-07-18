# WorldGraph — Unified Entity Graph System

## What We Built

One authoritative entity graph replaces the former flat gameplay files. `WorldGraph` remains the compatibility facade, while `WorldRepository` owns locking, revisions, atomic writes, and transactions.

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
= 2 authoritative files, ID-based references, atomic graph commits
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

### Economy (`misc:economy` node)
- Recurring expenses, income, production, random events
- All configurable per campaign

## CLI
`tools/dm-world.sh` — 55+ subcommands. All old tools (dm-npc.sh, dm-location.sh, etc.) rewired as thin wrappers.

`tools/dm-scene.sh` batches a full scene transition — location creation,
connection, party movement, time tick, consequence resolution, and quest updates
— through one external command and one WorldGraph transaction.

## Persistence

- `lib/world_repository.py` coordinates every graph writer with `flock`.
- Commits use a temporary file, `fsync`, and atomic `os.replace`.
- `meta.revision` rejects stale snapshots instead of silently overwriting them.
- `with graph.transaction():` loads once, commits once, and rolls back on error.
- Campaign bootstrap, save restore, and reset use the same repository path.

## Auto-Combat (in dice.py)
- `--target "creature"` — reads creature AC from world.json, auto-damage on hit
- `--defend --from "creature"` — creature attacks player from world.json stats
- `--spell "name" --target "creature"` — spell attacks and save-based spells
- `--range N` — auto-disadvantage beyond normal range
- Ammo auto-deduction from inventory

## Dashboard
The integrated FastAPI web UI reads player-safe projections from `world.json`
through `backend/campaign_views.py` and `backend/map_view.py`.

## What Was Deleted
- lib/npc_manager.py, location_manager.py, note_manager.py, plot_manager.py (~2300 lines)
- lib/player_manager.py and inventory_manager.py after their callers migrated
- lib/survival_engine.py (~1350 lines), action_tracker.py (~130 lines)
- custom-stats module entirely (~1300 lines)
- Old test files
- The world-travel module was retained and migrated to a WorldGraph projection layer.

## Remaining compatibility boundary

- `lib/json_ops.py` remains for non-graph metadata such as campaign overview and session snapshots.
- `campaign-overview.json` still carries display-oriented position metadata for existing clients; gameplay entities remain authoritative in `world.json`.
- The WorldGraph facade is intentionally preserved so existing shell tools keep one stable API while domain services are extracted incrementally.

## Tests
Run `uv run pytest` for the complete CORE and active-module suite.
