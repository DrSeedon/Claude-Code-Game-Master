# Graph Migration Plan — Unified World State

## Goal
Replace 7+ JSON files with one unified entity graph. All game objects (NPCs, locations, items, creatures, facts, quests) become nodes with typed edges. One file, one manager, one source of truth.

## Why
Current state: 7 files (character.json, inventory-system.json, inventory-party.json, npcs.json, locations.json, facts.json, wiki.json) + 2 more (consequences.json, plots.json). All linked by **string name matching** — rename an NPC and inventory breaks, rename a location and character.json points to nothing. No validation, no cascade, no integrity.

## Current Data Map

```
character.json          → stats, level, equipment, money, xp, save_proficiencies
inventory-system.json   → player items {stackable: {name: {qty, weight}}, unique: [strings]}
inventory-party.json    → NPC items, keyed by NPC name (exact match required)
npcs.json               → NPC data + party member character_sheets (embedded)
locations.json          → locations + connections graph (already a graph!)
facts.json              → flat arrays of lore/events/rumors/economy
wiki.json               → game mechanics: items, recipes, creatures, spells (has refs = mini-graph)
consequences.json       → timed events with triggers
plots.json              → quests with objectives, NPC refs, location refs
campaign-overview.json  → metadata: time, calendar, modules, narrator (STAYS SEPARATE)
```

## Target: world.json

```json
{
  "meta": {"version": 2, "schema": "graph"},
  "nodes": {
    "player:wilhelm": {
      "type": "player",
      "name": "Вильгельм Кнохенштих",
      "data": {
        "stats": {"str": 10, "dex": 13, ...},
        "level": 5, "hp": {"current": 28, "max": 28}, "ac": 12,
        "save_proficiencies": ["int", "wis"],
        "skills": {"оккультизм": {"total": 7, "breakdown": {...}}},
        "equipment": {"armor": {...}, "weapons": [...]},
        "money": 897, "xp": {"current": 9325, "next_level": 14000},
        "abilities": [...], "features": [...]
      },
      "inventory": {
        "stackable": {"Arrows": {"qty": 20, "weight": 0.02}},
        "unique": ["Liber Mortis [1.5kg]", "Кинжал Греты [0.4kg]"]
      }
    },
    "npc:elsa": {
      "type": "npc",
      "name": "Эльза Кранц",
      "data": {
        "description": "Жрица Моррь",
        "attitude": "intimate",
        "character_sheet": {"level": 4, "hp": {...}, ...}
      },
      "inventory": {
        "stackable": {},
        "unique": ["Медальон Моррь [0.1kg]"]
      },
      "events": [{"event": "...", "timestamp": "..."}]
    },
    "location:workshop": {
      "type": "location",
      "name": "Мастерская у южного кладбища",
      "data": {
        "description": "...",
        "discovered": "2026-03-23..."
      }
    },
    "item:healing-potion": {
      "type": "item",
      "name": "Отвар покоя",
      "data": {
        "mechanics": {"effect": "dark_power -(1d3+2)", "cooldown": "2 days"},
        "recipe": {"skill": "алхимия", "dc": 9, "ingredients": {"полынь": 1, "лаванда": 1, "валериана": 1}}
      }
    },
    "creature:goblin": {
      "type": "creature",
      "name": "Goblin",
      "data": {
        "mechanics": {"hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d6+1", "xp": 50}
      }
    },
    "fact:lore-001": {
      "type": "fact",
      "name": "Liber Mortis найден в архиве",
      "data": {
        "category": "lore",
        "text": "Liber Mortis найден в подвальном архиве ратуши Вортбада..."
      }
    },
    "quest:destroy-anchor": {
      "type": "quest",
      "name": "Уничтожить якорь Стража",
      "data": {
        "status": "completed",
        "objectives": [{"text": "Найти вход в катакомбы", "completed": true}]
      }
    },
    "consequence:witch-hunters": {
      "type": "consequence",
      "name": "Охотники на Ведьм",
      "data": {
        "trigger": "suspicion >= 20",
        "trigger_hours": 48,
        "hours_elapsed": 12
      }
    }
  },
  "edges": [
    {"from": "player:wilhelm", "to": "location:workshop", "type": "at"},
    {"from": "player:wilhelm", "to": "item:healing-potion", "type": "owns", "qty": 1},
    {"from": "player:wilhelm", "to": "npc:elsa", "type": "relationship", "data": "intimate"},
    {"from": "npc:elsa", "to": "location:workshop", "type": "at"},
    {"from": "npc:elsa", "to": "player:wilhelm", "type": "trained", "data": "русло Шайиша"},
    {"from": "location:workshop", "to": "location:market", "type": "connected", "path": "traveled"},
    {"from": "item:healing-potion", "to": "item:полынь", "type": "requires", "qty": 1},
    {"from": "creature:goblin", "to": "location:forest", "type": "spawns_at"},
    {"from": "quest:destroy-anchor", "to": "npc:marta", "type": "involves"},
    {"from": "quest:destroy-anchor", "to": "location:catacombs", "type": "at"},
    {"from": "fact:lore-001", "to": "player:wilhelm", "type": "known_by"}
  ]
}
```

## What Stays Separate
- **campaign-overview.json** — metadata, time, calendar, modules, narrator style, encounters config. NOT game entities.
- **session-log.md** — session history (text file, append-only)
- **session-handoff.md** — session continuity doc
- **campaign-rules.md** — per-campaign rules
- **module-data/custom-stats.json** — stat engine config (rates, thresholds). Could migrate later.
- **module-data/firearms-combat.json** — weapon database for firearms module. Stays until wiki absorbs it.

## Migration Phases

### Phase 1: Unified Entity Manager (lib/entity_manager.py)
- New `EntityManager` class: CRUD for nodes + edges
- Node types: player, npc, location, item, creature, fact, quest, consequence, spell, technique
- Edge types: at, owns, connected, requires, involves, trained, spawns_at, known_by, sells, relationship
- API:
  - `add_node(type, id, name, data)` / `get_node(id)` / `update_node(id, data)` / `remove_node(id)`
  - `add_edge(from, to, type, data?)` / `get_edges(node_id, type?)` / `remove_edge(from, to, type)`
  - `query(type=, tag=, name_contains=)` — search nodes
  - `neighbors(node_id, edge_type=)` — traverse graph
- File: `world.json` in campaign dir
- Backward compat: old files still readable during migration

### Phase 2: Tool Adapters (thin wrappers)
Each existing tool keeps its CLI interface but reads/writes through EntityManager:
- `dm-npc.sh` → EntityManager queries `type=npc`
- `dm-location.sh` → EntityManager queries `type=location`
- `dm-note.sh` → EntityManager creates `type=fact` nodes
- `dm-wiki.sh` → EntityManager queries `type=item|creature|spell|technique`
- `dm-inventory.sh` → EntityManager manages `owns` edges + node inventory
- `dm-plot.sh` → EntityManager manages `type=quest` nodes + `involves` edges
- `dm-consequence.sh` → EntityManager manages `type=consequence` nodes
- `dm-player.sh` → EntityManager manages `type=player` node

User-facing CLI **does not change**. Same commands, same flags. Only storage changes.

### Phase 3: Migration Script
- `lib/migrate_to_graph.py` — reads all old JSON files, creates world.json
- For each entity: generate node ID (`type:kebab-name`)
- For each implicit reference: create edge
- Validate: no orphan edges, no duplicate IDs
- Reversible: can export back to old format

### Phase 4: Dynamic Features (free from graph)
Once graph is live, these come naturally:
- **Auto-DC-Mod from Inventory**: `dm-roll.sh --skill "alchemy"` → traverse `player → owns → item` edges → check which items have dc_mod → apply
- **NPC inventory inline**: `dm-npc.sh status "Grimjaw"` → traverse `npc:grimjaw → owns → item` edges → show inventory
- **Location contents**: `dm-location.sh show "Tavern"` → traverse `* → at → location:tavern` edges → show NPCs + items present
- **Quest tracking**: `dm-plot.sh show "quest-id"` → traverse `quest → involves → npc` + `quest → at → location` edges → show full context
- **Relationship graph**: who knows whom, who trained whom, who sells what

## Node ID Convention
- `player:kebab-name` (e.g. `player:wilhelm`)
- `npc:kebab-name` (e.g. `npc:elsa-krantz`)
- `location:kebab-name` (e.g. `location:workshop`)
- `item:kebab-name` (e.g. `item:healing-potion`)
- `creature:kebab-name` (e.g. `creature:goblin`)
- `fact:category-NNN` (e.g. `fact:lore-001`)
- `quest:kebab-name` (e.g. `quest:destroy-anchor`)
- `consequence:kebab-name` (e.g. `consequence:witch-hunters`)
- `spell:kebab-name` (e.g. `spell:fire-bolt`)

## Edge Types
| Edge | From → To | Meaning |
|------|-----------|---------|
| `at` | player/npc → location | Currently located here |
| `owns` | player/npc → item | Has in inventory (qty in edge data) |
| `connected` | location → location | Can travel between (path type in data) |
| `requires` | item → item | Recipe ingredient (qty in data) |
| `involves` | quest → npc/location | Quest references this entity |
| `trained` | npc → player | NPC taught player something (skill in data) |
| `sells` | npc → item | NPC sells this item (price in data) |
| `spawns_at` | creature → location | Creature found here |
| `known_by` | fact → player/npc | Who knows this fact |
| `relationship` | player ↔ npc | Social bond (type in data: ally, enemy, intimate) |
| `triggers` | consequence → any | What the consequence affects |
| `crafted_with` | item → item | Tool needed for crafting |

## Risks
- **Migration bugs**: string→ID mapping can fail on fuzzy/duplicate names
- **Performance**: single large JSON vs many small ones. Probably fine under 10k nodes
- **Module compat**: custom-stats, firearms-combat read module-data directly. Need adapters
- **Session restore**: snapshots currently copy individual files. Need new snapshot format

## Estimated Effort
- Phase 1 (EntityManager): 1 session
- Phase 2 (Tool Adapters): 2-3 sessions (7 tools to adapt)
- Phase 3 (Migration): 1 session
- Phase 4 (Dynamic Features): ongoing, each feature = small PR
- Total: ~5 sessions of focused work

## When to Start
After at least 1 new campaign is played with current system. Wiki needs battle-testing with creatures, spells, recipes in actual combat. Graph migration should solve REAL problems, not theoretical ones.
