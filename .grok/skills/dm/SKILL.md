---
name: dm
description: >
  Run the repository's local AI Dungeon Master and persistent campaign engine
  inside Grok Build. Use when the user invokes /dm, $dm, /new-game, /dm-continue,
  /dm-save, /dm-mode, /create-character, /import, /enhance, /world-check, /reset,
  /setup, /help, or asks to create, continue, play, inspect, save, switch agency
  mode, or reset a tabletop RPG campaign.
when-to-use: >
  /dm, play campaign, continue adventure, new-game, dungeon master, tabletop RPG,
  save session, world-check, import book as campaign
compatibility: Requires project tools/*.sh, uv, and campaign data under world-state/
---

# DM Game Master (Grok Build)

Operate the existing campaign engine through its shell tools. Do not invent a
parallel state layer.

Shared runtime (do not preload wholesale):

- `.claude/additional/` — rules slots, loaders, narrator styles, templates
- `tools/` — mechanical CLI
- `modules/` — optional genre mechanics
- `codex-skills/dm/references/` — command and specialist playbooks (shared with Codex)
- `codex-skills/dm/scripts/` — session prepare / campaign list helpers

`.claude/commands/*.md` may also appear as legacy slash files. Prefer **this**
skill over those Claude-oriented stubs: Claude hooks do not replace an explicit
session prepare in Grok Build.

## Non-negotiable rules

- Persist every mechanical state change with `tools/*.sh` **before** narrating it.
- Do not edit campaign JSON by hand when a supported tool exists.
- `world.json` is authoritative for entities. `campaign-overview.json` is metadata.
  `campaign-rules.md` is campaign-specific rules.
- During gameplay, `/tmp/dm-rules.md` is authoritative for combat, checks,
  movement, loot, narration, persistence, modules, campaign rules, and style.
- Never reset or delete campaign data without explicit confirmation. Clearing
  chat context is not a world reset.
- Campaign **data** may be Russian. Engine rules, dm-slots, and module definitions
  remain English.
- If `uv` cannot write its home cache: `export UV_CACHE_DIR=/tmp/dm-uv-cache`.
- Read `references/grok-adaptation.md` when a shared reference mentions Claude- or
  Codex-only tools.

## Command router

Slash commands are intent aliases. Read only the matching reference under
`codex-skills/dm/references/commands/`:

| User intent | Reference |
|---|---|
| `/dm`, choose campaign, one-shot | `dm.md` |
| Continue play | `dm-continue.md` |
| Switch narrative/interactive agency | `dm-mode.md` |
| New full campaign | `new-game.md` |
| Create a character | `create-character.md` |
| Import a book or module | `import.md` |
| Save/end session | `dm-save.md` |
| Enhance an entity from RAG | `enhance.md` |
| Validate campaign consistency | `world-check.md` |
| Install/setup | `setup.md` |
| Reset campaign | `reset.md` |
| Help | `help.md` |

The user's explicit subcommand and already supplied answers count as menu
selections. Do not re-ask for information they already gave.

## `/dm` startup

For bare `/dm`:

1. Run `bash codex-skills/dm/scripts/list_campaigns.sh` from the project root.
2. Present saved campaigns plus a final `NEW ADVENTURE` option.
3. Wait for the user's choice unless it was already explicit.
4. Existing campaign → `bash tools/dm-campaign.sh switch <name>`, then continue below.
5. New campaign → read `codex-skills/dm/references/commands/new-game.md` (or import path).

For continuing an existing campaign:

1. Once per session (or after compaction if rules are missing), run from project root:

   ```bash
   export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/dm-uv-cache}"
   bash codex-skills/dm/scripts/prepare_session.sh
   ```

2. Read `/tmp/dm-rules.md` completely before narrating.
3. Internalize prepare output: location, time, player, party, quests, consequences,
   last session, handoff. Do **not** re-run overview/player/plot tools already covered.
4. If handoff location conflicts with current state, treat handoff as truth and
   persist the corrected location with tools.
5. Present the scene using compiled output-format and narrator rules.
6. Obey active `play_mode` / `player-agency` (interactive vs narrative).

Do not reread campaign files already printed by `prepare_session.sh` unless a
concrete mismatch needs investigation.

## Gameplay loop

For every player action:

1. Identify the applicable compiled rule and tool.
2. Declare DC/AC before any required roll.
3. Run the narrowest `tools/dm-*.sh` command. When one beat changes two or more of
   location, party position, time, consequences, or quest objectives, prefer one
   `tools/dm-scene.sh` call.
4. Persist HP, inventory, position, time, NPC memory, quests, facts, consequences
   **before** narration.
5. Narrate per active style and fail-forward rules.
6. Award XP/progression when compiled rules require it.
7. End the turn per agency mode: ask for the next action (interactive) or continue
   to a key decision / chapter break (narrative).

After context compaction: reread `/tmp/dm-rules.md`. If missing, rerun
`prepare_session.sh`.

## Cinematic visuals

When prepared context has `cinematic_visuals.enabled: true` (or the user asks for
major campaign art), read `../cinematic-scene/SKILL.md` and follow it. Use Grok
`image_gen` / `image_edit` — never invent a second image pipeline. Skip routine
turns. If image tools fail, continue play without blocking.

## New campaign

Read `codex-skills/dm/references/commands/new-game.md` and follow its phases.
Create entities only through `tools/dm-*.sh`. Ask compact questions when later
answers depend on earlier ones. Prefer `ask_user_question` for short numbered
menus when it is clearer than free prose.

## Specialists

Specialists are reference playbooks, not permanent workers. Read only what you
need under `codex-skills/dm/references/specialists/`. Execute locally by default.
Spawn a subagent only for genuinely independent parallel work; validate and import
results yourself.

## Workflows

- First scene for a new character: `codex-skills/dm/references/workflows/class-intros.md`
- How much world detail to materialize: `.../workflows/cognitive-rendering.md`
- Claude/Codex wording in copied refs: `references/grok-adaptation.md` and
  `codex-skills/dm/references/codex-adaptation.md`

Do not preload every command and specialist file. Keep context small.

## Development vs play

If the user is coding, reviewing, or refactoring this repo, do **not** enter DM
mode unless they clearly want to play. Developer rules live in root `AGENTS.md`.
