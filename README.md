[🇷🇺 Читать на русском](README.ru.md)

# DM Claude — Enhanced Fork

> **Fork of [Sstobo/Claude-Code-Game-Master](https://github.com/Sstobo/Claude-Code-Game-Master)** with a modular architecture — toggle optional systems (survival stats, firearms, encounters, navigation) per campaign like game mods.

**Drop any book into it. Play inside the story.** Got a favorite fantasy novel? A STALKER fanfic? A weird sci-fi book from the 70s? Drop the PDF in, and DM Claude extracts every character, location, item, and plot thread, then drops you into that world as whoever you want to be.

D&D 5e rules give the story stakes and consequences. You don't need to know D&D — just say what you want to do.

---

## What's New in This Fork

- **Module system** — optional mechanics as self-contained mods, toggled per campaign
- **Middleware architecture** — CORE tools are vanilla upstream; modules hook in without touching CORE
- **Unified inventory manager** — atomic transactions, stackable/unique items, auto-migration
- **Automated firearms combat** — RPM-based fire modes, PEN/PROT damage scaling, shot-by-shot output
- **Survival stats** — any custom stat (hunger, thirst, radiation) decaying automatically over time
- **Coordinate navigation** — real coordinates, A* pathfinding, ASCII/GUI maps
- **Random encounters** — DC-scaled checks during travel, waypoint creation
- **Timed consequences** — events that fire after elapsed game time with countdown display
- **i18n** — Cyrillic, Unicode, any language out of the box

---

## Modules

Optional systems you enable per campaign. At campaign creation `/dm` presents them as a mod selection menu — pick what fits your setting.

| Module | What it does | Good for |
|--------|-------------|----------|
| 🍖 **survival-stats** | Hunger, thirst, radiation, sleep decay per hour. Define any custom stat. Conditional effects (artifact heals only when wounded). | STALKER, Fallout, survival horror |
| ⚔️ **firearms-combat** | Automated combat resolver. RPM → shots per round, fire modes (single/burst/full_auto), PEN vs PROT scaling, subclass bonuses. Pre-built template with AKM/AK-74/M4A1/SVD. | Any modern/military campaign |
| 🎲 **encounter-system** | Random encounter checks during travel. DC scales with distance and time of day. Encounters create waypoints — fight, talk, or push through. | Open-world, wilderness travel |
| 🗺️ **coordinate-navigation** | Real XY coordinates on locations. A* pathfinding, travel time from distance + speed. ASCII map, minimap, GUI. Add locations by bearing and distance. | Any campaign with a real map |
| 📦 **inventory-system** | Atomic multi-change transactions (`--gold --hp --xp --add --remove` in one command). Stackable items with quantities. Unique items (weapons, armor). `--test` mode. | All campaigns (recommended always) |
| 📜 **quest-system** | Full quest metadata — objectives, NPCs, locations, rewards, state tracking. | Story-heavy campaigns |

Each module is self-contained: own `tools/`, `lib/`, `rules.md`, `module.json`. Drop a folder into `.claude/modules/` to install a community module.

---

## Campaign Ideas

The system is universal — not just fantasy. Here are some campaigns we've designed:

| Campaign | You play as... |
|----------|---------------|
| **S.T.A.L.K.E.R.** | A stalker in the Chernobyl Zone. Radiation, anomalies, mutants, rival factions. Hunger and thirst tick in real time. |
| **Fallout** | A vault dweller emerging into a post-nuclear wasteland. SPECIAL stats, bottlecaps, power armor. |
| **Metro 2033** | A survivor in Moscow's metro tunnels. Factions at war, mutants on the surface, bullets as currency. |
| **Civilization** | An immortal ruler guiding a civilization from stone age to space age. Strategic decisions across millennia. |
| **SCP: Infinite IKEA** | Trapped inside SCP-3008 — an infinite IKEA. Friendly by day, predatory staff by night. No exit. |
| **Star Wars: Clone Wars** | A clone trooper squad leader or Jedi on tactical missions during the Clone Wars. |
| **Warhammer 40K** | An Imperial Guard soldier in the grim far future. Everything wants to kill you. Everything will. |
| **RimWorld** | A colony manager on a frontier world. Raids, mental breaks, questionable survival ethics. |
| **Space Station 13** | A crewmember on a space station where everything goes wrong every 15 minutes. |
| **Pac-Man RPG** | A trapped soul in an endless maze, hunted by four ghosts with unique personalities. Yes, really. |
| **Ants vs Termites** | An ant commander leading colony wars across a backyard battlefield. Microscopic scale, epic stakes. |
| **Plague Inc (Reverse)** | An epidemiologist racing to stop a mutating pandemic while fighting bureaucracy and public denial. |
| **Inside a Computer** | A digital process inside a Russian server OS. Navigate file systems, fight viruses, avoid the kernel reaper. |
| **Medieval Child** | An orphaned child in war-torn medieval Europe. No combat stats — just stealth, cunning, and cold. |
| **Pirates of the Caribbean** | A pirate captain in the 1700s. Treasure, naval battles, supernatural curses. |
| **Barotrauma** | A submarine crew on an alien ocean moon. Pressure, monsters, and things going very wrong with the hull. |

All campaigns use the same engine. Custom stats, time effects, and encounters adapt to any setting.

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
| **`dm-inventory.sh`** | **Unified inventory manager — atomic transactions, stackable/unique items** |
| **`dm-combat.sh`** | **Automated firearms combat resolver with PEN/PROT mechanics** |
| `dm-npc.sh` | NPC creation, updates, party management |
| `dm-location.sh` | Locations, connections, **coordinates, navigation** |
| `dm-time.sh` | Advance time, **time effects, precise time, conditional effects** |
| `dm-consequence.sh` | Event scheduling, **timed triggers with countdown** |
| `dm-encounter.sh` | **Random encounter checks** |
| `dm-map.sh` | **ASCII maps, minimap, GUI** |
| `dm-path.sh` | **A* pathfinding between locations** |
| `dm-plot.sh` | Quest and storyline tracking, **plot creation** |
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
- **Inventory Weight & Slots** — carry capacity based on STR, overencumbrance penalties, automatic stacking, category filters. [See design in TODO.md](TODO.md)
- **Visual Map Export** — export ASCII maps to PNG/SVG for sharing outside the terminal.

Got ideas? [Open an issue](https://github.com/DrSeedon/Claude-Code-Game-Master/issues) or submit a PR.

---

## License

This work is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — free to share and adapt for non-commercial use. See [LICENSE](LICENSE) for details.

---

Original project by [Sean Stobo](https://www.linkedin.com/in/sean-stobo/). Fork enhanced by [Maxim Astrakhantsev](https://www.linkedin.com/in/maxim-astrakhantsev-13a9391b9/).

Your story awaits. Run `/dm` to begin.
