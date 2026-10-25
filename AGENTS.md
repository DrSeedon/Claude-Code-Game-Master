# DM System - Multi-client and Developer Rules

This is the core, sent on every turn of every agent. It must stay under 16 384 bytes. Anything needed only sometimes lives in `.orchestra/kb/rules-*.md` (never in `.claude/rules/`, which Claude Code loads in full) and is reached through the registry below.

## What this project is
- The D&D DM engine: bash tools `tools/dm-*.sh` over Python in `lib/`, a WorldGraph (`world.json`) per campaign, optional gameplay `modules/`, DM rules in `.claude/additional/dm-slots/`. Played through Claude Code, Codex or Grok Build skills over the same engine.
- The web game master on top of it: FastAPI backend in `backend/`, static frontend in `frontend/`, public at `https://dnd-game-master.duckdns.org` (VPS only).
- The orchestrator for this repository also drives the AI-table MVP in `/home/kesha/projects/ai-table-mvp` (a D&D master for a physical table). Project focus is set by an Orchestra temporary rule (currently: AI-table is the active line, this web game master is maintenance-only, fixes for breakage); it is not restated here.

## Stack and tests
- Python via `uv run python` (never `python3`) — in the repo since the initial commit (2026-02-08).
- Bash wrappers in `tools/` → Python modules in `lib/`. All tools route through `lib/world_graph.py`; `dm-world.sh` is the unified CLI and the older `dm-*.sh` tools are thin wrappers over it (2026-03-28, WorldGraph unification).
- Tests: `uv run pytest`. After lib/ or tools/ changes run the whole suite; after dm-slots or module rules edits verify English-only; after JSON schema changes run the affected tool with `--help`; after module middleware changes test the intercepted action end to end.
- Active modules: `bash .claude/additional/infrastructure/tools/dm-module.sh list`.

## Architecture
- `lib/` — CORE Python: dice, player, session, inventory, currency, NPCs, locations, plots, consequences, notes
- `tools/` — thin bash wrappers + `dispatch_middleware` for module hooks
- `modules/` — optional gameplay modules (custom-stats, world-travel, mass-combat, firearms-combat)
- `.claude/additional/dm-slots/` — DM rules (loaded into `/tmp/dm-rules.md`)
- `.claude/additional/infrastructure/` — loaders (dm-active-modules-rules.sh, dm-campaign-rules.sh, dm-narrator.sh)
- `.claude/additional/campaign-rules-templates/` and `narrator-styles/` — campaign rule templates and narrator style definitions
- Web app: `backend/server.py` (HTTP and WebSocket), `backend/game_session.py` (turn lifecycle), `backend/providers/claude_sdk.py` (Claude CLI), `frontend/js/app.js`.

## Always-applicable rules
- **LANGUAGE POLICY (MANDATORY, NO EXCEPTIONS):** ALL rules files (dm-slots, module rules, AGENTS.md, module.json) MUST be written entirely in English — every sentence, every example, every table cell. Campaign DATA (NPC names, location names, fact content, session logs) can be in any language. (2026-03-27, English-only rules cleanup.)
- **Modules MUST be campaign-agnostic.** This is a public repo used by multiple campaigns. Never add campaign-specific content (character names, spell names, setting-specific rules, faction names) to module code, module rules or dm-slots; campaign-specific rules belong in that campaign's `campaign-rules.md`. A module MUST NOT import, inspect, or name another gameplay module; CORE composes capabilities through `provides`, `providers`, `action_routes` (2026-03-27 and 2026-07-19, module system).
- **Bugs and errors go to `TODO.md` the moment they are found**, not at the end of the answer: what broke, where (file/function), the triggering case, the fix direction (owner order, 2026-10-25, War and Peace import).
- Gameplay rules live in `.claude/additional/dm-slots/`, loaded into `/tmp/dm-rules.md`. Edit THOSE files for gameplay changes, not this file; this file is dev-only.
- **Never restart Orchestra on the VPS yourself** — it interrupts active turns across projects; the Orchestra orchestrator owns that restart (2026-08-03, VPS migration notes).
- **No secrets in tracked files.** This is a public repository: never put a password, token or key in it (site password `DND_AUTH_PASSWORD` and `.duckdns_token` stay outside Git; password removed from the repo 2026-09-19). Live `world-state/campaigns`, `world-state/usage` and `.env` exist only on the VPS: never `git clean` or reclone over them without a backup.
- Do not restore `https://dnd.seedon.ru` (removed 2026-08-07: the domain belongs to a company that needed to drop the German-server association). DuckDNS: touch only `dnd-game-master` (and `dnd-table` for AI-table), always passing the domain explicitly.
- Do not set the Claude SDK `allowed_tools` option: under `bypassPermissions` it blocked Bash tools in wizard and game mode (measured 2026-07-20).
- Report problems as they happen, not at the finish line; fixing the same defect shape twice is a signal to escalate to the owner, not to fix it a third time (2026-08-19, concealed tactical-map tokens: four review rounds, then the feature was cut in one message). Ask the owner only about scope-defining, expensive or hard-to-reverse choices (2026-08-16).

## Rules file
There is one project rules content source: this root `AGENTS.md`; root `CLAUDE.md` is a relative symlink to it. Orchestra Claude workers use the system Claude CLI via `cli_path=shutil.which("claude")` (2.1.293 as of 2026-10-08), which reads `AGENTS.md` alone (source: Orchestra KB `.orchestra/kb/agent-control.md`, 2026-10-08); Codex reads `AGENTS.md` too. On 2026-10-07, the system Claude Code 2.1.284 on the VPS read both files because the user-wide `~/.claude/mods/agents-md` mod enables `instructionFiles=claude-md-and-agents-md` (installed 2026-09-20). Keep the symlink so clients that read only `CLAUDE.md` receive the same rules. Do not remove it or replace it with a second independent rules file.


## Registry: topic → file → when to read
Read the file before touching its topic; extend it when a rule changes. Owner-decision entries there are verbatim, with dates and quotes — never paraphrase a quote.
- Gameplay adapters (Claude / Codex / Grok Build skill entries), campaign migration after engine upgrades, half-graph → `.orchestra/kb/rules-gameplay-adapters.md` → when a `/dm` command is invoked, a campaign is created/continued/migrated, or a client skill is edited.
- CORE tools table, calendar, currency, module pattern, WorldGraph data model, slots, post-compaction recovery → `.orchestra/kb/rules-engine.md` → when changing `lib/`, `tools/`, `modules/` or campaign data, or after context compaction during play.
- Verification method (mutation checks, forged old data, pre-fix rig, comparing failures) → `.orchestra/kb/rules-verification.md` → when writing or accepting tests, or proving a fix.
- Deploy, DuckDNS, nginx, VPS clone, sudo/ssh path, orchestrator migration → `.orchestra/kb/rules-deploy-vps.md` → before any deploy, domain, VPS or service operation.
- Selectable models, bundled-CLI trap, web app map, wizard/SDK integration, web security → `.orchestra/kb/rules-web-app.md` → when changing `backend/`, `frontend/`, the wizard or model selection.
- AI-table execution topology and every dated owner decision about it (autonomy, fight feel, difficulty, addresses, live GM, game UI, GM narration) → `.orchestra/kb/rules-ai-table.md` → when working on or for the AI-table MVP.
