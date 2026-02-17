# DM System Modules

Modular extensions for DM System campaigns. Each module adds specific mechanics that can be enabled/disabled per campaign.

**Architecture:** CORE knows nothing about modules. Modules depend on CORE APIs. DM (Claude) reads each module's `rules.md` and calls module tools at the right moments.

## Available Modules

| Module | Status | Tests | Description |
|--------|--------|-------|-------------|
| 🍔 [survival-stats](survival-stats/) | ✅ Active | 34 | Custom stats (hunger, thirst, radiation) with time effects engine |
| 🔫 [firearms-combat](firearms-combat/) | ✅ Active | 9 | Firearms combat with PEN/PROT scaling, fire modes, RPM |
| 🎲 [encounter-system](encounter-system/) | ✅ Active | 16 | Random encounters during travel with waypoints |
| 🗺️ [coordinate-navigation](coordinate-navigation/) | ✅ Active | 14 | Coordinate system, pathfinding, ASCII/GUI maps |

## Module Structure

```
module-name/
├── module.json           # Metadata, dependencies, features
├── rules.md             # DM instructions (when to call module tools)
├── lib/
│   └── *.py             # Module business logic
├── tools/
│   └── dm-*.sh          # Bash wrappers (entry points for DM)
└── tests/
    └── test_*.py        # pytest tests (isolated with tmp_path)
```

## How Modules Work

1. **CORE** provides data CRUD and clock management — no module awareness
2. **Module** contains all business logic, imports CORE APIs (`PlayerManager`, `JsonOperations`)
3. **DM (Claude)** reads `rules.md` at session start, calls module tools when appropriate

## Running Tests

```bash
# All module tests
uv run python -m pytest .claude/modules/*/tests/ -v

# Specific module
uv run python -m pytest .claude/modules/survival-stats/tests/ -v
```

## Using Modules

```bash
bash tools/dm-module.sh scan     # Scan and register all modules
bash tools/dm-module.sh list     # List available modules
bash tools/dm-module.sh info --module survival-stats  # Module details
```

---

**Current Version**: v1.5.0
**Last Updated**: 2026-02-17
