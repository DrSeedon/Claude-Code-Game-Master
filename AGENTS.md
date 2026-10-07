# DM System - Multi-client and Developer Rules

## Gameplay adapters (Claude / Codex / Grok Build)

Play uses the same engine (`tools/*.sh`, WorldGraph, `.claude/additional/` rules).
Each client only needs a thin skill adapter — never a second state store.

| Client | Play skill entry | Notes |
|---|---|---|
| **Grok Build** | `.grok/skills/dm/SKILL.md` | Prefer this over legacy `.claude/commands/*`. Explicit `prepare_session.sh`; map tools via `.grok/skills/dm/references/grok-adaptation.md`. Cinematic: `.grok/skills/cinematic-scene/SKILL.md` → Grok `image_gen`. |
| **Codex** | `codex-skills/dm/SKILL.md` | Same scripts/references. Cinematic: `codex-skills/cinematic-scene/SKILL.md`. |
| **Claude Code** | `.claude/commands/` + UserPromptSubmit hooks | Hooks compile `/tmp/dm-rules.md` per prompt. |

Shared (do not duplicate under client skill trees):

- `.claude/additional/` — rules slots, loaders, narrator styles, templates
- `modules/` — optional genre mechanics
- `codex-skills/dm/scripts/` — `prepare_session.sh`, `list_campaigns.sh` (used by Codex and Grok)
- `codex-skills/dm/references/` — command and specialist playbooks (used by Codex and Grok)

When the user invokes `/dm`, `$dm`, another DM slash command, or asks to create,
continue, play, inspect, save, switch agency mode, or reset a campaign:

1. Activate the **client-appropriate** DM skill above (in Grok Build: `.grok/skills/dm`).
2. Load command and specialist references **progressively**. Never inject the entire `.claude/` tree.
3. For ordinary development tasks, follow the developer rules below **without** entering DM play mode.

Treat `/dm` as an alias for `$dm` even when the host has no native slash registration.

### Campaign migration after engine upgrades

- Empty inventory / Gold 0 / firearms "weapon not found" on an old campaign is often
  **half-graph** (graph exists, gear still in `module-data/inventory-system.json`).
- Grok skill: `.grok/skills/dm-migrate-campaign/SKILL.md`
- Post-mortem: `docs/migration/half-graph-postmortem.md`
- Tool: `uv run python tools/migrate_half_graph_campaign.py <name>`
- Flat-file → graph remains `bash tools/dm-migrate-worldgraph.sh <name>` (different case).

## Stack
- Python via `uv run python` (never `python3`)
- Bash wrappers in `tools/` → Python modules in `lib/`
- Tests: `uv run pytest`

## Architecture
- `lib/` — CORE Python: dice, player, session, inventory, currency, NPCs, locations, plots, consequences, notes
- `tools/` — thin bash wrappers + `dispatch_middleware` for module hooks
- `modules/` — optional gameplay modules (custom-stats, world-travel, mass-combat, firearms-combat)
- `.claude/additional/dm-slots/` — DM rules (loaded into `/tmp/dm-rules.md`)
- `.claude/additional/infrastructure/` — loaders (dm-active-modules-rules.sh, dm-campaign-rules.sh, dm-narrator.sh)
- `.claude/additional/campaign-rules-templates/` — campaign rule templates
- `.claude/additional/narrator-styles/` — narrator style definitions

## CORE tools (always available)
| Tool | Lib | Purpose |
|------|-----|---------|
| `dm-roll.sh` | `dice.py` | Dice with `--label`, `--dc`, `--ac`. Auto-lookup: `--skill "name"`, `--save "name"`, `--attack "weapon"`, `--initiative "name" ...`, `--advantage`, `--disadvantage`. Reads entities from world.json. Auto-combat: `--target "creature"` (player attacks, AC from world.json), `--defend --from "creature"` (creature attacks, stats from world.json). Auto-damage on hit. |
| `dm-inventory.sh` | `inventory_manager.py` | Items, weight, gold, HP/XP, transfers, `remove` (sold/destroyed/consumed), `use` (auto-consume via wiki), `craft` (auto-craft via wiki recipe). Always use `--qty N`, never call multiple times. |
| `dm-status.sh` | `inventory_manager.py status` | Compact inventory for session start |
| `dm-player.sh` | `player_manager.py` | XP, HP, HP max, gold, conditions |
| `dm-session.sh` | `session_manager.py` | Start/end, move (`--elapsed N`), save/restore |
| `dm-npc.sh` | `npc_manager.py` | NPCs, party, attitudes |
| `dm-location.sh` | `location_manager.py` | Locations, connections |
| `dm-note.sh` | `note_manager.py` | World facts |
| `dm-plot.sh` | `plot_manager.py` | Quests, objectives |
| `dm-consequence.sh` | `consequence_manager.py` | Timed events |
| `dm-time.sh` | `time_manager.py` | Game clock. Usage: `dm-time.sh "<time>" "<date>" --elapsed N [--sleeping]`. Positional args required. |
| `dm-campaign.sh` | `campaign_manager.py` | Campaign management |
| `dm-mode.sh` | `campaign_mode.py` | Persistent narrative/interactive player-agency mode |
| `dm-wiki.sh` | `wiki_manager.py` | Structured knowledge base: items, recipes, abilities, materials |
| `dm-condition.sh` | `player_manager.py` | Condition management (add/remove/check) — wrapper for dm-player.sh condition |
| `dm-search.sh` | `entity_enhancer.py` | Hybrid world-state + RAG search for scenes and entities |
| `dm-overview.sh` | — | World state overview (NPCs, locations, facts, consequences) |
| `dm-enhance.sh` | `entity_enhancer.py` | RAG entity enhancement — auto-runs on dm-session.sh move |

## Calendar system
- `lib/calendar.py` — universal, configurable per campaign
- Config in `campaign-overview.json` → `"calendar"` section (months, weekdays, epoch)
- Used by `time_manager.py` for date display and weekday calculation

## Currency system
- `lib/currency.py` — universal, configurable per campaign
- Config in `campaign-overview.json` → `"currency"` section
- Stored as single int in base units (copper for D&D)
- `format_money(2537)` → `"25g 3s 7c"`, `parse_money("2gp 5sp")` → `250`

## Module pattern (for optional modules)
Each module in `modules/<name>/`:
- `middleware/<tool>.sh` — intercepts CORE tool calls (pre-hook: exit 0 = handled)
- `middleware/<tool>.sh.post` — runs after CORE (post-hook: always runs)
- `lib/` — module Python code
- `tools/` — module-specific CLI
- `module.json` — metadata, replaces dm-slots

Modules declare neutral `provides`, `providers`, and `action_routes` contracts in
`module.json`. A module MUST NOT import, inspect, or name another gameplay
module. CORE composes active capabilities and resolved DM rules.

**Modules MUST be campaign-agnostic (MANDATORY).** This is a public repo used by multiple campaigns. NEVER add campaign-specific content (character names, spell names, setting-specific rules, faction names) to module code, module rules, or dm-slots. Campaign-specific rules belong in `campaign-rules.md` for that campaign only.

## Dev commands
```bash
uv run pytest                                              # run all tests
bash .claude/additional/infrastructure/tools/dm-module.sh list # list active modules
```

## Data Architecture — WorldGraph
- **`world.json`** — unified entity graph. ALL game data: player, NPCs, locations, items, creatures, facts, quests, consequences, spells, economy. One file per campaign.
- **`campaign-overview.json`** — metadata only: time, date, calendar, modules, narrator style, genre, tone.
- **`campaign-rules.md`** — per-campaign rules.
- Custom stats, inventory, wiki — all stored as nodes in `world.json`.
- `dm-time.sh --elapsed` auto-ticks via WorldGraph: custom stats decay, recurring expenses/income, production, consequences, random events.
- Move + time: `dm-session.sh move "Location" --elapsed 0.5` combines move and time advance in one call.

## Rules
- **LANGUAGE POLICY (MANDATORY, NO EXCEPTIONS):** ALL rules files (dm-slots, module rules, AGENTS.md, module.json) MUST be written entirely in English — every sentence, every example, every table cell. Campaign DATA (NPC names, location names, fact content, session logs) can be in any language.
- All tools route through `lib/world_graph.py` for data operations.
- `dm-world.sh` is the unified CLI — all old tools (dm-npc.sh, dm-location.sh, etc.) are thin wrappers over it.

## DM Gameplay Rules
All gameplay rules (combat, movement, narration, loot, social, time management, state persistence) live in `.claude/additional/dm-slots/`. These are loaded at session start into `/tmp/dm-rules.md`. Edit THOSE files for gameplay changes, not this file. This file is dev-only.

## Verification
- After lib/ or tools/ changes: `uv run pytest`
- After dm-slots or module rules edits: verify English-only (no Russian text in rules files)
- After JSON schema changes: run affected tool with `--help` to verify it still parses
- After module middleware changes: test the intercepted action end-to-end
- Prove a fix is load-bearing by deleting the element entirely (name and body) and repairing call sites, then mutate each part separately. Replacing a body with `pass` leaves name-based references alive and can falsely suggest the code is unused. Check where a mutant goes red: an upstream guard proves the guard, not the assertion under test. Measured 2026-08-19: deleting a round-trip field made a strict decoder raise `KeyError` before the comparison; changing the decoder to silently disagree with its source stayed green. Mutate toward a wrong value, not a missing one.
- Restore mutants with `trap ... EXIT`, never a later command in the same run: a timeout can leave the mutant on disk. Measured 2026-08-19: a 120-second default killed a 128-second suite during mutation. Name the test each mutant reddened; several mutants reddening one catch-all test prove one property repeatedly, not several properties.
- **A test that re-implements the check it verifies stays green while the real path is broken.** Measured 2026-08-18: breaking surface-to-capability mapping left a probe-double suite green and was caught only by a test driving a real server over a real socket. Cover authorization and authority seams through the actual entry path.
- **Every test passes on an empty store; upgrades break existing data.** Changes shipping where data already exists need an acceptance check against a forged pre-change record, not only a fresh one. Measured 2026-08-19: the first tactical-map deploy served three blank pages because the live room held a projection from the previous version. `world-state/campaigns` contains live campaigns that exist only on the VPS. A record can also be stale in meaning rather than presence: compare stored values with freshly computed ones. A presence-only repair missed an old projection that hid an entity the validator rejected moves onto. When a comment describes an event but the predicate checks a standing state property, attack from boot state, where the predicate may already be true without the event. Measured 2026-08-19: a concealed creature was served at revision 0 because the event path made the predicate true as a side effect.
- **A fix's own regression is invisible when testing only the fixed code.** Run the same attack against a rig at the pre-fix commit; inspect the branch the fix newly disables. Measured 2026-08-19: a maintenance-boot session guard made a never-authenticated session permanent, visible only against the older binary.
- **Comparing two failures proves nothing.** Assert each value is present and not its failure default before comparing. Measured 2026-08-19: four assertions compared unauthorized responses, including two that compared the same `{"code":"unauthorized"}` result because a browser could not send the required `Origin` header. Ask what each assertion sees when the code is broken.

## Slot System
All dm-slots files are replaceable by modules. Each slot has a `<!-- slot:name -->` marker. Modules declare `"replaces": ["slot-name"]` in module.json to override a slot. The loader (`dm-active-modules-rules.sh`) skips replaced slots and loads module rules instead.

## Post-compaction recovery
After context compaction, reload `/tmp/dm-rules.md` before continuing gameplay. In Claude Code,
the `UserPromptSubmit` hook compiles it for each prompt; in Codex, the DM skill compiles it during
session preparation. If it is missing, recompile:
```bash
bash .claude/additional/infrastructure/dm-active-modules-rules.sh > /tmp/dm-rules.md 2>/dev/null
```
Then read `/tmp/dm-rules.md`.

## Product decision interviews
- Ask the owner only about scope-defining, expensive, or hard-to-reverse choices. Decide reversible UI mechanics, such as drag versus tap or token presentation, within the implementation team.
- **Fixing the same defect shape twice is a signal to escalate, not to fix it a third time.** Tell the owner what keeps breaking, what it costs, and the options, including deleting the feature. Measured 2026-08-19: four review rounds and five blocking defects went into securing concealed tokens on the tactical map; the owner asked why anything was being hidden, and the feature was cut in one message. Reporting the repeated pattern after round two would have avoided those rounds. A repeated defect class may indicate a wrong requirement; the owner decides whether to keep it.
- **Report problems as they happen, not at the finish line.** Silence reads as progress. When work stalls, repeats, or reaches a decision outside the team's authority, report the concrete options and a recommendation in the same turn.

## Deployment and VPS operations

### Deploy
- The public site is `https://dnd-game-master.duckdns.org`; the service is `dnd-game-master.service`. Its site password is held only in the VPS `.env` as `DND_AUTH_PASSWORD`. This is a public repository: never put a password, token, or key in a tracked file.
- Do not restore `https://dnd.seedon.ru`: it was removed on 2026-08-07 because the domain belongs to a company that needed to remove the German-server association; the name now resolves through that company's Moscow wildcard.
- The DuckDNS account token is account-wide. This project may update only `dnd-game-master`; `dnd-table` belongs to the AI-table project and is the only other permitted name. Always pass the intended domain explicitly; never iterate over account domains.
- A wildcard can answer for names that were never configured. Probe with a deliberately nonexistent name and compare results: matching responses can come from the wildcard rather than the intended virtual host. A `404` or `200` from that wildcard probe says nothing about the target host.
- **A `200` is transport, not meaning.** DuckDNS can return HTTP 200 with body `KO` for a revoked token. Compare the response body with the expected value and test the failure branch with a deliberately wrong value; `curl -f` alone is insufficient.
- Deploy by pushing to `origin/main`, then pulling with `git pull --ff-only` in the VPS clone. The VPS pulls from GitHub, not from a developer machine. Do not use rsync: the VPS is a real Git clone. Run Git as `kesha`, never root; root-owned files break writes under the service user. `su -s /bin/bash kesha` works; `su - kesha` hangs in the configured environment. Check ownership before deploy with `find /home/kesha/projects/dnd-game-master ! -user kesha`.
- Live `world-state/campaigns`, `world-state/usage`, and `.env` are not in Git and exist only on the VPS. Never run `git clean` or reclone over them without a backup. Do not treat an empty Git directory as evidence that live data is absent.
- `sudo` from an agent process fails because `orchestra.service` sets `NoNewPrivileges=yes`. A fresh SSH process to `kesha@localhost` leaves that unit and can use kesha's configured NOPASSWD sudo: `ssh kesha@localhost 'sudo ...'`. Check the actual remote operation and its result.
- The DuckDNS token file is `.duckdns_token` in the project directory, gitignored; do not print or copy its contents. The keep-alive job may repoint DNS after an address change. A denied `crontab -l` under `NoNewPrivileges` means cron state is unknown, not absent.
- The service listens on port `18083`; a direct proxy is not needed for the current VPS deployment. Tell the owner before a production install.

### Orchestrator on the VPS
- The project orchestrator runs on the VPS. Read `docs/vps-handoff.md` before migration or handoff; it preserves the migration state and environment-specific traps.
- Use Orchestra's `scripts/migrate_agent.py` to migrate a session with its transcript, logs, inbox, and worktrees. Do not hand-write database `INSERT` or `UPDATE` statements: the live server keeps session state in memory and `save_session()` supplies defaults. The migration tool uses an upsert and its idle check prevents the orchestrator from migrating itself; an external actor must launch it.
- Never restart Orchestra on the VPS yourself. It interrupts active turns across projects; the Orchestra orchestrator owns that restart.
- MCP servers are per-session in the `mcp_servers_custom` database column, not in `~/.claude.json`. Orchestra MCP is injected automatically. Ask the Orchestra orchestrator to provision other servers.
- The dashboard's internal port is firewalled; use the configured public dashboard hostname externally or loopback on the VPS.
- Skills copied from a laptop may contain `/mnt/data/...` paths. Search for those paths before trusting a copied skill and replace machine-specific paths with a configurable environment variable and a suitable default.
- A configured MCP entry proves nothing about the executable: verify that the binary exists and invoke it. A server-wide `mcp-pandoc` entry once existed while `pandoc` was missing.

## Models and Claude CLI
- Selectable Claude models are defined in `backend/runtime/registry.py`: Sonnet 5, Sonnet 5.5, Opus 5, Opus 5.5, and Fable 5.1. The default remains `claude-sonnet-5`. Per-turn usage and model prices are in `backend/usage_log.py`; usage is persisted in `world-state/usage/game-turns.jsonl` and exposed by `GET /api/usage`.
- **`claude-agent-sdk` ships a Claude Code CLI inside its wheel and may select it before the system CLI.** That bundled CLI is frozen at the SDK release date and can reject a newer model while the system CLI supports it. Measured 2026-09-18: bundled 2.1.191 rejected `claude-fable-5-1`, while system CLI 2.1.263 ran it. `ClaudeSDKProvider` passes `options.cli_path = shutil.which("claude")`; keep this selection.

## Web application map
```text
Browser → nginx/TLS → FastAPI (`backend/server.py`)
  /ws/game   → GameSession registry → ClaudeSDKProvider → Claude CLI
  /ws/wizard → ephemeral provider + WizardMCP UI tools + dm-*.sh tools
  /api/*     → campaign, status, model, and health endpoints
  /          → static frontend
```

Important files: `backend/server.py` (HTTP and WebSocket routes); `backend/game_session.py`
(session registry and turn lifecycle); `backend/live_broker.py` (pub/sub); `backend/event_log.py`
(append-only log); `backend/providers/claude_sdk.py` (SDK and streaming); `backend/claude_dm.py`
(prompt assembly); `backend/wizard_mcp.py` and `backend/wizard_prompt.py` (wizard); `backend/auth.py`
(cookie authentication); `backend/config.py` (environment configuration); `backend/campaign_api.py`
(campaign endpoints); `backend/usage_log.py` (turn usage); `frontend/js/app.js` (client application).

## Wizard and SDK integration
- The wizard creates campaign data through CLI tools (`dm-campaign.sh`, `dm-location.sh`, `dm-npc.sh`, `dm-plot.sh`, `dm-player.sh`), not a JSON blueprint. Wizard MCP has exactly three UI tools: `show_choices`, `clear_choices`, and `wizard_complete`. `pendingWizardMsg` queues a message sent while generation is in progress and sends it when generation completes.
- Do not set the Claude SDK `allowed_tools` option. Under `bypassPermissions`, the tools are already permitted; the old allowlist blocked Bash tools in both wizard and game mode (measured 2026-07-20).

## Web application security rules
- Campaign names are validated against path traversal such as `../`; session IDs must match `^[A-Za-z0-9_-]{1,64}$`.
- `bypassPermissions` is acceptable only for this password-protected site. Authentication middleware skips only `/auth/*` and static assets.

## Rules file
There is one project rules content source: this root `AGENTS.md`; root `CLAUDE.md` is a relative symlink to it. Orchestra Claude workers use the CLI bundled in `claude-agent-sdk` 2.1.205, which reads `CLAUDE.md` but not `AGENTS.md` alone; Codex reads `AGENTS.md`. On 2026-10-07, the system Claude Code 2.1.284 on the VPS read both files because the user-wide `~/.claude/mods/agents-md` mod enables `instructionFiles=claude-md-and-agents-md` (installed 2026-09-20). Keep the symlink so every client receives the same rules. Do not remove it or replace it with a second independent rules file.

## Current workers
- `dnd-backend` — persistent worker for the game backend.
- `ai-table-worker` — worker for the AI-table project.

## AI-table execution
- The AI-table orchestrator drives tickets sequentially: independent oracle, implementation, tests, merge, then acceptance. Delegate closed mechanical work and independent red oracles; use a full-cycle worker for open research, architecture, or complex implementation.
- **Owner decision, 2026-10-07 (supersedes the 2026-08-17 per-ticket owner checkpoint).** Translated from the owner's voice message: "While we have limits, keep working. Finish all the work fully yourself. Don't ask me about the tickets any more — the tickets go one after another on your side, you check everything, everything works properly." Prompted by the AI-table line sitting silently for 45 days on I3 waiting for a gate nobody was driving. Rule: the orchestrator approves phase gates and moves to the next ticket itself; ask the owner only about irreversible or out-of-project steps such as external repository access, new spending, or data deletion.
- **Owner decision, 2026-10-07 22:07 (project focus).** Translated from his voice message: "Now we focus on one project — the commercial project with Lyosha. Only that one for now: the D&D master for a physical table." Rule: the AI-table MVP (`/home/kesha/projects/ai-table-mvp`, tasks #5, #19–#29) is the only active line; the web game master in this repository is in maintenance — no new features, only fixes for breakage.
- AI-table I0 is local-only in `/home/kesha/projects/ai-table-mvp`; do not add a remote, organization, or external access. Remote visibility, organization ownership, branch protection, an off-provider mirror, and remote-principal proof are fail-closed gates before external sharing. I1 is the first browser checkpoint and must expose `/table`, `/scene`, and `/admin`.
