# World State Schema

The runtime has two authoritative JSON documents per campaign:

```text
world-state/campaigns/<slug>/
  world.json
  campaign-overview.json
  campaign-rules.md
  session-log.md
  session-handoff.md
  saves/
  module-data/
  extracted/
```

Legacy `character.json`, `npcs.json`, `locations.json`, `facts.json`,
`consequences.json`, and `plots.json` are import sources only. Run
`tools/dm-migrate-worldgraph.sh <campaign>` to merge them into `world.json`.

## world.json

```json
{
  "meta": {
    "version": 2,
    "schema": "graph",
    "revision": 14
  },
  "nodes": {
    "player:active": {
      "type": "player",
      "name": "Ada",
      "data": {
        "level": 3,
        "hp": {"current": 18, "max": 22},
        "current_location": "Workshop"
      },
      "inventory": {
        "stackable": {},
        "unique": []
      }
    }
  },
  "edges": [
    {
      "from": "npc:guide",
      "to": "location:workshop",
      "type": "at"
    }
  ]
}
```

Node IDs use `<type>:<kebab-id>`. Gameplay fields belong under `data`.
Inventory is the only standard node-owned structure outside `data`.

Common node types are `player`, `npc`, `location`, `item`, `creature`, `fact`,
`quest`, `consequence`, `spell`, `technique`, `effect`, and `misc`.

Common edge types are `at`, `owns`, `connected`, `requires`, `involves`,
`trained`, `sells`, `spawns_at`, `known_by`, `relationship`, `triggers`, and
`crafted_with`.

All graph writes go through `WorldRepository`. It uses a stable lock file,
atomic replacement, a monotonic revision, and transactions.

### Combatant fields

`WorldGraph.combatant_stats()` normalizes player, NPC, and creature schemas.
Creature templates may provide `attack_bonus`/`damage` or the mass-combat
aliases `atk`/`dmg`. `pen` and `prot` default to zero.

Player HP uses `hp.current` and `hp.max`. NPC party HP uses
`character_sheet.hp`. A creature keeps its configured maximum in `hp`; the
first persisted injury creates `hp_current`, which becomes its current HP.

Do not decrement these fields directly. Use `WorldGraph.apply_damage()` or a
complete combat command such as `dm-roll.sh --target`,
`dm-roll.sh --defend --from`, or the firearms resolver.

## campaign-overview.json

This file contains campaign metadata, not gameplay entities:

```json
{
  "schema_version": 2,
  "name": "ada-campaign",
  "campaign_name": "Ada Campaign",
  "genre": "Science fiction",
  "tone": "tense",
  "description": "",
  "modules": {
    "world-travel": true,
    "firearms-combat": false
  },
  "narrator_style": "serious-cinematic",
  "created_at": "2026-07-17T00:00:00Z",
  "current_date": "17 July 2504",
  "precise_time": "08:15",
  "time_of_day": "08:15",
  "player_position": {
    "previous_location": "Landing Pad",
    "current_location": "Workshop"
  },
  "current_character": "Ada",
  "session_count": 1,
  "play_mode": "interactive",
  "calendar": {},
  "currency": {}
}
```

`modules` is always a map of module ID to enabled state. Readers still accept
the old list form during migration. Updates use `JsonOperations.transaction`
so clock, position, mode, and module changes cannot overwrite each other.

## module-data

Optional modules may persist private configuration in
`module-data/<module-id>.json`. Gameplay entities still live in `world.json`.
Module-data writes are atomic and included in campaign snapshots.

## extracted

Document import specialists write intermediate JSON into `extracted/`.
These files are staging artifacts, not live game state. The importer validates
them and creates WorldGraph nodes and edges.
