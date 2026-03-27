# DM System - Developer Rules

## Stack
- Python via `uv run python` (never `python3`)
- Bash wrappers in `tools/` → Python modules in `lib/`
- Tests: `uv run pytest`

## Architecture
- `lib/` — CORE Python: dice, player, session, inventory, currency, NPCs, locations, plots, consequences, notes
- `tools/` — thin bash wrappers + `dispatch_middleware` for module hooks
- `.claude/additional/modules/` — optional gameplay modules (custom-stats, world-travel, mass-combat, firearms-combat)
- `.claude/additional/dm-slots/` — DM rules (loaded into `/tmp/dm-rules.md`)
- `.claude/additional/infrastructure/` — loaders (dm-active-modules-rules.sh, dm-campaign-rules.sh, dm-narrator.sh)
- `.claude/additional/campaign-rules-templates/` — campaign rule templates
- `.claude/additional/narrator-styles/` — narrator style definitions

## CORE tools (always available)
| Tool | Lib | Purpose |
|------|-----|---------|
| `dm-roll.sh` | `dice.py` | Dice with `--label`, `--dc`, `--ac`. Auto-lookup: `--skill "name"`, `--save "name"`, `--attack "weapon"`, `--advantage`, `--disadvantage`. Reads character.json automatically. |
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
Each module in `.claude/additional/modules/<name>/`:
- `middleware/<tool>.sh` — intercepts CORE tool calls (pre-hook: exit 0 = handled)
- `middleware/<tool>.sh.post` — runs after CORE (post-hook: always runs)
- `lib/` — module Python code
- `tools/` — module-specific CLI
- `module.json` — metadata, replaces dm-slots

**Modules MUST be campaign-agnostic (MANDATORY).** This is a public repo used by multiple campaigns. NEVER add campaign-specific content (character names, spell names, setting-specific rules, faction names) to module code, module rules, or dm-slots. Campaign-specific rules belong in `campaign-rules.md` or `facts.json` for that campaign only.

## Dev commands
```bash
uv run pytest                                              # run all tests
bash .claude/additional/infrastructure/tools/dm-module.sh list # list active modules
```

## Rules
- **LANGUAGE POLICY (MANDATORY, NO EXCEPTIONS):** ALL rules files (dm-slots, module rules, CLAUDE.md, module.json) MUST be written entirely in English — every sentence, every example, every table cell. Campaign DATA (NPC names, location names, fact content, session logs) can be in any language. If you catch yourself writing Russian (or any non-English) text in a rules file — STOP and rewrite it in English.
- CORE tools delegate to modules via `dispatch_middleware "tool.sh" "$ACTION" "$@" && exit $?`
- Inventory data lives in `module-data/inventory-system.json` (not character.json)
- Custom stats live in `module-data/custom-stats.json` (not character.json)
- `campaign-overview.json` is for CORE data only (character, location, time, precise_time, game_date, modules list, currency, calendar, narrator_style, tone, genre)
- `wiki.json` stores structured game mechanics: items, recipes (with DC + ingredients), abilities, materials, techniques. Each entity has type, mechanics, recipe, refs, tags. Supports parent.child subentries via dot-separated IDs (e.g. `book-name.chapter-i`). Use `dm-wiki.sh` to manage.
- `facts.json` stores narrative/lore only: events, rumors, NPC backstory, world history. NO game mechanics (DC, damage, ingredients) in facts — those go in wiki.json.
- Game clock: `dm-time.sh` owns `precise_time` (HH:MM) and `game_date` in campaign-overview.json. Module custom-stats only ticks stats via post-hook.
- `dm-time.sh --elapsed` also auto-ticks: recurring expenses (food, rent), recurring income (with dice + DC checks), recurring production (skeleton workers: mine ore, forge goods, chop wood, gather herbs into workshop inventory), and random events (d100 type + d6 scope). See custom-stats module rules.
- Move + time: `dm-session.sh move "Location" --elapsed 0.5` combines move and time advance in one call

## DM Gameplay Rules
All gameplay rules (combat, movement, narration, loot, social, time management, state persistence) live in `.claude/additional/dm-slots/`. These are loaded at session start into `/tmp/dm-rules.md`. Edit THOSE files for gameplay changes, not this file. This file is dev-only.

## Verification
- After lib/ or tools/ changes: `uv run pytest`
- After dm-slots or module rules edits: verify English-only (no Russian text in rules files)
- After JSON schema changes: run affected tool with `--help` to verify it still parses
- After module middleware changes: test the intercepted action end-to-end

## Slot System
All dm-slots files are replaceable by modules. Each slot has a `<!-- slot:name -->` marker. Modules declare `"replaces": ["slot-name"]` in module.json to override a slot. The loader (`dm-active-modules-rules.sh`) skips replaced slots and loads module rules instead.

## Post-compaction recovery
After context compaction, ALWAYS reload DM rules before continuing gameplay:
```bash
# DM rules are pre-compiled by the UserPromptSubmit hook
Read /tmp/dm-rules.md
```
If `/tmp/dm-rules.md` is missing (hook didn't run), recompile:
```bash
bash .claude/additional/infrastructure/dm-active-modules-rules.sh > /tmp/dm-rules.md 2>/dev/null
```
Then read the file.
