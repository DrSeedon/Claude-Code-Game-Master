# DM System - Multi-client and Developer Rules

> ⛔ **QUIET "LIKE MICE" MODE (2026-11-04 — MANDATORY OWNER RULE):**
> Zero blunders, server overloads, multi-threaded downloads (Yandex.Disk / clouds / archives > 50 MB are strictly FORBIDDEN without explicit owner "yes"), heavy worker swarms, or API limit burn! Work as quietly, carefully, and incrementally as possible (clarified 2026-11-05: do not throttle lightweight agents — a Workflow stage of N parts runs N agents at once; gate heavy runs on our cgroup RAM and pids, not the hub-wide `loadavg`; at most 2 headless Chrome across all our projects; clean up all spawned processes). Do not create or keep any `hub-*` / `Мастер стола` / `AI-стол` hub-master T3 threads on the hub. Full regulations are in `~/agent-rules/global.md`.

This is the core, sent on every turn of every agent. It must stay under 16 384 bytes. Anything needed only sometimes lives in `.orchestra/kb/rules-*.md` (never in `.claude/rules/`, which Claude Code loads in full) and is reached through the registry below.

## What this project is
> **VPS-ONLY CHECKOUT MODE (2026-11-09 — MANDATORY OWNER RULE):**
> By owner order («вынеси все свои проекты с хаба на впс синкуй чтобы на хабе не было ок. но все работало типо если доработки то на впс моем бы работал ок. а треды и так бы работали»), all repository code, `.git`, `.venv`, `build/`, and `world-state/` have been moved off the Multicast hub onto `orchestra-vps` (`158.220.127.161`):
> - **D&D Game Master repo & builds on VPS:** `/home/kesha/projects/dnd-game-master` (`https://github.com/DrSeedon/Claude-Code-Game-Master.git`)
> - **AI-table MVP repo on VPS:** `/home/kesha/projects/ai-table-mvp` (`https://github.com/DrSeedon/ai-table-mvp.git`) and live deploy `/opt/ai-table-i1/app`
> - **What remains in this hub directory (`/mnt/claude-data/astrahancev-maxim-911aird/claude-code-game-master`):** ONLY a lightweight stub (`AGENTS.md`, `CLAUDE.md`, `.orchestra/kb/`, `.agents/skills/`, `skills/`, `ops/ai-table/hub-vps.sh`, `ops/play/hub-vps.sh`) so T3 threads (`AI-стол и D&D-мастер`, `ИИ-стол и живой мастер`, `AI-стол: Северин (хаб-мастер)`) and hub-master SSH bridges work seamlessly. **Never clone or build the project back onto the hub; run all code edits, git operations, and tests directly on `orchestra-vps` via `ssh orchestra-vps`!**

- The D&D DM engine: bash tools `tools/dm-*.sh` over Python in `lib/`, a WorldGraph (`world.json`) per campaign, optional gameplay `modules/`, DM rules in `.claude/additional/dm-slots/`. Played through Claude Code, Codex or Grok Build skills over the same engine.
- The web game master on top of it: FastAPI backend in `backend/`, static frontend in `frontend/`, public at `https://dnd-game-master.duckdns.org` (VPS only).
- The orchestrator for this repository also drives the AI-table MVP in `/home/kesha/projects/ai-table-mvp` (a D&D master for a physical table). Project focus is set by an Orchestra temporary rule (currently: AI-table is the active line with priority on the Live Human GM mode and literal 1:1 concept UI port; this web game master is maintenance-only, fixes for breakage); it is not restated here.

## Project leadership and multi-agent roles (CEO + CTO, owner decision updated 2026-11-09)
- **Gemini 4 Argon (CEO & Chief Product / Art / Game Director — T3 thread `AI-стол и D&D-мастер`, `mcp:559b1d17-1cce-409b-9d5b-72a87c83e315` (T3 thread id; `91e833de-…` is its internal Antigravity id and cannot be addressed)):**
  - Main project boss working directly with the owner (Maxim) on product strategy, game design, table UX, and visual direction across the D&D engine, online tables, and the AI-table MVP.
  - Reviews and approves all screenshots, UI surfaces (`/table`, `/scene`, `/admin`, `/gm` Human-GM console, online play screen), concept slides, and generated art (using Codex `imagegen` (`gpt-image-2`) as priority #1), enforcing 1:1 visual parity with the approved concept deck (`https://sites.aimulticast.org/astrahancev/ai-table-concept/`), dual-side physical table readability, and Gamedesign Bible principles (`/mnt/claude-data/astrahancev-maxim-911aird/multicode/docs/gamedesign-bible/00-шпаргалка.md`).
  - Coordinates tasks and role boundaries with the CTO thread and specialized workers.
- **Claude Opus 5.5 on `xhigh` (CTO & Hands-On Technical Executive — T3 thread `ИИ-стол и живой мастер`, `200c8968-f34c-46df-a255-df2e3e59b653`, `effort: "xhigh"`, updated 2026-11-09 by owner order; `gpt-6.1-sol` is globally disabled):**
  - Owns technical architecture, hands-on code implementation (`lib/`, `tools/`, `modules/`, `backend/`, `frontend/`, and `/home/kesha/projects/ai-table-mvp` on the VPS), VPS infrastructure, and I11 walker end-to-end verification; works directly by hand in its own thread without spawning coding sub-workers.
  - Never sends intermediate step-by-step chat reports via `t3_thread_send` to the CEO thread (writes intermediate state silently to disk and notifies CEO only once when a full wave/milestone is complete with screenshots/artifacts, or on a fatal blocker).
- **Severin AI-Table Voice GM (`AI-стол: Северин (хаб-мастер)`, `mcp:3c45592e-4bb9-4be1-946b-f59f71034110`, `Claude Sonnet 5.5` on `medium`):**
  - Bound to webhook `scheduled-task:23f4d4d5-9db9-4228-959d-67f535f587aa` (`ai-table turn`) for the AI-table voice GM mode.
- **Global hub rules:** always follow `~/agent-rules/global.md` (`~/.claude/rules/global.md` / `~/.codex/AGENTS.md`).

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
