# World State JSON Schema Reference

This document defines the canonical JSON schemas for all world state files. Managers enforce these schemas when reading and writing data.

---

## Campaign Structure

Each campaign lives in its own folder: `world-state/campaigns/<name>/`

```
<campaign-name>/
├── campaign-overview.json   # Campaign settings and current state
├── npcs.json                # All NPCs
├── locations.json           # All locations
├── facts.json               # World facts by category
├── consequences.json        # Pending/resolved events
├── items.json               # Items (from imports)
├── plots.json               # Plot hooks and quests
├── session-log.md           # Session history
├── character.json           # Player character sheet
└── saves/                   # Snapshot saves
```

---

## campaign-overview.json

```json
{
  "campaign_name": "string",
  "genre": "Fantasy",
  "tone": {
    "horror": 30,
    "comedy": 30,
    "drama": 40
  },
  "current_date": "string (in-game date)",
  "time_of_day": "dawn|morning|midday|afternoon|dusk|evening|night|midnight",
  "player_position": {
    "current_location": "string or null",
    "previous_location": "string or null",
    "arrival_time": "ISO timestamp"
  },
  "current_character": "string (character name)",
  "session_count": 0
}
```

---

## npcs.json

A dictionary keyed by NPC name.

```json
{
  "NPC_NAME": {
    "description": "string (physical/personality description)",
    "attitude": "friendly|neutral|hostile|suspicious|helpful|indifferent|fearful|respectful|dismissive|curious",
    "created": "ISO timestamp",
    "events": [
      {"event": "string describing what happened", "timestamp": "ISO timestamp"}
    ],
    "tags": {
      "locations": ["location name"],
      "quests": ["quest name"]
    },
    "context": ["optional source passages"],
    "enhanced": false,
    "enhanced_at": "ISO timestamp",
    "is_party_member": false,
    "character_sheet": null
  }
}
```

### Party Member Character Sheet

When `is_party_member: true`, the `character_sheet` contains:

```json
{
  "character_sheet": {
    "race": "Human",
    "class": "Fighter",
    "level": 2,
    "hp": {
      "current": 18,
      "max": 22
    },
    "ac": 14,
    "stats": {"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 11, "cha": 10},
    "saves": {"str": 4, "dex": 1, "con": 3, "int": 0, "wis": 0, "cha": 0},
    "skills": {},
    "attack_bonus": 4,
    "damage": "1d8+2",
    "equipment": ["Longsword", "Shield", "Chain Shirt"],
    "features": ["Second Wind", "Fighting Style (Defense)"],
    "conditions": [],
    "xp": 0
  }
}
```

**HP Tracking:** Party members use `hp.current` and `hp.max`. Update with:
```bash
bash tools/dm-npc.sh hp "Name" -5   # Damage
bash tools/dm-npc.sh hp "Name" +3   # Heal
```

### Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| description | Yes | Character description |
| attitude | Yes | One of the supported attitude values |
| created | Yes | ISO timestamp when created |
| tags | No | Object with `locations` and `quests` arrays |
| events | No | Array of event objects |
| context | No | Source passages for RAG enhancements |
| enhanced | No | Flag when RAG enhancements applied |
| enhanced_at | No | ISO timestamp when enhanced |
| is_party_member | No | True if NPC is a party member |
| character_sheet | No | Full character sheet if party member (see above)

---

## locations.json

A dictionary keyed by location name.

```json
{
  "LOCATION_NAME": {
    "position": "string (relative position, e.g. 'north of town')",
    "description": "string (what the place looks like)",
    "connections": [
      {"to": "Other Location", "path": "rocky trail"}
    ],
    "discovered": "ISO timestamp",
    "notes": "optional string",
    "source": "optional string"
  }
}
```

### Dungeon Rooms (Extended Schema)

Dungeon rooms (stored in `locations.json`) may include:

```json
{
  "ROOM_NAME": {
    "dungeon": "string (dungeon name)",
    "room_number": 1,
    "description": "string",
    "exits": {
      "north": {"to": "Room 2", "type": "open|door|secret|stairs-up|stairs-down"}
    },
    "state": {"discovered": false, "visited": false, "cleared": false}
  }
}
```

---

## facts.json

A dictionary with category keys, each containing an array of fact strings.

```json
{
  "world_building": [
    "The kingdom has been at peace for 100 years",
    "Dragons are extinct except for one"
  ],
  "session_events": [
    "The party met the king on day 1"
  ],
  "plot_hooks": [
    "A mysterious stranger mentioned a treasure"
  ]
}
```

### Common Categories

- `world_building` - Established world facts
- `session_events` - What happened this session
- `player_choices` - Key decisions made
- `npc_relations` - How NPCs feel about the party
- `world_lore` - World facts, history, lore details

> **Note:** Plot/quest data belongs in `plots.json` via `dm-plot.sh`, not in notes.

---

## consequences.json

Tracks events that will trigger in the future.

```json
{
  "active": [
    {
      "id": "8-char-uuid",
      "consequence": "string (what will happen)",
      "trigger": "string (when it triggers)",
      "created": "ISO timestamp"
    }
  ],
  "resolved": [
    {
      "id": "8-char-uuid",
      "consequence": "string",
      "trigger": "string",
      "created": "ISO timestamp",
      "resolved": "ISO timestamp"
    }
  ]
}
```

---

## plots.json

A dictionary keyed by plot name.

```json
{
  "PLOT_NAME": {
    "type": "main|side|mystery|threat",
    "status": "active|completed|failed|dormant",
    "description": "string (what the quest is about)",
    "npcs": ["involved", "npc", "names"],
    "locations": ["relevant", "locations"],
    "objectives": ["optional objective strings"],
    "rewards": "optional string",
    "consequences": "optional string",
    "events": [
      {"event": "progress update", "timestamp": "ISO timestamp"}
    ],
    "completed_at": "ISO timestamp or null",
    "failed_at": "ISO timestamp or null"
  }
}
```

---

## items.json

A dictionary keyed by item name. Typically populated by `/import`.

```json
{
  "ITEM_NAME": {
    "name": "string",
    "description": "string",
    "type": "weapon|armor|potion|scroll|wondrous|treasure|equipment|prop|artifact",
    "rarity": "common|uncommon|rare|very rare|legendary|artifact",
    "mechanics": "optional string",
    "value": "optional string",
    "location": "optional string",
    "attunement": false,
    "cursed": false,
    "source": "optional string"
  }
}
```

---

## character.json

The player character sheet.

```json
{
  "name": "string",
  "race": "string",
  "class": "string",
  "level": 1,
  "background": "string",

  "stats": {
    "str": 10,
    "dex": 10,
    "con": 10,
    "int": 10,
    "wis": 10,
    "cha": 10
  },

  "hp": {"current": 10, "max": 10},

  "ac": 10,
  "skills": {},
  "saves": {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},

  "equipment": ["item", "names"],
  "features": ["class", "features"],
  "background": "string",
  "alignment": "string",
  "bonds": "string",
  "flaws": "string",
  "ideals": "string",
  "traits": "string",
  "notes": [],
  "gold": 0,
  "xp": {"current": 0, "next_level": 300}
}
```

---

## Save Files (saves/*.json)

Snapshots of world state at a point in time.

```json
{
  "name": "string (save name)",
  "created": "ISO timestamp",
  "session_number": 5,
  "snapshot": {
    "campaign_overview": {},
    "npcs": {},
    "locations": {},
    "facts": {},
    "consequences": {},
    "characters": {}
  }
}
```

---

## Validation Notes

- All timestamps use ISO 8601 format with timezone
- Entity names serve as dictionary keys (case-sensitive)
- Empty arrays `[]` are preferred over `null` for list fields
- Boolean fields default to `false` if omitted
- The `created` field is auto-set by managers when entities are created
