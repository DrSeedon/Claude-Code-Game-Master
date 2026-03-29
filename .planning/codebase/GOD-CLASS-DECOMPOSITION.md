# God Class Decomposition Analysis

> Deep analysis of god classes in the DM System codebase with concrete decomposition proposals.

---

## 1. WorldGraph (lib/world_graph.py)

**LOC:** 2,481 | **Methods:** 87 (71 class methods + 5 nested closures + 1 standalone function + `main()`) | **Inherits:** None

WorldGraph is the unified graph-based world state manager that replaced 6 separate EntityManager subclasses in the graph migration (commit `972e01e`). It owns ALL game entity operations through a single `world.json` file with typed nodes and edges.

### 1.1 Complete Method Catalog by Responsibility Group

#### Group A: Core Infrastructure (7 methods, ~57 LOC, lines 71–101)

| Line | Method | Purpose |
|------|--------|---------|
| 71 | `__init__` | Initialize with campaign directory |
| 75 | `_load` | Load world.json into memory |
| 81 | `_save` | Persist world.json to disk |
| 88 | `_empty_world` | Create fresh world structure |
| 95 | `_validate_node_id` | Validate `type:kebab-name` format |
| 349 | `_slug` | Convert name to kebab-case (Cyrillic support) |
| 366 | `_now` | Get ISO timestamp |

**Coupling:** Used by every other group. The `_load`/`_save` pattern (load-modify-save) is called from ~50 methods, creating an implicit transaction model without actual transactions.

#### Group B: Node CRUD (6 methods, ~84 LOC, lines 103–177)

| Line | Method | Purpose |
|------|--------|---------|
| 103 | `add_node` | Create entity node |
| 116 | `get_node` | Retrieve node by ID |
| 120 | `update_node` | Modify node attributes |
| 131 | `remove_node` | Delete node + cascade edges |
| 144 | `list_nodes` | Query nodes by type |
| 153 | `search_nodes` | Fuzzy search by name |

**Coupling:** Pure graph operations. Used by all domain groups (C–H) as primitives.

#### Group C: Edge CRUD (4 methods, ~57 LOC, lines 179–235)

| Line | Method | Purpose |
|------|--------|---------|
| 179 | `add_edge` | Create typed relationship |
| 197 | `get_edges` | Query edges by node/type/direction |
| 209 | `remove_edge` | Delete specific edge |
| 221 | `get_neighbors` | Get connected nodes via edge type |

**Coupling:** Pure graph operations. Used by domain groups for relationships (NPC→location, quest→NPC, inventory ownership).

#### Group D: Display & Formatting (3 methods, ~112 LOC, lines 237–348)

| Line | Method | Purpose |
|------|--------|---------|
| 237 | `format_node` | Pretty-print node with edges (61 LOC) |
| 298 | `format_node_list` | Tabular node listing |
| 315 | `stats` | World statistics summary (34 LOC) |

**Coupling:** Reads from B (get_node, list_nodes) and C (get_edges). Contains ANSI color formatting via embedded `Colors` class.

#### Group E: ID Resolution (3 methods, ~25 LOC, lines 369–401)

| Line | Method | Purpose |
|------|--------|---------|
| 369 | `_resolve_id` | Name-or-ID → canonical node ID |
| 377 | `_player_id` | Get active player node ID |
| 384 | `_fact_next_id` | Auto-increment fact IDs |

**Coupling:** Used by all domain groups. `_player_id` couples to `campaign-overview.json`.

#### Group F: NPC Domain (4 methods, ~55 LOC, lines 402–457)

| Line | Method | Purpose |
|------|--------|---------|
| 402 | `npc_create` | Create NPC node with attitude |
| 416 | `npc_event` | Append event to NPC history |
| 427 | `npc_promote` | Add party membership edge |
| 439 | `npc_locate` | Move NPC to location (replace `at` edge) |

**Coupling:** Uses B (add_node, update_node), C (add_edge, remove_edge), E (_resolve_id).

#### Group G: Location Domain (2 methods, ~22 LOC, lines 458–491)

| Line | Method | Purpose |
|------|--------|---------|
| 458 | `location_create` | Create location node |
| 469 | `location_connect` | Bidirectional connection with path type |

**Coupling:** Uses B (add_node), C (add_edge, get_edges). `_has_edge` nested helper at line 475.

#### Group H: Facts Domain (1 method, ~12 LOC, lines 492–504)

| Line | Method | Purpose |
|------|--------|---------|
| 492 | `fact_add` | Add categorized fact with auto-ID |

**Coupling:** Uses B (add_node), E (_fact_next_id).

#### Group I: Quest Domain (5 methods, ~50 LOC, lines 505–555)

| Line | Method | Purpose |
|------|--------|---------|
| 505 | `quest_create` | Create quest with objectives |
| 522 | `quest_objective_add` | Add objective to quest |
| 532 | `quest_objective_complete` | Mark objective done |
| 544 | `quest_complete` | Complete entire quest |
| 548 | `quest_fail` | Fail quest |

**Coupling:** Uses B (add_node, update_node), A (_load/_save).

#### Group J: Consequence Domain (4 methods, ~59 LOC, lines 556–614)

| Line | Method | Purpose |
|------|--------|---------|
| 556 | `consequence_add` | Create timed consequence |
| 576 | `consequence_tick` | Advance timers, return triggered |
| 595 | `consequence_list_resolved` | Query resolved consequences |
| 605 | `consequence_resolve` | Mark resolved |

**Coupling:** Uses B (add_node, list_nodes, update_node). `consequence_tick` also used by tick engine (Group N).

#### Group K: Inventory Operations (9 methods, ~121 LOC, lines 615–714)

| Line | Method | Purpose |
|------|--------|---------|
| 615 | `_ensure_inventory` | Init inventory on node |
| 622 | `inventory_add` | Add stackable item |
| 633 | `inventory_add_unique` | Add non-stackable item |
| 640 | `inventory_remove` | Remove stackable quantity |
| 658 | `inventory_remove_unique` | Remove specific unique item |
| 671 | `inventory_show` | Format inventory display (27 LOC) |
| 698 | `inventory_transfer` | Move items between owners |
| 857 | `inventory_craft` | Craft from recipe (47 LOC) |
| 904 | `inventory_use` | Use consumable (31 LOC) |

**Coupling:** Direct `_load`/`_save` manipulation. `craft` and `use` depend on wiki nodes (Group L). `inventory_loot` (line 936, 29 LOC) bridges inventory + player stats.

#### Group L: Player Operations (7 methods, ~88 LOC, lines 717–856)

| Line | Method | Purpose |
|------|--------|---------|
| 717 | `player_update_stat` | Modify HP/XP/gold/AC |
| 732 | `player_hp_max` | Adjust max HP |
| 744 | `player_condition` | Add/remove/list conditions (43 LOC) |
| 787 | `player_set` | Set active player character |
| 802 | `player_show` | Display character sheet (29 LOC) |
| 832 | `wiki_add` | Add wiki entity (creature/item/spell) |
| 936 | `inventory_loot` | Add loot (items + gold + XP) |
| 966 | `_player_data` | Get player node data (helper) |

**Coupling:** Uses E (_player_id), A (_load/_save). `wiki_add` is misplaced here — it's a reference data operation.

#### Group M: Custom Stats & Timed Effects (6 methods, ~95 LOC, lines 972–1146)

| Line | Method | Purpose |
|------|--------|---------|
| 972 | `custom_stat_get` | Query custom stat |
| 981 | `custom_stat_set` | Modify stat (delta or absolute) |
| 1019 | `custom_stat_list` | List all custom stats |
| 1052 | `custom_stat_define` | Define stat with decay rate |
| 1079 | `timed_effect_add` | Add temporary effect |
| 1116 | `timed_effect_list` | List active effects |

**Coupling:** Uses E (_player_id), A (_load/_save). Tightly coupled to tick engine (Group N).

#### Group N: Tick Engine (13 methods + 5 nested closures, ~580 LOC, lines 1147–1697)

| Line | Method | Purpose |
|------|--------|---------|
| 1147 | `_tick_custom_stats` | Apply stat decay |
| 1186 | `_tick_timed_effects` | Expire/apply effects |
| 1205 | `_check_stat_thresholds` | Generate threshold warnings |
| 1234 | `_tick_production` | Location production (dice rolls, 81 LOC) |
| 1315 | `_tick_expenses` | Deduct recurring expenses |
| 1358 | `_tick_income` | Roll income (70 LOC) |
| 1428 | `_tick_random_events` | Generate random events |
| 1452 | `_tick_consequences_elapsed` | Advance consequence timers |
| 1467 | `_find_economy_node` | Locate economy config |
| 1473 | `_tick_expenses_from_world` | Economy-based expenses |
| 1516 | `_tick_income_from_world` | Economy-based income (70 LOC) |
| 1586 | `_tick_random_events_from_world` | Economy-based random events |
| 1607 | `tick` | **Master orchestrator** (91 LOC) |

**Nested closures** (duplicated across methods):
- `_roll(expr)` — dice expression evaluator (duplicated 3x at lines 1235, 1372, 1529)
- `_fm(amount)` — money formatter (duplicated 3x at lines 1334, 1388, 1545)

**Coupling:** Reads/writes custom stats (M), consequences (J), player data (L), inventory (K). Most complex group — 580 LOC with heavy internal coupling and duplicated helper closures.

#### Group O: Wiki Display (1 method, ~28 LOC, lines 1698–1726)

| Line | Method | Purpose |
|------|--------|---------|
| 1698 | `wiki_recipe` | Display recipe for craftable item |

**Coupling:** Uses B (get_node), C (get_edges).

#### Group P: CLI Entry Point (main function, ~262 LOC, lines 1727–2000+)

| Line | Method | Purpose |
|------|--------|---------|
| 1727 | `main()` | argparse CLI with 30+ subcommands |
| 1989 | `resolve()` | CLI helper for name→ID resolution |

**Coupling:** Calls every domain method. Pure dispatch logic.

### 1.2 Responsibility Group Summary

| Group | Responsibility | Methods | Est. LOC | % of Total |
|-------|---------------|---------|----------|------------|
| A | Core Infrastructure | 7 | 57 | 2.3% |
| B | Node CRUD | 6 | 84 | 3.4% |
| C | Edge CRUD | 4 | 57 | 2.3% |
| D | Display & Formatting | 3 | 112 | 4.5% |
| E | ID Resolution | 3 | 25 | 1.0% |
| F | NPC Domain | 4 | 55 | 2.2% |
| G | Location Domain | 2 | 22 | 0.9% |
| H | Facts Domain | 1 | 12 | 0.5% |
| I | Quest Domain | 5 | 50 | 2.0% |
| J | Consequence Domain | 4 | 59 | 2.4% |
| K | Inventory Operations | 9 | 121 | 4.9% |
| L | Player Operations | 8 | 88 | 3.5% |
| M | Custom Stats & Effects | 6 | 95 | 3.8% |
| N | Tick Engine | 13+5 | 580 | 23.4% |
| O | Wiki Display | 1 | 28 | 1.1% |
| P | CLI Entry Point | 2 | 262 | 10.6% |
| — | Imports, Colors, docstrings, blank lines | — | ~774 | 31.2% |
| **Total** | | **83+** | **2,481** | **100%** |

### 1.3 Inter-Group Coupling Matrix

```
         A  B  C  D  E  F  G  H  I  J  K  L  M  N  P
A (Infra) .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
B (Node)  ✓  .  .  .  .  .  .  .  .  .  .  .  .  .  .
C (Edge)  ✓  .  .  .  .  .  .  .  .  .  .  .  .  .  .
D (Disp)  ✓  ✓  ✓  .  .  .  .  .  .  .  .  .  .  .  .
E (Resol) ✓  ✓  .  .  .  .  .  .  .  .  .  .  .  .  .
F (NPC)   ✓  ✓  ✓  .  ✓  .  .  .  .  .  .  .  .  .  .
G (Loc)   ✓  ✓  ✓  .  .  .  .  .  .  .  .  .  .  .  .
H (Fact)  ✓  ✓  .  .  ✓  .  .  .  .  .  .  .  .  .  .
I (Quest) ✓  ✓  .  .  .  .  .  .  .  .  .  .  .  .  .
J (Cons)  ✓  ✓  .  .  .  .  .  .  .  .  .  .  .  .  .
K (Inv)   ✓  ✓  ✓  .  .  .  .  .  .  .  .  ✓  .  .  .
L (Play)  ✓  ✓  .  .  ✓  .  .  .  .  .  ✓  .  .  .  .
M (Stats) ✓  .  .  .  ✓  .  .  .  .  .  .  .  .  .  .
N (Tick)  ✓  ✓  .  .  ✓  .  .  .  .  ✓  ✓  ✓  ✓  .  .
P (CLI)   .  .  .  .  .  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓  .
```

**Key insight:** The Tick Engine (N) is the most coupled component — it touches 5 other domain groups. The CLI (P) is pure dispatch, not a coupling concern.

### 1.4 Code Smells

1. **Duplicated closures** — `_roll()` duplicated 3x, `_fm()` duplicated 3x in tick engine methods
2. **Load-modify-save in every method** — No unit-of-work pattern; each method calls `_load()` and `_save()` independently, causing N file I/O operations per compound action
3. **Embedded Colors class** (lines 26–56) — ANSI color constants duplicated from `lib/colors.py`
4. **Mixed abstraction levels** — Graph primitives (add_node) live alongside domain logic (npc_promote) and engine logic (tick)
5. **CLI in same file** — 262-line `main()` with argparse couples CLI parsing to business logic

### 1.5 Proposed Decomposition: 5 Focused Classes

#### Class 1: `GraphStore` (Groups A + B + C + E)
**File:** `lib/graph_store.py` (~220 LOC)
**Responsibility:** Graph primitives — nodes, edges, ID resolution, persistence

```python
class GraphStore:
    def __init__(self, campaign_dir: Path)
    def load(self) -> dict
    def save(self, data: dict) -> bool
    def add_node(self, node_id, node_type, name, data, **extra) -> bool
    def get_node(self, node_id) -> Optional[dict]
    def update_node(self, node_id, updates) -> bool
    def remove_node(self, node_id, cascade) -> bool
    def list_nodes(self, node_type) -> List[dict]
    def search_nodes(self, query, node_type) -> List[dict]
    def add_edge(self, from_id, to_id, edge_type, data) -> bool
    def get_edges(self, node_id, edge_type, direction) -> List[dict]
    def remove_edge(self, from_id, to_id, edge_type) -> bool
    def get_neighbors(self, node_id, edge_type, direction) -> List[dict]
    def resolve_id(self, name_or_id, node_type) -> Optional[str]
    def player_id(self) -> Optional[str]
    # Utilities: _slug, _now, _validate_node_id, _empty_world, _fact_next_id
```

#### Class 2: `WorldDomain` (Groups F + G + H + I + J)
**File:** `lib/world_domain.py` (~200 LOC)
**Responsibility:** Domain entity operations (NPC, location, fact, quest, consequence)

```python
class WorldDomain:
    def __init__(self, store: GraphStore)
    # NPC
    def npc_create(self, name, description, attitude) -> str
    def npc_event(self, node_id, event_text) -> bool
    def npc_promote(self, node_id) -> bool
    def npc_locate(self, node_id, location_id) -> bool
    # Location
    def location_create(self, name, description) -> str
    def location_connect(self, from_id, to_id, path_type) -> bool
    # Facts
    def fact_add(self, category, text) -> str
    # Quests
    def quest_create(self, name, quest_type, description) -> str
    def quest_objective_add / complete / fail(...)
    # Consequences
    def consequence_add / tick / resolve / list_resolved(...)
```

#### Class 3: `InventoryEngine` (Groups K + partial L)
**File:** `lib/inventory_engine.py` (~250 LOC)
**Responsibility:** All inventory, crafting, player stats, conditions

```python
class InventoryEngine:
    def __init__(self, store: GraphStore)
    def add(self, owner_id, item_name, qty, weight) -> bool
    def add_unique(self, owner_id, item_desc) -> bool
    def remove(self, owner_id, item_name, qty) -> bool
    def remove_unique(self, owner_id, item_name) -> bool
    def show(self, owner_id) -> str
    def transfer(self, from_id, to_id, item_name, qty) -> bool
    def craft(self, owner_id, recipe_id, qty) -> bool
    def use(self, owner_id, item_name) -> Optional[dict]
    def loot(self, owner_id, items, gold, xp) -> bool
    # Player stats
    def player_update_stat(self, stat, delta) -> bool
    def player_hp_max(self, delta) -> bool
    def player_condition(self, action, condition_name) -> bool
    def player_set(self, name) -> bool
    def player_show(self) -> str
    def wiki_add(self, entity_id, entity_type, name, ...) -> bool
    def wiki_recipe(self, entity_id) -> str
```

#### Class 4: `TickEngine` (Groups M + N)
**File:** `lib/tick_engine.py` (~680 LOC)
**Responsibility:** Time-based simulation — stat decay, effects, economy, production, random events

```python
class TickEngine:
    def __init__(self, store: GraphStore)
    # Custom stats
    def custom_stat_get / set / list / define(...)
    # Timed effects
    def timed_effect_add / list(...)
    # Tick sub-systems (private)
    def _tick_custom_stats(self, w, elapsed, sleeping) -> List[dict]
    def _tick_timed_effects(self, w, elapsed) -> List[str]
    def _check_stat_thresholds(self, w) -> List[dict]
    def _tick_production(self, w, elapsed) -> dict
    def _tick_expenses / income / random_events(...)
    def _tick_consequences_elapsed(self, w, elapsed) -> List[dict]
    def _tick_expenses_from_world / income_from_world / random_events_from_world(...)
    # Master orchestrator
    def tick(self, elapsed_hours, sleeping) -> dict
    # Shared helpers (extracted from nested closures)
    @staticmethod
    def _roll(expr: str) -> int
    @staticmethod
    def _format_money(amount, conf=None) -> str
```

**Key improvement:** Extract `_roll()` and `_fm()` into shared static methods, eliminating 6 duplicated closures.

#### Class 5: `WorldGraph` (Facade + Groups D + P)
**File:** `lib/world_graph.py` (~400 LOC)
**Responsibility:** Backward-compatible facade + formatting + CLI

```python
class WorldGraph:
    """Backward-compatible facade that delegates to focused classes."""
    def __init__(self, campaign_dir: Path = None):
        self.store = GraphStore(campaign_dir)
        self.domain = WorldDomain(self.store)
        self.inventory = InventoryEngine(self.store)
        self.tick_engine = TickEngine(self.store)

    # Delegate all existing methods for backward compatibility
    def add_node(self, *a, **kw): return self.store.add_node(*a, **kw)
    def npc_create(self, *a, **kw): return self.domain.npc_create(*a, **kw)
    def inventory_add(self, *a, **kw): return self.inventory.add(*a, **kw)
    def tick(self, *a, **kw): return self.tick_engine.tick(*a, **kw)
    # ... etc for all 87 methods

    # Own methods: format_node, format_node_list, stats
    def format_node(self, node_id) -> str: ...
    def format_node_list(self, nodes) -> str: ...
    def stats(self) -> str: ...

def main(): ...  # CLI stays here
```

### 1.6 LOC Distribution After Decomposition

| New Class | Est. LOC | Methods | SRP Focus |
|-----------|----------|---------|-----------|
| `GraphStore` | 220 | 20 | Data persistence + graph primitives |
| `WorldDomain` | 200 | 16 | Domain entity CRUD |
| `InventoryEngine` | 250 | 17 | Items, crafting, player stats |
| `TickEngine` | 680 | 18+2 | Time simulation engine |
| `WorldGraph` (facade) | 400 | delegates + 3 own | Backward compat + display + CLI |
| **Total** | **~1,750** | **~76** | Reduced due to deduplication |

**Net reduction:** ~730 LOC (29%) from deduplicating closures, removing embedded Colors, and simplifying the facade.

### 1.7 Migration Strategy

**Approach:** Incremental extraction with facade pattern (no big-bang rewrite)

**Phase 1: Extract GraphStore** (lowest risk)
1. Move groups A, B, C, E into `lib/graph_store.py`
2. Have `WorldGraph.__init__` create a `GraphStore` instance
3. Delegate node/edge methods to `self.store`
4. All external callers (`session_manager.py`, `entity_enhancer.py`, tools) continue using `WorldGraph` — zero changes needed
5. Run `uv run pytest` — all tests pass through facade

**Phase 2: Extract TickEngine** (highest value — eliminates duplication)
1. Move groups M, N into `lib/tick_engine.py`
2. Extract shared `_roll()` and `_format_money()` as static methods
3. `WorldGraph.tick()` delegates to `self.tick_engine.tick()`
4. Existing `dm-time.sh` post-hook calls `wg.tick()` — unchanged

**Phase 3: Extract WorldDomain** (medium complexity)
1. Move groups F, G, H, I, J into `lib/world_domain.py`
2. Delegate via facade
3. Tools calling `wg.npc_create()` etc. — unchanged

**Phase 4: Extract InventoryEngine** (highest complexity — most coupling)
1. Move groups K, L into `lib/inventory_engine.py`
2. Handle the player↔inventory coupling carefully
3. `inventory_manager.py` (legacy, 1,553 LOC) still exists for module compatibility — can be deprecated after module migration

**Phase 5: Slim down WorldGraph facade**
1. Remove method bodies, keep only delegation
2. Add deprecation warnings for direct WorldGraph method calls where appropriate
3. Update documentation

### 1.8 Backward Compatibility Strategy

- **Facade pattern** — `WorldGraph` retains all 87 method signatures, delegating to new classes
- **No external API changes** — all bash tools, session_manager, entity_enhancer, inventory_manager continue calling `WorldGraph` methods identically
- **Test compatibility** — existing tests import `WorldGraph` and call its methods; facade ensures they pass without modification
- **Gradual adoption** — new code can import focused classes directly (`from graph_store import GraphStore`), old code uses facade
- **Module middleware** — custom-stats middleware calls `wg.tick()`, `wg.custom_stat_set()` — all delegated through facade

### 1.9 Impact on Existing Tests

| Test File | Tests WorldGraph? | Impact |
|-----------|------------------|--------|
| `tests/test_session_manager.py` | Indirectly (via SessionManager) | None — facade preserves API |
| `tests/test_player_manager.py` | No (tests legacy PlayerManager) | None |
| `tests/test_consequence_manager.py` | No (tests legacy ConsequenceManager) | None |
| `tests/test_dice_combat.py` | No | None |
| `tests/test_encounter_engine.py` | Indirectly | None — facade |
| `tests/test_location_manager.py` | No (tests legacy) | None |
| `tests/test_note_manager.py` | No (tests legacy) | None |

**New tests needed:** Unit tests for `GraphStore`, `WorldDomain`, `InventoryEngine`, `TickEngine` (currently only integration-tested through the facade).

---

## 2. InventoryManager (lib/inventory_manager.py)

**LOC:** 1,554 | **Methods:** 38 (28 class methods + 2 standalone functions + 2 module-level helpers + `main()`) | **Inherits:** None

InventoryManager is the unified inventory/stats manager for player characters and party NPCs. It handles item CRUD, gold/HP/XP modifications, weight/encumbrance calculations, transfers between characters, crafting, consumable use, and formatted display output. Operates in dual mode: player (default) or NPC (via `npc_name` constructor parameter).

### 2.1 Complete Method Catalog by Responsibility Group

#### Group A: Load/Save & Initialization (9 methods, ~118 LOC, lines 86–227)

| Line | Method | Purpose |
|------|--------|---------|
| 86 | `__init__` | Init with campaign path + optional NPC name, load character + inventory |
| 100 | `_load_character` | Load player from `character.json`, merge custom stats from module-data |
| 115 | `_load_npc_as_character` | Load NPC `character_sheet` into player-compatible dict |
| 145 | `_save_character` | Persist player to `character.json` + custom stats to module-data |
| 160 | `_save_npc_character` | Write NPC stats back into `npcs.json` |
| 175 | `_load_inventory` | Load player inventory from `module-data/inventory-system.json` |
| 183 | `_load_npc_inventory` | Load NPC inventory from `module-data/inventory-party.json` |
| 189 | `_save_inventory` | Persist inventory (player or NPC path) |
| 199 | `_migrate_old_format` | One-time migration from legacy `equipment[]` or inline `inventory{}` |

**Coupling:** `ModuleDataManager` for module-data I/O, `currency.py` for gold migration, `character.json` / `npcs.json` for persistence. The dual player/NPC branching is replicated across load, save, and inventory methods (6 if/else branches).

#### Group B: Migration Helpers (3 methods, ~20 LOC, lines 228–247)

| Line | Method | Purpose |
|------|--------|---------|
| 228 | `_is_unique_item` | Heuristic: detect unique items by regex/keywords |
| 243 | `_parse_item_quantity` | Parse "Item (3 шт)" → (name, qty) |
| 199 | `_migrate_old_format` | *(listed in Group A — orchestrates B helpers)* |

**Coupling:** Only used by `_migrate_old_format`. Dead code if no legacy campaigns remain.

#### Group C: Weight & Encumbrance (9 methods, ~108 LOC, lines 249–355)

| Line | Method | Purpose |
|------|--------|---------|
| 251 | `_get_stackable_qty` | Get quantity from stackable entry (handles dict/int) |
| 257 | `_get_stackable_weight` | Get per-unit weight from stackable entry |
| 265 | `_set_stackable` | Set quantity+weight for stackable item |
| 281 | `_parse_unique_weight` | Extract `[Xkg]` tag from unique item string |
| 287 | `_get_unique_weight` | Get weight for unique item (tag or default) |
| 293 | `_add_weight_to_unique` | Append `[Xkg]` tag to unique item string |
| 298 | `calculate_weight` | Full weight calculation with encumbrance tiers (58 LOC) |
| 672 | `_categorize_item` | Keyword-based item categorization (ammo/weapon/food/etc.) |
| 985 | `show_weight_breakdown` | Formatted weight report (42 LOC) |

**Coupling:** Uses `ITEM_CATEGORIES`, `DEFAULT_WEIGHTS`, `ENCUMBRANCE_*` module constants. `calculate_weight` reads `character.stats.str` for capacity.

#### Group D: Transaction Validation & Execution (4 methods, ~186 LOC, lines 359–543)

| Line | Method | Purpose |
|------|--------|---------|
| 359 | `validate_transaction` | Pre-check gold, HP, item quantities, custom stats (50 LOC) |
| 412 | `apply_transaction` | Execute operations dict atomically with rollback (132 LOC) |
| 561 | `_preview_changes` | Dry-run display for `--test` mode (45 LOC) |
| 545 | `_print_weight_warning` | Emit encumbrance warnings post-transaction |

**Coupling:** Heart of the class. `apply_transaction` calls `_save_character`, `_save_inventory`, `calculate_weight`, `_print_changes_summary`. Operations dict is a mini-DSL with keys: `gold`, `hp`, `xp`, `add`, `remove`, `set`, `add_unique`, `remove_unique`, `custom_stats`, `_weights`, `_unique_weights`, `_dice_rolls`.

#### Group E: Display & Formatting (3 methods, ~152 LOC, lines 607–983)

| Line | Method | Purpose |
|------|--------|---------|
| 607 | `_print_changes_summary` | Rich ANSI output of transaction results (65 LOC) |
| 815 | `show_status` | Compact session-start status (50 LOC) |
| 880 | `show_inventory` | Full inventory display with filtering (103 LOC) |

**Coupling:** Uses `Colors` (imported or fallback stub), `format_money`/`format_delta` from currency.py. All three methods duplicate HP/XP/weight extraction logic.

#### Group F: Transfer & Drop (5 methods, ~82 LOC, lines 680–811)

| Line | Method | Purpose |
|------|--------|---------|
| 682 | `transfer_to` | Move items between player↔NPC inventories (67 LOC) |
| 750 | `_is_npc_name` | Check if name is a party NPC |
| 757 | `_is_player_name` | Check if name matches player character |
| 766 | `remove_item` | Direct removal (bypass transaction for sold/destroyed) (46 LOC) |
| 1027 | `show_party_inventory` | Display all party members' inventories (34 LOC) |

**Coupling:** `transfer_to` creates a second `InventoryManager` instance for the target — recursive instantiation pattern. `remove_item` bypasses `apply_transaction`, saving directly — inconsistent with the transaction model.

#### Group G: Wiki Integration — Standalone Functions (2 functions, ~223 LOC, lines 1327–1549)

| Line | Function | Purpose |
|------|----------|---------|
| 1327 | `_craft_item` | Craft from wiki recipe: check ingredients, roll skill, apply transaction (157 LOC) |
| 1486 | `_use_consumable` | Use consumable: lookup wiki effects, build operations, apply (64 LOC) |

**Coupling:** Import `WikiManager` at call time (lazy import). Receive `manager` as parameter. These are **standalone functions**, not class methods — extracted but still tightly coupled to `InventoryManager` internals (access `.inventory`, `.character`, `.apply_transaction`, `.reason`).

#### Group H: CLI Entry Point (2 functions, ~260 LOC, lines 1065–1325)

| Line | Function | Purpose |
|------|----------|---------|
| 1065 | `_resolve_target` | Map character name → NPC name or None (player) |
| 1084 | `main` | argparse CLI with 8 subcommands: update, show, weigh, party, transfer, loot, remove, use, craft (241 LOC) |

**Coupling:** Pure dispatch. Duplicates gold-parsing logic between `update` and `loot` subcommands (lines 1201–1212 ≈ 1271–1282).

### 2.2 Responsibility Group Summary

| Group | Responsibility | Methods | Est. LOC | % of Total |
|-------|---------------|---------|----------|------------|
| A | Load/Save & Init | 9 | 118 | 7.6% |
| B | Migration Helpers | 2 | 20 | 1.3% |
| C | Weight & Encumbrance | 9 | 108 | 6.9% |
| D | Transaction System | 4 | 186 | 12.0% |
| E | Display & Formatting | 3 | 152 | 9.8% |
| F | Transfer & Drop | 5 | 82 | 5.3% |
| G | Wiki Integration (standalone) | 2 | 223 | 14.3% |
| H | CLI Entry Point | 2 | 260 | 16.7% |
| — | Constants, imports, blank lines | — | ~405 | 26.1% |
| **Total** | | **36+** | **1,554** | **100%** |

### 2.3 Dual Player/NPC Mode Analysis

The `is_npc` flag creates **parallel code paths** throughout the class:

| Operation | Player Path | NPC Path |
|-----------|------------|----------|
| Load character | `character.json` | `npcs.json` → `character_sheet` → normalize to player dict |
| Save character | `character.json` + module-data `custom-stats` | `npcs.json` → denormalize back to `character_sheet` |
| Load inventory | `module-data/inventory-system.json` | `module-data/inventory-party.json[npc_name]` |
| Save inventory | `module-data/inventory-system.json` | `module-data/inventory-party.json[npc_name]` |

**Issues:**
1. **Normalization asymmetry** — NPC data is normalized to player format on load and denormalized on save. Fields like `xp` (int vs dict), `hp` (int vs dict), and `money` (with gold migration) are handled differently. This creates subtle bugs when NPC data doesn't match expected shapes.
2. **No shared abstraction** — Both paths produce the same `self.character` dict, but the mapping logic is duplicated across 4 method pairs instead of using a Strategy or Adapter pattern.
3. **Recursive instantiation** — `transfer_to` creates a new `InventoryManager(npc_name=target)` to add items to the target. `show_party_inventory` creates one per NPC. This causes redundant file I/O (character.json loaded N+1 times).

### 2.4 Code Smells

1. **God class** — 1,554 LOC mixing persistence, business logic, display, CLI parsing, and wiki integration
2. **Operations dict as mini-DSL** — `apply_transaction` accepts a `Dict` with 11+ possible keys (`gold`, `hp`, `xp`, `add`, `remove`, `set`, `add_unique`, `remove_unique`, `custom_stats`, `_weights`, `_unique_weights`, `_dice_rolls`). No schema, no type safety, underscore-prefixed "private" keys mixed with public ones.
3. **Inconsistent save patterns** — `apply_transaction` does atomic save with rollback; `remove_item` saves directly; `transfer_to` calls `apply_transaction` then does additional saves. Three different consistency models.
4. **Duplicated display logic** — HP extraction (`isinstance(hp, dict)` check) appears 6 times. Gold formatting appears 8+ times. Weight status coloring appears in 3 methods.
5. **Hardcoded Russian strings** — `_craft_item` and `_use_consumable` contain Russian UI text ("Ингредиенты:", "АВТОУСПЕХ", "скрафтил", etc.) violating the English-only rules policy.
6. **Duplicated gold parsing** — Lines 1201–1212 (update) ≈ 1271–1282 (loot) — identical `parse_money` loop.
7. **Module constants as global state** — `ITEM_CATEGORIES`, `DEFAULT_WEIGHTS`, `ENCUMBRANCE_TIERS` are hardcoded at module level with mixed Russian/English keywords, not configurable per campaign.

### 2.5 Proposed Decomposition: 5 Focused Classes

#### Class 1: `CharacterStore` (Group A persistence)
**File:** `lib/character_store.py` (~120 LOC)
**Responsibility:** Load/save character and inventory data, abstracting player vs NPC differences

```python
class CharacterStore:
    """Unified character data access for player and NPC."""
    def __init__(self, campaign_path: Path, npc_name: Optional[str] = None)
    def load_character(self) -> dict
    def save_character(self, data: dict)
    def load_inventory(self) -> dict
    def save_inventory(self, data: dict)
    @property
    def is_npc(self) -> bool
    @property
    def name(self) -> str
```

**Key improvement:** Encapsulate the player/NPC branching in one place. All other classes receive a `CharacterStore` and never check `is_npc`.

#### Class 2: `WeightCalculator` (Group C)
**File:** `lib/weight_calculator.py` (~100 LOC)
**Responsibility:** Weight calculation, encumbrance tiers, item categorization

```python
class WeightCalculator:
    def __init__(self, config: Optional[dict] = None)  # campaign-specific weight config
    def calculate(self, inventory: dict, str_score: int) -> dict
    def categorize_item(self, name: str) -> str
    def get_stackable_weight(self, item_name: str, val) -> float
    def get_unique_weight(self, item: str) -> float
```

**Key improvement:** Configurable weight constants (move `ITEM_CATEGORIES`, `DEFAULT_WEIGHTS`, `ENCUMBRANCE_TIERS` into campaign config). Pure computation, no I/O.

#### Class 3: `InventoryTransaction` (Group D)
**File:** `lib/inventory_transaction.py` (~200 LOC)
**Responsibility:** Atomic inventory/stat modifications with validation and rollback

```python
@dataclass
class TransactionOps:
    """Typed replacement for the operations dict."""
    gold: int = 0
    hp: int = 0
    xp: int = 0
    add: Dict[str, int] = field(default_factory=dict)
    remove: Dict[str, int] = field(default_factory=dict)
    add_unique: List[str] = field(default_factory=list)
    remove_unique: List[str] = field(default_factory=list)
    custom_stats: Dict[str, int] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)

class InventoryTransaction:
    def __init__(self, store: CharacterStore, weight_calc: WeightCalculator)
    def validate(self, ops: TransactionOps) -> Tuple[bool, List[str]]
    def execute(self, ops: TransactionOps, test_mode: bool = False) -> bool
```

**Key improvement:** Replace untyped `Dict` operations with `TransactionOps` dataclass. Eliminate `_weights`/`_dice_rolls` underscore-key hack.

#### Class 4: `InventoryDisplay` (Group E + partial F)
**File:** `lib/inventory_display.py` (~200 LOC)
**Responsibility:** All formatted output — status, full inventory, weight breakdown, party summary, transaction summaries

```python
class InventoryDisplay:
    def __init__(self, currency_config: dict)
    def print_status(self, character: dict, inventory: dict, weight_info: dict)
    def print_inventory(self, character: dict, inventory: dict, weight_info: dict, category: Optional[str] = None)
    def print_weight_breakdown(self, character: dict, weight_info: dict)
    def print_party_summary(self, party_data: List[dict])
    def print_transaction_result(self, changes_log: list, character: dict)
    def print_weight_warning(self, weight_info: dict, who: str)
    def preview_changes(self, ops: TransactionOps, character: dict)
```

**Key improvement:** Extract all ANSI formatting into one class. Eliminate duplicated HP/XP/weight extraction. Display methods become pure formatters that accept data, not managers.

#### Class 5: `InventoryManager` (Facade + Transfer + CLI)
**File:** `lib/inventory_manager.py` (~250 LOC)
**Responsibility:** Backward-compatible facade, transfer logic, CLI entry point

```python
class InventoryManager:
    """Backward-compatible facade delegating to focused classes."""
    def __init__(self, campaign_path: Path, npc_name: Optional[str] = None):
        self.store = CharacterStore(campaign_path, npc_name)
        self.weight_calc = WeightCalculator()
        self.transaction = InventoryTransaction(self.store, self.weight_calc)
        self.display = InventoryDisplay(load_config(campaign_path))

    # Delegate existing methods for backward compat
    def apply_transaction(self, ops, test_mode=False) -> bool
    def validate_transaction(self, ops) -> Tuple[bool, List[str]]
    def calculate_weight(self) -> dict
    def show_inventory(self, category=None)
    def show_status(self)
    def transfer_to(self, target, items, unique_items, test_mode=False) -> bool
    def remove_item(self, item, qty=None, is_unique=False) -> bool
```

### 2.6 LOC Distribution After Decomposition

| New Class | Est. LOC | Methods | SRP Focus |
|-----------|----------|---------|-----------|
| `CharacterStore` | 120 | 7 | Data persistence + player/NPC abstraction |
| `WeightCalculator` | 100 | 5 | Weight computation + categorization |
| `InventoryTransaction` | 200 | 3 | Atomic operations + validation |
| `InventoryDisplay` | 200 | 7 | All formatted output |
| `InventoryManager` (facade) | 250 | delegates + transfer + CLI | Backward compat |
| `_craft_item` / `_use_consumable` | 220 | 2 | Wiki integration (stay as functions or move to `wiki_actions.py`) |
| **Total** | **~1,090** | **~24+** | Reduced via deduplication |

**Net reduction:** ~460 LOC (30%) from eliminating duplicated HP/gold extraction, gold parsing, display logic, and the player/NPC branching repetition.

### 2.7 Migration Strategy

**Approach:** Incremental extraction with facade pattern (same as WorldGraph)

**Phase 1: Extract CharacterStore** (highest value — eliminates dual-mode branching)
1. Move load/save methods into `lib/character_store.py`
2. `InventoryManager.__init__` creates `self.store = CharacterStore(...)` and sets `self.character = self.store.load_character()`
3. Replace all `self._save_character()` calls with `self.store.save_character(self.character)`
4. All bash tools call `InventoryManager` unchanged — zero external impact
5. Run `uv run pytest`

**Phase 2: Extract WeightCalculator** (low risk — pure computation)
1. Move weight methods + constants into `lib/weight_calculator.py`
2. `InventoryManager` delegates `calculate_weight` to `self.weight_calc.calculate(...)`
3. Make constants configurable via campaign config (optional)

**Phase 3: Extract InventoryDisplay** (medium risk — many call sites)
1. Move all `show_*` and `_print_*` methods into `lib/inventory_display.py`
2. Deduplicate HP/XP/weight extraction into shared helpers
3. `InventoryManager` delegates display calls

**Phase 4: Extract InventoryTransaction** (highest risk — core logic)
1. Introduce `TransactionOps` dataclass
2. Move `validate_transaction` and `apply_transaction` into `lib/inventory_transaction.py`
3. Keep facade methods that convert old `Dict` format → `TransactionOps` for backward compat
4. `remove_item` should be refactored to use `InventoryTransaction` instead of direct saves

**Phase 5: Fix standalone functions**
1. Move `_craft_item` and `_use_consumable` to `lib/wiki_actions.py`
2. Replace Russian UI strings with English (rules compliance)
3. Import in CLI only when needed (maintain lazy import pattern)

### 2.8 Backward Compatibility Strategy

- **Facade pattern** — `InventoryManager` retains all existing method signatures
- **Operations dict** — Old `Dict`-based transaction format continues to work through facade adapter that converts to `TransactionOps`
- **Bash tool compatibility** — `dm-inventory.sh` calls `main()` CLI, which stays in `inventory_manager.py`
- **Module middleware** — custom-stats module post-hooks call `InventoryManager` methods; facade ensures they work unchanged
- **`transfer_to` recursive pattern** — Still creates child `InventoryManager` instances, but each internally uses `CharacterStore` (cleaner, same external behavior)

### 2.9 Impact on Existing Tests

| Test File | Tests InventoryManager? | Impact |
|-----------|------------------------|--------|
| `tests/test_inventory_manager.py` | Yes (if exists) | Facade preserves API |
| `tests/test_session_manager.py` | Indirectly (via session flow) | None |
| `tests/test_dice_combat.py` | No | None |

**New tests needed:** Unit tests for `CharacterStore` (player vs NPC paths), `WeightCalculator` (encumbrance tiers), `InventoryTransaction` (validation + rollback), `InventoryDisplay` (output formatting).

---

*Section 3 (secondary problem classes) will be added by subsequent subtasks.*
