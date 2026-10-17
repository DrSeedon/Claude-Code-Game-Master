# Engine: CORE tools, calendar, currency, modules, WorldGraph, slots, post-compaction

Moved verbatim from the root AGENTS.md on 2026-10-17 (task V-47, owner's rules-structure decision). Edit here when a rule changes.

## CORE tools (always available)
| Tool | Lib | Purpose |
|------|-----|---------|
| `dm-roll.sh` | `dice.py` | Dice with `--label`, `--dc`, `--ac`. Auto-lookup: `--skill "name"`, `--save "name"`, `--attack "weapon"`, `--initiative "name" ...`, `--advantage`, `--disadvantage`. Reads entities from world.json. Auto-combat: `--target "creature"` (player attacks, AC from world.json), `--defend --from "creature"` (creature attacks, stats from world.json). Auto-damage on hit. |
| `dm-inventory.sh` | `inventory_manager.py` | Items, weight, gold, HP/XP, transfers, `remove` (sold/destroyed/consumed), `use` (auto-consume via wiki), `craft` (auto-craft via wiki recipe). Always use `--qty N`, never call multiple times. |
| `dm-status.sh` | `inventory_manager.py status` | Compact inventory for session start |
| `dm-player.sh` | `player_manager.py` | XP, HP, HP max, gold, conditions |
| `dm-session.sh` | `session_manager.py` | Start/end, move (`--elapsed N`), save/restore |
| `dm-npc.sh` | `npc_manager.py` | NPCs, party, attitudes |
| `dm-location.sh` | `location_manager.py` | Locations, connections |
| `dm-note.sh` | `note_manager.py` | World facts |
| `dm-plot.sh` | `plot_manager.py` | Quests, objectives |
| `dm-consequence.sh` | `consequence_manager.py` | Timed events |
| `dm-time.sh` | `time_manager.py` | Game clock. Usage: `dm-time.sh "<time>" "<date>" --elapsed N [--sleeping]`. Positional args required. |
| `dm-campaign.sh` | `campaign_manager.py` | Campaign management |
| `dm-mode.sh` | `campaign_mode.py` | Persistent narrative/interactive player-agency mode |
| `dm-wiki.sh` | `wiki_manager.py` | Structured knowledge base: items, recipes, abilities, materials |
| `dm-condition.sh` | `player_manager.py` | Condition management (add/remove/check) — wrapper for dm-player.sh condition |
| `dm-search.sh` | `entity_enhancer.py` | Hybrid world-state + RAG search for scenes and entities |
| `dm-overview.sh` | — | World state overview (NPCs, locations, facts, consequences) |
| `dm-enhance.sh` | `entity_enhancer.py` | RAG entity enhancement — auto-runs on dm-session.sh move |

## Calendar system
- `lib/calendar.py` — universal, configurable per campaign
- Config in `campaign-overview.json` → `"calendar"` section (months, weekdays, epoch)
- Used by `time_manager.py` for date display and weekday calculation

## Currency system
- `lib/currency.py` — universal, configurable per campaign
- Config in `campaign-overview.json` → `"currency"` section
- Stored as single int in base units (copper for D&D)
- `format_money(2537)` → `"25g 3s 7c"`, `parse_money("2gp 5sp")` → `250`

## Module pattern (for optional modules)
Each module in `modules/<name>/`:
- `middleware/<tool>.sh` — intercepts CORE tool calls (pre-hook: exit 0 = handled)
- `middleware/<tool>.sh.post` — runs after CORE (post-hook: always runs)
- `lib/` — module Python code
- `tools/` — module-specific CLI
- `module.json` — metadata, replaces dm-slots

Modules declare neutral `provides`, `providers`, and `action_routes` contracts in
`module.json`. A module MUST NOT import, inspect, or name another gameplay
module. CORE composes active capabilities and resolved DM rules.

**Modules MUST be campaign-agnostic (MANDATORY).** This is a public repo used by multiple campaigns. NEVER add campaign-specific content (character names, spell names, setting-specific rules, faction names) to module code, module rules, or dm-slots. Campaign-specific rules belong in `campaign-rules.md` for that campaign only.
## Data Architecture — WorldGraph
- **`world.json`** — unified entity graph. ALL game data: player, NPCs, locations, items, creatures, facts, quests, consequences, spells, economy. One file per campaign.
- **`campaign-overview.json`** — metadata only: time, date, calendar, modules, narrator style, genre, tone.
- **`campaign-rules.md`** — per-campaign rules.
- Custom stats, inventory, wiki — all stored as nodes in `world.json`.
- `dm-time.sh --elapsed` auto-ticks via WorldGraph: custom stats decay, recurring expenses/income, production, consequences, random events.
- Move + time: `dm-session.sh move "Location" --elapsed 0.5` combines move and time advance in one call.

## Slot System
All dm-slots files are replaceable by modules. Each slot has a `<!-- slot:name -->` marker. Modules declare `"replaces": ["slot-name"]` in module.json to override a slot. The loader (`dm-active-modules-rules.sh`) skips replaced slots and loads module rules instead.

## Post-compaction recovery
After context compaction, reload `/tmp/dm-rules.md` before continuing gameplay. In Claude Code,
the `UserPromptSubmit` hook compiles it for each prompt; in Codex, the DM skill compiles it during
session preparation. If it is missing, recompile:
```bash
bash .claude/additional/infrastructure/dm-active-modules-rules.sh > /tmp/dm-rules.md 2>/dev/null
```
Then read `/tmp/dm-rules.md`.

