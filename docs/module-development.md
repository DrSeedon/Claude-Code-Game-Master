# Module Development Guide

Create custom modules for DM Claude. Each module is a self-contained folder that hooks into the CORE system without modifying it.

---

## Quick Start

```bash
mkdir -p .claude/additional/modules/my-module/{lib,tools,middleware,tests}
```

Create `module.json`, `rules.md`, and optionally `creation-rules.md`. That's it — the system auto-discovers modules by scanning for `module.json`.

---

## Directory Structure

```
.claude/additional/modules/my-module/
├── module.json              # Required — module manifest
├── rules.md                 # Required — DM instructions during gameplay
├── creation-rules.md        # Optional — DM instructions during /new-game
├── README.md                # Optional — developer docs
├── lib/                     # Python modules
│   └── my_engine.py
├── tools/                   # CLI wrappers (bash → python)
│   └── dm-my-tool.sh
├── middleware/               # Hooks into CORE tools
│   ├── dm-player.sh          # Intercepts dm-player.sh calls
│   └── dm-time.sh.post       # Runs AFTER dm-time.sh completes
└── tests/
    └── test_my_engine.py
```

---

## module.json

The manifest. Every field explained:

```json
{
  "id": "my-module",
  "name": "My Module",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "One-line description shown in module list",

  "category": "character-mechanics",
  "genre_tags": ["fantasy", "survival", "scifi"],
  "tags": ["custom-tag"],

  "enabled_by_default": false,
  "dependencies": [],
  "optional_dependencies": [],
  "incompatible_with": [],

  "middleware": ["dm-player.sh"],
  "post_middleware": ["dm-time.sh.post"],
  "replaces": [],

  "features": ["Feature 1", "Feature 2"],
  "use_cases": ["When to use this module"],
  "architecture": "Brief technical summary"
}
```

### Key fields

| Field | Purpose |
|-------|---------|
| `id` | Unique identifier. Must match folder name. |
| `enabled_by_default` | If `true`, module is active for new campaigns without user selection. |
| `dependencies` | List of module IDs that must be enabled first. System blocks activation if deps are missing. |
| `optional_dependencies` | Modules that enhance functionality if present. Not required — graceful fallback if absent. |
| `incompatible_with` | List of module IDs that conflict. Advisory only (not enforced). |
| `middleware` | CORE tools this module intercepts (pre-hook). Return exit 0 to handle, non-zero to let CORE handle. |
| `post_middleware` | CORE tools this module hooks after execution. File must be named `<tool>.post`. |
| `replaces` | DM slot names this module replaces (e.g., `"movement"` replaces `dm-slots/movement.md`). |

---

## Middleware

Middleware is how modules hook into CORE tools without modifying them. Three types:

### Pre-hook (intercept)

File: `middleware/dm-player.sh`

Called BEFORE CORE runs. If your middleware exits 0, CORE is skipped. Exit non-zero to let CORE handle it.

```bash
#!/bin/bash
MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Handle --help
if [ "$1" = "--help" ]; then
    echo "  my-action <args>    Description of what it does"
    exit 1  # exit 1 = don't consume the call
fi

ACTION="$1"
shift

case "$ACTION" in
    my-action)
        exec bash "$MODULE_DIR/tools/dm-my-tool.sh" "$@"
        ;;
esac

# Fall through to CORE for unrecognized actions
exit 1
```

### Post-hook

File: `middleware/dm-time.sh.post`

Called AFTER CORE runs. Always runs (return code ignored). Use for side effects.

```bash
#!/bin/bash
MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Parse args passed from CORE
ELAPSED=""
for arg in "$@"; do
    if [ "$arg" = "--elapsed" ]; then
        # next arg is the value
    fi
done

[ -n "$ELAPSED" ] || exit 0
bash "$MODULE_DIR/tools/dm-my-tool.sh" tick --elapsed "$ELAPSED"
```

### Help hook

When CORE tool prints help, it calls `dispatch_middleware_help "dm-tool.sh"`. Your middleware receives `--help` as `$1`. Print additional help lines and exit 1.

---

## Slot Replacement

Modules can replace vanilla DM rule slots. Add slot names to `"replaces"` in `module.json`:

```json
"replaces": ["movement"]
```

This tells the rules loader to use your `rules.md` instead of `.claude/additional/dm-slots/movement.md`. The DM gets your rules in place of the vanilla ones.

---

## Tools (CLI)

Bash wrapper that calls Python. Pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_dir="$SCRIPT_DIR"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"

cd "$PROJECT_ROOT"
uv run python .claude/additional/modules/my-module/lib/my_engine.py "$@"
```

The git-root finder pattern (`while [ ! -d "$_dir/.git" ]`) is mandatory — do NOT use relative `../../..` paths.

---

## Python Modules

```python
from pathlib import Path

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))

from lib.campaign_manager import CampaignManager
from lib.world_graph import WorldGraph
```

Use `PROJECT_ROOT` finder instead of `.parent.parent...` chains. Import CORE modules for data access.

### Available CORE APIs

| Module | Key methods |
|--------|------------|
| `CampaignManager(world_state_dir)` | `get_active_campaign_dir()`, `get_active()` |
| `WorldGraph(campaign_dir)` | Entity CRUD, inventory, player stats, quests, locations, consequences, and `transaction()` |

Modules must treat `world.json` as the only gameplay entity store. Use
`WorldGraph` methods instead of reading or writing `world.json` directly. Group
related mutations in `with graph.transaction():` so they commit together.

---

## rules.md

DM instructions loaded during gameplay. Tells Claude when and how to use your module.

```markdown
# My Module — DM Rules

## When to Call
- After X happens, run: `bash .claude/additional/modules/my-module/tools/dm-my-tool.sh action`

## When NOT to Call
- Don't call when Y

## Display Format
Show data like this in the status bar: ...
```

Loaded by `dm-active-modules-rules.sh` when the module is active.

---

## creation-rules.md

Instructions for `/new-game` world-building phase. Tells Claude how to set up campaign data for your module.

```markdown
# My Module — Creation Rules

## Step 1: Ask the user about X
## Step 2: Write config to campaign-overview.json
## Step 3: Initialize character data
```

Loaded by `dm-active-modules-creation-rules.sh` during campaign creation.

---

## Campaign Data

### Module-specific data (recommended)

Store module config and runtime data in `module-data/<module-id>.json` inside the campaign directory:

```
world-state/campaigns/<campaign>/module-data/
  firearms-combat.json
  my-module.json
```

Use `ModuleDataManager` from infrastructure:

```python
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "infrastructure"))
from module_data import ModuleDataManager

mdm = ModuleDataManager(campaign_dir)
config = mdm.load("my-module")
config["setting"] = "value"
mdm.save("my-module", config)
```

### Per-character data

Store per-character data on the active player node in `world.json`:

```python
graph = WorldGraph(campaign_dir)
with graph.transaction():
    graph.update_node("player:active", {
        "data": {"my_module_data": {"setting": "value"}}
    })
```

---

## Dependencies

If your module requires another:

```json
"dependencies": ["mass-combat"]
```

The system will:
- Block activation if `mass-combat` is not enabled
- Block deactivation of `mass-combat` if your module depends on it

---

## Tests

Use pytest with tmp campaign directories:

```python
import json
import pytest
from pathlib import Path
from lib.world_graph import WorldGraph

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())

def make_campaign(tmp_path, overview, character):
    ws = tmp_path / "world-state"
    campaigns = ws / "campaigns" / "test"
    campaigns.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("test")

    (campaigns / "campaign-overview.json").write_text(json.dumps(overview))
    graph = WorldGraph(campaigns)
    graph.add_node("player:active", "player", character["name"], character)
    return ws

class TestMyModule:
    def test_basic(self, tmp_path):
        ws = make_campaign(tmp_path, {...}, {...})
        # test your module logic
```

Run: `uv run pytest .claude/additional/modules/my-module/tests/ -v`

---

## Installation

Community modules: drop the folder into `.claude/additional/modules/` and run:

```bash
bash .claude/additional/infrastructure/tools/dm-module.sh scan
bash .claude/additional/infrastructure/tools/dm-module.sh list
bash .claude/additional/infrastructure/tools/dm-module.sh activate my-module
```

---

## Checklist

- [ ] `module.json` with all required fields (`id`, `name`, `version`, `description`)
- [ ] `id` matches folder name
- [ ] `rules.md` with DM instructions
- [ ] Middleware exits 1 for unrecognized actions (lets CORE handle them)
- [ ] Middleware handles `--help` (exit 1 after printing)
- [ ] Tools use git-root finder, not relative paths
- [ ] Python uses `next(p for p in Path(__file__).parents if (p / ".git").exists())`
- [ ] Tests pass: `uv run pytest .claude/additional/modules/my-module/tests/ -v`
- [ ] No modifications to `lib/` or `tools/` (CORE stays clean)
