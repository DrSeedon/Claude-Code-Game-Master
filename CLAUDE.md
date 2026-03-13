# DM System - Developer Rules

## Stack
- Python via `uv run python` (never `python3`)
- Bash wrappers in `tools/` → Python modules in `lib/`
- Tests: `uv run pytest`

## Architecture
- `lib/` — upstream CORE only. No custom features.
- `tools/` — thin bash wrappers + `dispatch_middleware` for module hooks
- `.claude/additional/modules/` — self-contained gameplay modules (with module.json)
- `.claude/additional/dm-slots/` — vanilla DM rules (27 slot files, loaded in advanced mode only)
- `.claude/additional/infrastructure/` — advanced mode loaders (dm-active-modules-rules.sh, dm-campaign-rules.sh, dm-narrator.sh)
- `.claude/additional/campaign-rules-templates/` — campaign rule templates
- `.claude/additional/narrator-styles/` — narrator style definitions

## Two gameplay modes
- **Vanilla** (`/dm`): loads dm-slots via `dm-active-modules-rules.sh` → `/tmp/dm-rules.md` (pure vanilla slots, no module replacements)
- **Advanced** (`/dm-continue`): loads dm-slots + module rules via `dm-active-modules-rules.sh` → `/tmp/dm-rules.md`, campaign rules via `dm-campaign-rules.sh`, narrator styles. Activated when `campaign-overview.json` has `"advanced_mode": true`

## Module pattern
Each module in `.claude/additional/modules/<name>/`:
- `middleware/<tool>.sh` — intercepts CORE tool calls, handles `--help`
- `lib/` — module Python code
- `tools/` — module-specific CLI
- `module.json` — metadata

## Dev commands
```bash
uv run pytest                                              # run all tests
bash .claude/additional/infrastructure/tools/dm-module.sh list # list active modules
git diff upstream/main -- lib/                              # check CORE purity
```

## Rules
- CORE tools delegate to modules via `dispatch_middleware "tool.sh" "$ACTION" "$@" && exit $?`
- `lib/` diff from upstream: only `ensure_ascii=False`, `require_active_campaign`, `name=None` auto-detect
- Never add features to `lib/` — put them in modules
- `/dm` vanilla: no external rules loaded. `/dm-continue` advanced: loads `.claude/additional/dm-slots/*.md` + module rules via `dm-active-modules-rules.sh`

## Post-compaction recovery
After context compaction, ALWAYS reload all DM rules before continuing gameplay:
```bash
# Load all active module rules
bash .claude/additional/infrastructure/dm-active-modules-rules.sh --modules-only | cat

# Load campaign rules
bash .claude/additional/infrastructure/dm-campaign-rules.sh | cat
```
This ensures module-specific rules (inventory usage, combat mechanics, custom stats, etc.) are fresh in context and not forgotten after compaction.
