## Dungeon Exploration <!-- slot:dungeon-exploration -->

### Two Modes

| Mode | Best For | When to Use |
|------|----------|-------------|
| **Lightweight** (Default) | Fast-paced, narrative-focused | Most dungeons |
| **Structured** (Optional) | Tactical puzzles, revisitable | Complex dungeons, 3+ revisits |

### Lightweight Mode (Default)

Keep dungeon details in a single master location entry:

```json
{
  "The Laughing Crypt": {
    "position": "Beneath the ruins",
    "description": "A two-level crypt...",
    "internal_layout": "UPPER: Entry chamber → DOWN: Pit. EAST: Alcove.",
    "current_area": "Entry chamber",
    "areas_visited": ["Entry chamber"],
    "notes": "Grimaldi regenerating below."
  }
}
```

Do not render maps in terminal output. Describe lightweight spatial relationships
in prose; structured location nodes are rendered by the web map.

### Lightweight Flow
```
1. ENTER - Describe entrance, mention visible exits, no JSON needed
2. EXPLORE - Narrate each area and keep exits/spatial relationships explicit
3. COMBAT - Note which "zone" enemies are in, describe movement narratively
4. EXIT - Update master location notes if significant, log discoveries
```

### When to Update Structured Map Data
- Complex multi-path decisions
- Combat with positioning across zones
- Player asks for spatial clarity
- **NOT every room transition** - keep pacing snappy

### Structured Mode (When Needed)

Separate location per room with `dungeon` field:

```json
{
  "Goblin Caves - Guard Room": {
    "dungeon": "Goblin Caves",
    "room_number": 2,
    "exits": {
      "north": { "to": "Chieftain's Chamber", "type": "door", "locked": true },
      "south": { "to": "Entry Hall", "type": "open" },
      "east": { "to": "Hidden Treasury", "type": "secret", "dc": 16, "found": false }
    },
    "state": { "discovered": true, "visited": true, "cleared": false }
  }
}
```

### Structured Flow
```
1. VALIDATE EXIT - Does it exist? Blocked/locked? Secret unfound?
2. HANDLE OBSTACLES - Locked: pick/force/key. Secret: find first (Perception)
3. PERSIST THE TRANSITION - Create/connect/move in one call:
   bash tools/dm-scene.sh "[Dungeon Room Name]" --description "[description]" --path "[terrain and distance]" --elapsed 0.05
4. APPLY OTHER SCENE STATE - Add repeated `--with`, `--resolve`, or `--objective` flags to that same call when needed
5. SHOW ROOM - Describe (2-4 sentences), list exits with types, note creatures
```

**IMPORTANT:** For dungeon rooms, use `dm-scene.sh` so creation, connection, party movement, time, consequences, and quest progress remain one coherent transition.

**Use Structured when:** Revisited 3+ times, complex puzzle states, player wants tactical grid play

### ASCII Map Symbols
```
@ = Current position    + = Door        # = Locked door
△ = Stairs up          ▽ = Stairs down  ~ = Secret (found)
▓ = Fog of war (undiscovered)
```

### Dungeon Room Display Format
```
================================================================
  DUNGEON: Goblin Caves                    ROOM 2: Guard Room
  ────────────────────────────────────────────────────────────
  HP: ████████░░░░ 18/24   │  XP: 340  │  GP: 27
================================================================

  Torchlight reveals a cramped chamber. An overturned table
  and scattered bones suggest a hasty departure.

  EXITS: North (door, locked) · South (passage) · East (wall?)

  [A]ttack goblins  [S]earch room  [B]ack south

================================================================
```

---
