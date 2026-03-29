# Coding Conventions

**Analysis Date:** 2026-03-29 (post WorldGraph migration)

## Naming Patterns

**Files:**
- Python libs: `snake_case.py` — `world_graph.py`, `inventory_manager.py`, `entity_manager.py`
- Bash tools: `dm-kebab-case.sh` — `dm-roll.sh`, `dm-session.sh`, `dm-inventory.sh`
- Test files: `test_<module_name>.py` — mirrors the lib filename exactly

**Classes:**
- PascalCase — `WorldGraph`, `PlayerManager`, `EntityManager`, `DiceRoller`, `JsonOperations`
- Manager suffix for stateful CRUD classes — `SessionManager`, `CampaignManager`, `PlayerManager`

**Methods:**
- `snake_case` throughout
- Private/internal helpers prefixed with `_` — `_load()`, `_save()`, `_find_campaign_dir()`, `_resolve_attack()`
- Public API never prefixed
- Boolean-return methods use verb phrases: `add_node()`, `update_node()`, `can_afford()`

**Variables:**
- `snake_case` for all locals and attributes
- UPPER_CASE for module-level constants — `NODE_TYPES`, `EDGE_TYPES`, `SCHEMA_VERSION`, `ENCUMBRANCE_TIERS`

**JSON keys:**
- `snake_case` in all data files — `"campaign_name"`, `"time_of_day"`, `"current_date"`
- Node IDs use `type:kebab-name` format — `"player:hero"`, `"npc:merchant"`, `"location:tavern"`

## Code Style

**Formatter:**
- `black` with `line-length = 100`, target `py311`/`py312` (configured in `pyproject.toml`)

**Linter:**
- `ruff` with `line-length = 100`, rule sets: `E, F, W, C90, I, N, UP, B, A, C4, SIM, RET`
- E501 (line-too-long) suppressed — black handles line length

**Type hints:**
- `mypy` configured but `disallow_untyped_defs = false` — type hints present in signatures but not enforced on all functions
- `from typing import Dict, List, Optional, Tuple, Any` used consistently; `Optional[X]` preferred over `X | None`

## Import Organization

**Order:**
1. Standard library (`json`, `sys`, `re`, `argparse`, `pathlib`, `datetime`, `typing`)
2. Infrastructure path setup (`sys.path.insert(0, ...)`) if needed
3. Internal project imports with try/except fallback for path flexibility

**Path injection pattern** (used in every lib file run standalone):
```python
sys.path.insert(0, str(Path(__file__).parent))
```

**Module imports:** Modules use `from lib.<module> import <Class>` pattern:
```python
PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))
from lib.world_graph import WorldGraph
from lib.module_data import ModuleDataManager
```

**Colors import pattern** (defensive try/except everywhere):
```python
try:
    from lib.colors import Colors
except ImportError:
    try:
        from colors import Colors
    except ImportError:
        class Colors:
            RESET = RS = RED = R = GREEN = G = ""
```

## Error Handling

**Two distinct strategies depending on context:**

**CLI entry points (`main()` functions, `world_graph.py` argparse handlers):**
- Use `sys.exit(1)` with `print(..., file=sys.stderr)` for fatal errors
- Use `print(f"[ERROR] ...")` for readable CLI errors

**Library methods (called by other Python code):**
- Return `False` / `None` for recoverable failures — `add_node()` returns `False` on duplicate
- Return `True` for success — uniform boolean contract in `JsonOperations`, `WorldGraph`
- Raise `RuntimeError` for programming errors — `EntityManager.__init__` raises when no active campaign and `require_active_campaign=True`
- Silent fallback with defaults: `json_ops.load_json()` catches `JSONDecodeError` and returns default `{}`

**JSON persistence:**
- Atomic writes everywhere via temp file + rename pattern (from `json_ops.py`):
```python
temp_path = filepath.with_suffix('.tmp')
with open(temp_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
temp_path.replace(filepath)
```
- `ensure_ascii=False` used in all JSON writes (38 occurrences in lib/) — supports Unicode campaign data

## Logging

**Framework:** None — `print()` to stdout/stderr only

**Patterns:**
- `print(f"[ERROR] ...", file=sys.stderr)` — errors go to stderr
- `print(f"[SUCCESS] ...")` — positive confirmations to stdout
- ANSI color tags via `lib/colors.py`: `tag_success()`, `tag_error()`, `tag_warning()`
- No structured logging, no log levels, no timestamps in lib code

## Comments / Docstrings

**Module-level docstrings:** Always present, single paragraph describing module purpose. Example from `world_graph.py`:
```python
"""
WorldGraph — unified graph-based world state manager.
Nodes (player, npc, location, ...) connected by typed edges (...).
Data lives in world.json per campaign.
"""
```

**Class docstrings:** Present on all public classes, 1-2 sentences.

**Method docstrings:** Present on public methods, using plain prose (not Google/NumPy style). Args/Returns documented inline as plain text when non-obvious:
```python
def load_json(self, filename: str, default: Any = None) -> Any:
    """
    Load JSON file with error handling
    Returns default value if file doesn't exist or is invalid
    """
```

**Inline comments:** Sparse — used for non-obvious business logic (`# D&D 5e XP thresholds for levels 1-20`) and section separators in large files.

## Function Design

**Size:** Methods tend to be medium (10-40 lines). `main()` functions are long (50-150+ lines) as they handle all argparse subcommands.

**Parameters:** Constructor always accepts `Optional` campaign path for testability:
```python
def __init__(self, world_state_dir: Optional[str] = None, require_active_campaign: bool = True):
```
`require_active_campaign=False` + direct path = testing mode across all managers.

**Return Values:**
- Boolean for write operations (`True`/`False`)
- `dict` or `None` for read operations
- Validators return `Tuple[bool, Optional[str]]` — `(is_valid, error_message)`

## Module Design

**Exports:** No `__all__` defined anywhere. All public names are importable.

**Barrel files:** `lib/__init__.py` exists but is empty — no re-exports.

**CLI dual-use pattern:** Every lib file that can be run standalone has:
```python
if __name__ == "__main__":
    main()
```
`main()` sets up `argparse` with subcommands and calls library methods. Same file serves as both importable module and CLI tool.

## Bash Tool Pattern

All tools in `tools/` follow an identical 3-line pattern:
```bash
#!/bin/bash
source "$(dirname "$0")/common.sh"
$PYTHON_CMD "$LIB_DIR/<module>.py" "$@"
CORE_RC=$?
dispatch_middleware_post "dm-<tool>.sh" "$@"
exit $CORE_RC
```
- `common.sh` sourced for `PYTHON_CMD`, `LIB_DIR`, campaign path resolution, and middleware dispatch
- `dispatch_middleware_post` called after CORE for module hooks (no-op if modules not loaded)

## Campaign-Agnosticism Rule

Module code (`.claude/additional/modules/`) must contain zero campaign-specific content (character names, spell names, faction names). Campaign-specific rules go in `campaign-rules.md` per campaign. Violation = public repo pollution.

---

*Convention analysis: 2026-03-29*
