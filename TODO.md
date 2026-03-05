# TODO — DM System

## Module System (Community Expansion Packs)

### Done

- [x] **Module Registry** — `.claude/additional/registry.json` with metadata for all modules
- [x] **Module Loader** — `.claude/additional/module_loader.py` for module discovery and activation
- [x] **Module Structure** — each module is self-contained in `.claude/additional/modules/<name>/`
- [x] **Middleware Architecture** — `dispatch_middleware` / `dispatch_middleware_post` / `dispatch_middleware_help`
- [x] **4 modules created**: custom-stats, world-travel, firearms-combat, inventory-system
- [x] `dm-module.sh list` — show available modules
- [x] `/new-game` asks which modules to enable
- [x] `module.json` manifest with dependencies, middleware declarations, features
- [x] Module rules loaded during gameplay (`rules.md`) and campaign creation (`creation-rules.md`)
- [x] `dm-module.sh activate/deactivate` — toggle modules for active campaign
- [x] Module dependency validation on enable (checks hard deps before activation, blocks deactivation if dependents exist)
- [x] **Restructured** `.claude/modules/` → `.claude/additional/` with clean separation

### Remaining

- [x] Community docs: [module development guide](docs/module-development.md)

---

## custom-stats module

### Done

- [x] SurvivalEngine — per-tick stat simulation, conditional effects, threshold consequences
- [x] Sleep/rest mode with `--sleeping` flag
- [x] CLI: `dm-survival.sh tick/status/custom-stat/custom-stats-list`
- [x] Middleware: `dm-player.sh` (show stats), `dm-consequence.sh` (timed triggers)

- [x] Auto-tick via `dm-time.sh.post` middleware — `dm-time.sh "Night" "Day 3" --elapsed 4` ticks stats automatically
- [x] Sleep rate support — `sleep_rate` field in time_effects rules slows stat drain during sleep

### Remaining

_(none)_

---

## world-travel module

### Done

- [x] Hierarchical locations (compound/interior with entry points)
- [x] BFS pathfinding with bidirectional connections
- [x] Coordinate system with bearing-based location creation
- [x] GUI map (tkinter) with campaign terrain colors and caching
- [x] Encounter engine with DC scaling by distance/time
- [x] Middleware: `dm-session.sh` (move intercept), `dm-location.sh`
- [x] Vehicle system — `dm-vehicle.sh` with create/board/exit/move/map/status/list

### Remaining

- [ ] Submaps for building interiors, ship decks, dungeon floors
- [ ] Encounter generation creates type (Dangerous/Neutral/Beneficial) but DM must narrate — no auto-enemy spawn

---

## firearms-combat module

### Done

- [x] Full-auto combat resolver with RPM calculation, penetration vs protection, crits, XP
- [x] CLI: `dm-combat.sh resolve --weapon AK-74 --ammo 120 --targets "Enemy:13:30:4"`

### Remaining

- [ ] Single fire mode — currently returns "not implemented"
- [ ] Burst fire mode — currently returns "not implemented"
- [ ] Auto-update ammo in inventory after combat (currently manual)
- [ ] Enemy type support (`--enemy-type` flag parsed but not implemented)

---

## inventory-system module

### Done

- [x] Stackable + unique items with atomic transactions and rollback
- [x] Gold, HP, XP tracking
- [x] Loot shorthand: `dm-inventory.sh loot`
- [x] Migration from old `equipment[]` format
- [x] CLI: `dm-inventory.sh show/update/loot`

### Remaining

- [ ] Equipment slots (weapon, armor, accessory)
- [ ] Weight system with carry capacity (STR-based)
- [ ] Transfer items between characters
- [ ] Separate `inventory.json` file (currently stored in `character.json`)
- [ ] Filter by category: `dm-inventory.sh list --category weapon`

---

## Quest System

- [ ] `dm-plot.sh add` — create quests via CLI (currently manual JSON only)
- [ ] `dm-plot.sh objectives` — mark quest objectives as complete
- [ ] `/dm quests` — display active quests to player
