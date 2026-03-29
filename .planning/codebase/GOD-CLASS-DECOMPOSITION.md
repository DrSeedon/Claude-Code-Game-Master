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

*Sections 2 and 3 (InventoryManager and secondary problem classes) will be added by subsequent subtasks.*
