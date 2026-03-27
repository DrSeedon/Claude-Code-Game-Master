## DM Reference <!-- slot:dm-reference -->

### Quick Start

| Command | What it does |
|---------|--------------|
| `/new-game` | Create a new campaign world |
| `/create-character` | Build your player character |
| `/import` | Import a PDF/document as a new campaign |
| `/dm` | Play the game (handles everything) |
| `/dm save` | Save session state |
| `/dm character` | Show character sheet |
| `/dm overview` | View campaign state |
| `/enhance` | Enrich entities with source material via RAG |
| `/help` | See all commands |

### Your DM Tools

| Tool | When to use it |
|------|----------------|
| `dm-campaign.sh` | Switch campaigns, create new ones, list available |
| `dm-extract.sh` | Import PDFs/documents |
| `dm-enhance.sh` | Enrich known entities by name, or get scene context (NOT free-text search) |
| `dm-npc.sh` | Create NPCs, update status, tag with locations/quests |
| `dm-location.sh` | Add locations, connect paths, manage coordinates & navigation |
| `dm-consequence.sh` | Track events that will trigger later |
| `dm-note.sh` | Record important facts about the world |
| `dm-search.sh` | Search world state AND/OR source material (see Search Guide below) |
| `dm-plot.sh` | Add, view, and update plot/quest progress |
| `dm-player.sh` | Update PC stats (HP, XP, gold, conditions) |
| `dm-session.sh` | Start/end sessions, move party, save/restore |
| `dm-overview.sh` | Quick summary of world state |
| `dm-time.sh` | Advance game time |

### World State Files

Each campaign in `world-state/campaigns/<name>/`:

| File | Contains |
|------|----------|
| `campaign-overview.json` | Name, location, time, precise_time, game_date, active character, modules, currency, calendar |
| `npcs.json` | NPCs with descriptions, attitudes, events, tags |
| `locations.json` | Locations with connections and descriptions |
| `facts.json` | Narrative world facts (lore, events, rumors) — NO game mechanics |
| `wiki.json` | Structured game mechanics: items, recipes, abilities, materials (with DC, ingredients, effects). Supports parent.child subentries (see below) |
| `consequences.json` | Pending and resolved events |
| `plots.json` | Plot hooks and quests |
| `session-log.md` | Session history and summaries |
| `character.json` | Player character sheet |
| `saves/*.json` | Save point snapshots |
| `module-data/inventory-system.json` | Player inventory (stackable + unique items) |
| `module-data/custom-stats.json` | Custom stats values, rules, consequences |
| `module-data/inventory-party.json` | Party NPC inventories |

### Wiki Subentries (parent.child)

Dot-separated IDs create automatic parent/child relationships. Use for books with chapters, skill trees with branches, recipe chains, or any hierarchical content.

```
liber-mortis          → parent (type: book)
liber-mortis.i        → child  (type: chapter, auto-linked)
liber-mortis.vi       → child  (type: chapter, auto-linked)
```

**Rules:**
- Dot in ID = child. Parent ID = everything before the dot
- `dm-wiki.sh show <parent>` → shows overview + CONTENTS list with status icons
- `dm-wiki.sh show <parent.child>` → shows child + PARENT link
- `dm-wiki.sh list` → hides children by default, shows parent with "(N parts)"
- `dm-wiki.sh list --children` → shows all entries including children
- Children should have `sequence` in mechanics for sort order
- Status field in mechanics maps to icons: COMPLETE ✅, COMPLETE_WITH_GAPS ⚠️, PARTIAL 🔶, NOT_READ 🔒
- Types: `book` for parents, `chapter` for children (or any valid type)

### Technical Notes

- **Python**: Always use `uv run python` (never `python3` or `python`)
- **Saves**: JSON-based snapshots in each campaign's `saves/` folder
- **Architecture**: Bash wrappers call Python modules in `lib/`
- **Multi-Campaign**: Tools read `world-state/active-campaign.txt` to determine which campaign folder to use

### Auto Memory Policy

Claude Code has a persistent memory directory (`~/.claude/projects/.../memory/`). **Do NOT use it as a shadow copy of campaign data.** All campaign knowledge has established homes:

| Data | Where it lives |
|------|---------------|
| Character stats | `character.json` |
| NPC info | `npcs.json` via `dm-npc.sh` |
| Locations | `locations.json` via `dm-location.sh` |
| Facts & lore (narrative) | `facts.json` via `dm-note.sh` |
| Items, recipes, abilities (mechanics) | `wiki.json` via `dm-wiki.sh` |
| Session history | `session-log.md` via `dm-session.sh` |
| Tool usage patterns | This file (CLAUDE.md) |

Memory is **only** for operational lessons that don't fit anywhere else — e.g., a Python version quirk, an OS-specific workaround. If a lesson applies to all users, put it in CLAUDE.md instead. When in doubt, don't write to memory — read from the existing world state files.

---
