# TODO — DM System

## Module System ✅

- [x] Module Registry, Loader, Structure, Middleware Architecture
- [x] 4 modules: custom-stats, world-travel, firearms-combat, inventory-system
- [x] `dm-module.sh list/activate/deactivate` with dependency validation
- [x] Restructured `.claude/modules/` → `.claude/additional/`
- [x] [Module development guide](docs/module-development.md)

---

## custom-stats module ✅

All done: SurvivalEngine, sleep mode, auto-tick via middleware, sleep_rate, timed effects, rate modifiers.

---

## world-travel module ✅

All done:
- [x] Coordinate system, BFS pathfinding, bearing-based location creation
- [x] GUI map (tkinter) with terrain colors and caching
- [x] Encounter engine with DC scaling, segment checks, waypoints
- [x] Vehicle system — `dm-vehicle.sh` create/board/exit/move/map/status/list
- [x] **Hierarchy/submaps** — `dm-hierarchy.sh` create-compound/add-room/enter/exit/move/tree/validate. Compounds have children (interior rooms), entry points, nested navigation. GUI supports interior view with breadcrumbs. Vehicles use hierarchy for internal rooms.

### Remaining

- [ ] Encounter auto-spawn — engine rolls category (Dangerous/Neutral/Beneficial/Special) but DM narrates manually. No encounter table → auto-generate NPC/monster with stats.

---

## firearms-combat module

### Done

- [x] Full-auto combat resolver with RPM → shots/round, PEN vs PROT, crits, XP

### Remaining

- [ ] Single fire mode — `--fire-mode single` returns "not implemented". 1 shot/round, no progressive penalty.
- [ ] Burst fire mode — `--fire-mode burst` returns "not implemented". 3 shots/round, moderate penalties.
- [ ] Auto-ammo deduction — after combat, auto-call `dm-inventory.sh` to subtract spent ammo. Currently manual.
- [ ] Enemy type presets — `--enemy-type` flag is parsed but ignored. Types (mutant, human, armored) should set AC/HP/PROT defaults.

---

## inventory-system module

### Done

- [x] Stackable + unique items with atomic transactions and rollback
- [x] Gold, HP, XP, custom-stat tracking in one command
- [x] Loot shorthand, old format migration

### Remaining

- [ ] Equipment slots — weapon/armor/accessory/helmet. Equipped items give AC/stat bonuses. Currently all items are a flat list.
- [ ] Weight system — item weight, carry capacity = STR × 15, overload penalty to speed.
- [ ] Transfer items — `dm-inventory.sh transfer "Item" "CharA" "CharB"`. Atomic remove+add.
- [ ] Separate inventory.json — move `inventory` out of `character.json` into its own file.
- [ ] Category filter — `dm-inventory.sh list --category weapon`.

---

## Quest System (CORE)

`dm-plot.sh` has list/show/search/update/complete/fail/threads/counts but no way to create quests via CLI.

- [ ] `dm-plot.sh add "Name" --type side --description "..."` — create quest. PlotManager has no `add_plot()` method.
- [ ] `dm-plot.sh objectives "Quest" "Objective" complete` — mark sub-objectives.
- [ ] `/dm quests` — player-facing active quest display.
