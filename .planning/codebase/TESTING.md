# Testing Patterns

**Analysis Date:** 2026-03-29 (post WorldGraph migration)

## Test Framework

**Runner:**
- `pytest` (version not pinned, `pytest-cov>=7.0.0` in dev deps)
- Config: `pyproject.toml` → `[tool.pytest.ini_options]`

**Assertion Library:**
- pytest built-in `assert` — no external assertion library

**Run Commands:**
```bash
uv run pytest                        # run all tests
uv run pytest tests/test_world_graph.py  # single file
uv run pytest -k "TestAddNode"       # single class
uv run pytest --cov=lib              # coverage (requires pytest-cov)
```

## Test File Organization

**Location:**
- Core tests: `tests/` (flat, co-located with project root)
- Module tests: `.claude/additional/modules/<name>/tests/` (each module owns its tests)

**Naming:**
- `test_<lib_module_name>.py` — mirrors the lib filename: `test_world_graph.py` ↔ `lib/world_graph.py`
- No `*_test.py` suffix variant used

**pytest discovery:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests", ".claude/additional/modules"]
```
Module tests are auto-discovered from `.claude/additional/modules` subtrees.

**Structure:**
```
tests/
  conftest.py               # shared fixtures (minimal_campaign, stalker_campaign)
  test_world_graph.py       # WorldGraph CRUD, edges, search
  test_tick_engine.py       # WorldGraph tick/time methods
  test_dice_combat.py       # DiceRoller, _resolve_attack, auto-combat, spell/creature lookup
  test_encounter_engine.py  # check_encounter, _weighted_choice
  test_player_manager.py    # PlayerManager HP, XP, conditions (WorldGraph player node)
  test_session_manager.py   # SessionManager move, save/restore, context (WorldGraph)

.claude/additional/modules/world-travel/tests/
  test_navigation.py        # PathFinder coordinate math
  test_encounter_engine.py  # module encounter logic
  test_vehicle_manager.py
  test_hierarchy_manager.py

.claude/additional/modules/mass-combat/tests/
  test_mass_combat.py

.claude/additional/modules/firearms-combat/tests/
  test_firearms_resolver.py
```

## Test Structure

**Suite Organization — class per behavior group:**
```python
class TestAddNode:
    def test_add_node_creates_entry(self, graph): ...
    def test_add_node_rejects_duplicate_id(self, graph): ...
    def test_add_node_validates_id_format(self, graph): ...
    def test_add_node_with_data(self, graph): ...

class TestGetNode:
    def test_get_node_returns_data(self, populated_graph): ...
    def test_get_node_returns_none_for_missing(self, graph): ...
```

- One `class Test<Operation>` per logical operation or feature area
- All test methods are plain `def test_<scenario>` (no async)
- Methods receive fixtures as args (standard pytest injection)

**Patterns:**
- Setup: factory function or fixture creates isolated `tmp_path` environment
- No shared mutable state between tests — every test gets a fresh `tmp_path`
- Teardown: none needed — `tmp_path` is pytest-managed temp dir, auto-cleaned
- Assertion: single `assert` per logical claim, sometimes 2-3 per test for related properties

## Mocking

**Framework:** `unittest.mock` (`patch`, `MagicMock`)

**Used in:**
- `tests/test_dice_combat.py` — `from unittest.mock import patch, MagicMock`
- `tests/test_tick_engine.py` — `from unittest.mock import patch`
- `tests/test_encounter_engine.py` — `from unittest.mock import patch`

**Primary pattern — patch random for deterministic rolls:**
```python
from unittest.mock import patch

def test_always_encounters(self, campaign_dir, base_overview):
    write_overview(campaign_dir, base_overview)
    with patch("encounter_engine.random.random", return_value=0.0):
        result = check_encounter(5.0, campaign_dir)
    assert result is not None
```

**What to Mock:**
- `random.random` / `random.randint` for dice and encounter probability tests
- File I/O functions only if testing failure paths (rare)

**What NOT to Mock:**
- File system — use `tmp_path` fixture instead; tests write real JSON files
- `WorldGraph`, `PlayerManager` and other lib classes — test against real instances with `tmp_path`

## Fixtures and Factories

**Shared fixtures** in `tests/conftest.py`:
```python
@pytest.fixture
def minimal_campaign(tmp_path):
    campaign_dir = tmp_path / "minimal-campaign"
    campaign_dir.mkdir()
    overview = {"campaign_name": "Minimal Test", "time_of_day": "Day", ...}
    with open(campaign_dir / "campaign-overview.json", "w", encoding="utf-8") as f:
        json.dump(overview, f, indent=2, ensure_ascii=False)
    return campaign_dir

@pytest.fixture
def stalker_campaign(tmp_path):
    # Full campaign with character.json, locations.json, custom_stats, encounters
    ...
    return campaign_dir
```

**Local factory functions** (preferred over fixtures for parameterized setup):
```python
def make_campaign(tmp_path, overview_extra=None, character=None):
    campaign_dir = tmp_path / "world-state" / "campaigns" / "test-campaign"
    campaign_dir.mkdir(parents=True)
    (tmp_path / "world-state" / "active-campaign.txt").write_text("test-campaign")
    # write campaign-overview.json and character.json
    return str(ws), campaign_dir

def make_world_state(tmp_path, consequences=None):
    # similar pattern for consequence/session tests
    return str(ws), camp
```

**Local fixtures per test file:**
```python
@pytest.fixture
def graph(tmp_path):
    return WorldGraph(tmp_path)

@pytest.fixture
def populated_graph(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_node("player:hero", "player", "Hero")
    g.add_node("npc:merchant", "npc", "Old Merchant", data={"attitude": "friendly"})
    # ... add edges
    return g
```

**Location:**
- Shared fixtures: `tests/conftest.py`
- Module-specific fixtures: defined inline in the test file itself

## Coverage

**Requirements:** None enforced (no `--cov-fail-under` in config)

**View Coverage:**
```bash
uv run pytest --cov=lib --cov-report=term-missing
```

**Approximate coverage by area:**
- `WorldGraph` — high coverage via `test_world_graph.py` + `test_tick_engine.py` (153 test functions total in `tests/`)
- `PlayerManager`, `SessionManager` — dedicated test files (all use world.json fixtures)
- `dice.py` auto-combat (`_resolve_attack`, `_resolve_spell_attack`, creature/spell lookup) — covered in `test_dice_combat.py`
- `FirearmsCombatResolver` — 15 tests in module test suite
- `MassCombatEngine` — 22 tests in module test suite
- `inventory_manager.py`, `currency.py` — **no dedicated test files** (gap)
- `entity_enhancer.py`, `rag/` — **no test files** (gap)

## Test Types

**Unit Tests:**
- Scope: single class or function, isolated from file system via `tmp_path`
- All tests in `tests/` are unit tests
- No network calls in tests

**Integration Tests:**
- Not formally separated — some tests in `tests/test_session_manager.py` and `test_player_manager.py` touch multiple managers (PlayerManager + file persistence verification)
- Module tests in `.claude/additional/modules/*/tests/` test module libs end-to-end

**E2E Tests:**
- Not used — no shell/CLI invocation tests

## Common Patterns

**Testability via `require_active_campaign=False`:**
All managers accept a direct campaign path bypassing the active-campaign discovery:
```python
mgr = PlayerManager(ws)  # ws = str(tmp_path / "world-state")
# internally: CampaignManager reads active-campaign.txt to find campaign dir
```
Or for WorldGraph (accepts `campaign_dir` directly):
```python
g = WorldGraph(tmp_path)  # tmp_path IS the campaign dir
```

**Persistence verification pattern (WorldGraph):**
```python
def test_hp_persisted_to_file(self, tmp_path):
    ws, camp = make_campaign(tmp_path)
    mgr = PlayerManager(ws)
    mgr.modify_hp("Hero", -5)
    world = json.loads((camp / "world.json").read_text())
    char = world["nodes"]["player:active"]["data"]
    assert char["hp"]["current"] == 15
```
Reading world.json directly after the operation verifies atomic write worked correctly.

**Edge case pattern — clamping:**
```python
def test_hp_clamps_at_zero(self, tmp_path):
    ws, camp = make_campaign(tmp_path)
    mgr = PlayerManager(ws)
    result = mgr.modify_hp("Hero", -999)
    assert result["current_hp"] == 0
    assert result["unconscious"] is True

def test_hp_clamps_at_max(self, tmp_path):
    ...
    result = mgr.modify_hp("Hero", +999)
    assert result["current_hp"] == 20
```

**Deterministic randomness:**
```python
with patch("encounter_engine.random.random", return_value=0.0):
    result = check_encounter(5.0, campaign_dir)
```

**None/missing returns:**
```python
def test_get_node_returns_none_for_missing(self, graph):
    assert graph.get_node("npc:nobody") is None

def test_no_config_returns_none(self, campaign_dir):
    write_overview(campaign_dir, {"campaign_name": "Test"})
    result = check_encounter(3.0, campaign_dir)
    assert result is None
```

---

*Testing analysis: 2026-03-29*
