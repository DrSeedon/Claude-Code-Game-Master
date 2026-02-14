[🇷🇺 Читать на русском](README.ru.md)

# DM Claude — Enhanced Fork

> **Fork of [Sstobo/Claude-Code-Game-Master](https://github.com/Sstobo/Claude-Code-Game-Master)** with custom character stats, time effects, random encounters, coordinate navigation, and ASCII/GUI maps.

**Drop any book into it. Play inside the story.** Got a favorite fantasy novel? A STALKER fanfic? A weird sci-fi book from the 70s? Drop the PDF in, and DM Claude extracts every character, location, item, and plot thread, then drops you into that world as whoever you want to be.

D&D 5e rules give the story stakes and consequences. You don't need to know D&D — just say what you want to do.

---

## What's New in This Fork

### Custom Character Stats
Define **any** stats for your campaign — hunger, thirst, radiation, morale, sanity, reputation — whatever fits your world. Fully universal, zero hardcoded stat names.

```bash
bash tools/dm-player.sh custom-stat hunger +15
bash tools/dm-player.sh custom-stat radiation -5
```

### Time Effects Engine
Stats change automatically as game time passes. Define rates per hour in your campaign config, and the system handles the rest.

```
Time updated to: Evening (18:30), Day 3
Custom Stats:
  hunger: 80 → 68 (-12)
  thirst: 70 → 52 (-18)
```

### Auto Movement Time
Move between locations and travel time is calculated automatically from distance and character speed. Custom stats tick during travel.

```bash
bash tools/dm-session.sh move "Ruins"
# Auto-calculates: 2000m at 4 km/h = 30 minutes
# Auto-applies time effects to hunger, thirst, etc.
```

### Timed Consequences
Schedule events that trigger after elapsed game time, not just on story beats.

```bash
bash tools/dm-consequence.sh add "Trader arrives at camp" "in 24 hours" --hours 24
```

### Random Encounter System
Configurable random encounters during travel — frequency scales with distance, time of day, and character stats. Encounters create waypoints on the map where you can fight, talk, or explore before continuing.

```bash
bash tools/dm-encounter.sh check "Village" "Ruins" 2000 open
```

### Coordinate Navigation & Maps
Locations have real coordinates. A* pathfinding finds routes. View your world as ASCII maps or a GUI window.

```bash
bash tools/dm-map.sh              # Full ASCII map
bash tools/dm-map.sh --minimap    # Tactical minimap

# Add locations by bearing and distance
bash tools/dm-location.sh add "Outpost" "Abandoned outpost" \
  --from "Village" --bearing 90 --distance 2500 --terrain forest
```

### i18n Support
Cyrillic names, non-English attitudes, and Unicode identifiers work out of the box. Build campaigns in any language.

---

## In Action — Dungeon Crawler Carl

A campaign imported from *Dungeon Crawler Carl*. Tandy the sasquatch rips the skin off a Terror Clown, forces Carl to wear it as a disguise, then performs a sasquatch mating dance to distract Grimaldi while Donut frees the dragon.

![Tandy acquires Terror Clown skin disguise for Carl](public/622422010_1572097020675669_3114747955156903860_n.png)

![Tandy performs a sasquatch mating dance to distract Grimaldi](public/625560066_33916991331281718_1129121114640091251_n.png)

![Exploring The Laughing Crypt — thirty clown bodies wake up](public/623940676_2000130920531570_2521032782764513297_n.png)

---

## Getting Started

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

```bash
git clone https://github.com/DrSeedon/Claude-Code-Game-Master.git
cd Claude-Code-Game-Master
./install.sh
```

Once installed:

1. Drop a PDF in the `source-material/` folder
2. Run `claude` to launch Claude Code
3. Run `/dm` and let the agent guide you

---

## How It Works

When you import a document, the system vectorizes it with ChromaDB and spawns extraction agents that pull the book apart into structured data. During gameplay, every scene gets grounded in real passages from your source material.

Everything persists. NPCs remember what you said last session. Consequences fire days later in-game time. Locations change as events unfold. Save and restore at any point.

Specialist agents spin up on the fly — monster stats, spell mechanics, loot tables, equipment databases. The player sees only the story. It uses the [D&D 5e API](https://www.dnd5eapi.co/) for official rules, spellbooks, monsters, and equipment.

---

## Commands

| Command | What it does |
|---------|--------------|
| `/dm` | Start or continue your story |
| `/dm save` | Save your progress |
| `/dm character` | View your character sheet |
| `/dm overview` | See the world state |
| `/new-game` | Create a world from scratch |
| `/create-character` | Build your character |
| `/import` | Import a PDF/document as a campaign |
| `/enhance` | Enrich entities with source material |
| `/help` | Full command reference |

## Tools

| Tool | Purpose |
|------|---------|
| `dm-campaign.sh` | Create, list, switch campaigns |
| `dm-session.sh` | Session lifecycle, movement, save/restore |
| `dm-player.sh` | HP, XP, gold, inventory, **custom stats** |
| `dm-npc.sh` | NPC creation, updates, party management |
| `dm-location.sh` | Locations, connections, **coordinates, navigation** |
| `dm-time.sh` | Advance time, **time effects, precise time** |
| `dm-consequence.sh` | Event scheduling, **timed triggers** |
| `dm-encounter.sh` | **Random encounter checks** |
| `dm-map.sh` | **ASCII maps, minimap, GUI** |
| `dm-path.sh` | **A* pathfinding between locations** |
| `dm-plot.sh` | Quest and storyline tracking |
| `dm-search.sh` | Search world state and source material |
| `dm-enhance.sh` | RAG-powered entity enrichment |
| `dm-extract.sh` | Document import pipeline |
| `dm-note.sh` | Record world facts |
| `dm-overview.sh` | World state summary |

**Bold** = new in this fork.

## Specialist Agents

| Agent | Triggered by |
|-------|--------------|
| `monster-manual` | Combat encounters |
| `spell-caster` | Casting spells |
| `rules-master` | Mechanical edge cases |
| `gear-master` | Shopping, identifying gear |
| `loot-dropper` | Victory, treasure discovery |
| `npc-builder` | Meeting new NPCs |
| `world-builder` | Exploring new areas |
| `dungeon-architect` | Entering dungeons |
| `create-character` | New characters |

---

## Roadmap

Features planned for future releases:

- **Nested Sub-Maps** — locations can contain their own internal maps. Enter a castle and explore its floors. Board a spaceship and navigate its decks. Dive into a cave system with branching tunnels. Each sub-map connects back to the parent world map seamlessly.
- **Multi-Floor Dungeons** — vertical dungeon navigation with stairs, elevators, ladders between floors. Each floor is its own sub-map with independent room states.
- **Vehicle Interiors** — ships, airships, space stations as explorable sub-maps that move on the world map. The vehicle travels between locations while you explore inside it.
- **Campaign Templates** — pre-built campaign configs for popular genres (post-apocalyptic, space exploration, medieval, urban horror) with ready-to-use custom stats, time effects, and encounter tables.
- **Visual Map Export** — export ASCII maps to PNG/SVG for sharing outside the terminal.

Got ideas? [Open an issue](https://github.com/DrSeedon/Claude-Code-Game-Master/issues) or submit a PR.

---

## License

This work is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — free to share and adapt for non-commercial use. See [LICENSE](LICENSE) for details.

---

Original project by [Sean Stobo](https://www.linkedin.com/in/sean-stobo/). Fork enhanced by [Maxim Astrakhantsev](https://www.linkedin.com/in/maxim-astrakhantsev-13a9391b9/).

Your story awaits. Run `/dm` to begin.
