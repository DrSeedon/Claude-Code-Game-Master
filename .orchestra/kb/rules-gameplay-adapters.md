# Gameplay adapters and campaign migration

Moved verbatim from the root AGENTS.md on 2026-10-17 (task V-47, owner's rules-structure decision). Edit here when a rule changes.

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

Codex discovers the DM and cinematic skills through `.agents/skills/` symlinks
to `codex-skills/`. Native `UserPromptSubmit` hooks in `.codex/hooks.json`
reuse the shared Claude context loaders for DM startup commands. Read the
complete compiled `/tmp/dm-rules.md` before play; keep explicit session
registration in `prepare_session.sh` so hooks do not start extra sessions.

### Campaign migration after engine upgrades

- Empty inventory / Gold 0 / firearms "weapon not found" on an old campaign is often
  **half-graph** (graph exists, gear still in `module-data/inventory-system.json`).
- Grok skill: `.grok/skills/dm-migrate-campaign/SKILL.md`
- Post-mortem: `docs/migration/half-graph-postmortem.md`
- Tool: `uv run python tools/migrate_half_graph_campaign.py <name>`
- Flat-file → graph remains `bash tools/dm-migrate-worldgraph.sh <name>` (different case).
