---
name: dm
description: Run the repository's local AI Dungeon Master and persistent campaign engine. Use when the user invokes /dm, $dm, /new-game, /dm-continue, /dm-save, /dm-mode, /create-character, /import, /enhance, /world-check, or asks to create, continue, play, inspect, save, switch agency mode, or reset a tabletop RPG campaign.
---

# DM Game Master

Operate the existing campaign engine through its shell tools. Treat `.claude/additional/` as runtime data shared by Claude and Codex, not as instructions to preload wholesale.

## Non-negotiable rules

- Persist every mechanical state change before narrating it.
- Use `tools/*.sh`; do not edit campaign JSON directly when a supported tool exists.
- `world.json` is authoritative for current entities. `campaign-overview.json` is metadata. `campaign-rules.md` contains campaign-specific rules.
- During gameplay, `/tmp/dm-rules.md` is authoritative for combat, checks, movement, loot, narration, persistence, modules, campaign rules, and narrator style.
- Never reset or delete campaign data without explicit confirmation. Resetting conversation context is not the same as resetting world state.
- Campaign data may be Russian. Engine rules and module definitions remain English.
- When `uv` cannot write to its home cache, set `UV_CACHE_DIR=/tmp/dm-uv-cache`.

## Command router

Treat slash commands as aliases even though Codex does not register them as native slash commands. Read only the matching reference:

| User intent | Reference |
|---|---|
| `/dm`, choose campaign, one-shot | `references/commands/dm.md` |
| Continue play | `references/commands/dm-continue.md` |
| Switch narrative/interactive agency mode | `references/commands/dm-mode.md` |
| New full campaign | `references/commands/new-game.md` |
| Create a character | `references/commands/create-character.md` |
| Import a book or module | `references/commands/import.md` |
| Save/end session | `references/commands/dm-save.md` |
| Enhance an entity from RAG | `references/commands/enhance.md` |
| Validate campaign consistency | `references/commands/world-check.md` |
| Install/setup | `references/commands/setup.md` |
| Reset campaign | `references/commands/reset.md` |
| Help | `references/commands/help.md` |

The user's explicit subcommand and already supplied answers count as menu selections. Do not ask them to repeat information merely to reproduce a menu.

## `/dm` startup

For bare `/dm`:

1. Run `scripts/list_campaigns.sh`.
2. Present saved campaigns plus a final `NEW ADVENTURE` option.
3. Wait for the user's choice unless it was already explicit.
4. For an existing campaign, switch with `tools/dm-campaign.sh switch <name>` and continue below.
5. For a new campaign, read `references/commands/new-game.md` or the requested import/one-shot reference path.

For continuing an existing campaign:

1. Run `scripts/prepare_session.sh` once.
2. Read `/tmp/dm-rules.md` completely before narrating.
3. Internalize the script output: location, time, player, party, active quests, consequences, last session, and handoff.
4. If the handoff location conflicts with current state, treat the handoff as truth and persist the corrected location.
5. Present the scene using the compiled output-format and narrator rules.

Read the active `play_mode` from the prepared campaign context and obey the compiled `player-agency` slot. Do not assume interactive control when narrative mode is active.

Do not reread campaign files already included in `prepare_session.sh` output unless a concrete mismatch requires investigation.

## Cinematic visuals

When the prepared campaign context has `cinematic_visuals.enabled: true`, read `../cinematic-scene/SKILL.md` once and follow it for major visual beats. Use the available raster image-generation tool; do not generate routine illustrations. The image skill's spoiler, continuity, composition, frequency, and final-action rules are mandatory.

If image generation is unavailable, continue gameplay normally without treating visuals as a blocker.

## Gameplay loop

For every player action:

1. Identify the applicable compiled rule and tool.
2. Declare DC/AC before any required roll.
3. Execute the narrowest tool command. When one narrative beat changes two or more of location, party position, time, consequences, or quest objectives, use one `tools/dm-scene.sh` call instead of separate domain commands.
4. Persist HP, inventory, position, time, NPC memory, quest state, facts, and consequences before narration.
5. Narrate the outcome according to the active style and fail-forward rules.
6. Award XP or progression when the compiled rules require it.
7. End according to the compiled `player-agency` mode: ask for the next action in interactive mode; continue to a key decision or chapter break in narrative mode.

After context compaction, reread `/tmp/dm-rules.md`. If it is missing, rerun `scripts/prepare_session.sh`.

## New campaign

Read `references/commands/new-game.md` and follow its phases in order. The required sequence is:

1. Campaign name and collision check.
2. Create and activate the campaign.
3. Select modules and load their creation rules.
4. Select narrator style.
5. Select campaign rule template and custom rules.
6. Configure currency and calendar.
7. Gather tone, magic level, and setting type.
8. If the campaign uses hidden surprises, define a fixed premise, a 100% primary-secret table, and independent percentage complications; roll and persist them without spoilers.
9. Generate starting world entities through `tools/dm-world.sh` and related wrappers.
10. Create the player character.
11. Validate the finished campaign before starting play.

Ask one compact question at a time when later answers depend on the earlier answer. Use a structured input tool only when it is available and materially clearer than normal dialogue.

## Specialists

Specialists are reference playbooks, not permanently loaded agents. Read only the needed file under `references/specialists/`:

- `create-character.md`: D&D character construction.
- `rules-master.md`: official mechanics and conditions.
- `monster-manual.md`: monsters and encounter data.
- `spell-caster.md`: spells and spellcasting.
- `gear-master.md`: equipment and magic items.
- `loot-dropper.md`: contextual loot generation.
- `npc-builder.md`: NPC enhancement.
- `world-builder.md`: locations and world detail.
- `dungeon-architect.md`: structured dungeon generation.
- `extractor-*.md`: document import extraction.

Execute a specialist locally by default. Use a subagent only when delegation is allowed and the work is genuinely independent; give it the relevant specialist reference and concrete output path. The primary agent validates and imports all results.

## Workflow references

- Read `references/workflows/class-intros.md` when opening a newly created character's first scene.
- Read `references/workflows/cognitive-rendering.md` when deciding how much detail to create around the current location.
- Read `references/codex-adaptation.md` when a copied reference mentions a Claude-only tool or hook.

Do not preload all command and specialist references. The point of this adapter is to keep normal Codex context small.
