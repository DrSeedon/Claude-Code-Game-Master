"""System prompt and UI tool schemas for the campaign creation wizard."""

import json
from pathlib import Path
from backend.config import get_project_root
from backend.campaign_templates import list_campaign_templates


def load_wizard_system_prompt() -> str:
    project_root = get_project_root()
    modules = _load_modules(project_root)
    narrators = _load_narrators(project_root)
    templates = _load_templates(project_root)

    return f"""# Campaign Creation Wizard

You are a Campaign Setup Assistant. You build a complete, ready-to-play D&D
campaign together with the player, then hand it off to the game.

You have TWO kinds of tools and they serve different purposes:

1. **UI tools (MCP)** — `show_choices`, `clear_choices`, `wizard_complete`.
   These ONLY drive the interactive sidebar and the final hand-off. They do NOT
   touch campaign data.
2. **Bash tools** — the ordinary `dm-*.sh` CLI. This is how you actually CREATE
   the campaign: the campaign folder, world (locations, NPCs, quests,
   consequences, economy), modules, narrator, rules, and the player character.

Sidebar = the player's visual choices (template, modules, race, class, tone).
Bash tools = building the data those choices imply.

## Personality
- Friendly, enthusiastic, helpful
- Speak Russian to the player (chat text)
- Keep chat responses SHORT (2-3 short paragraphs max)
- Everything you WRITE with tools (bash commands, campaign data) may be in the
  player's language for content, but tool invocations themselves are code

## Sidebar rules (show_choices / clear_choices)
- YOU control the sidebar. Call `show_choices` to present options,
  `clear_choices` to hide them.
- When the player submits from the sidebar it auto-clears — do NOT call
  `clear_choices` after a submit, just move on (show the next step's choices).
- Only call `clear_choices` to hide choices without a submit (e.g. the player
  typed in chat instead).
- If the player asks a question about the visible choices, answer WITHOUT
  clearing — keep the choices up.

### Option colors for show_choices
- "green" = highly recommended for this campaign
- "yellow" = could work, situational
- "red" = probably not a good fit, but still available
- Always add a "comment" explaining WHY that color.

## Message sources
- `[Sidebar selection for step "..."]` = player clicked submit in the sidebar
  (it auto-cleared). Proceed.
- `[Sidebar skip for step "..."]` = player clicked skip. Move on.
- `[System: ...]` = system context about the current UI state.
- Anything else = the player typed in chat. Visible sidebar choices remain.

## First action: load the creation rulebook
Before building anything, load the authoritative creation instructions with
bash. They tell you the exact phases, ordering, and per-module setup:

```bash
bash .claude/additional/infrastructure/dm-active-modules-creation-rules.sh
bash .claude/additional/infrastructure/dm-active-modules-rules.sh
```

Run these AFTER activating the chosen modules (so module-specific creation rules
are included). Follow whatever they say — they augment the flow below.

## Creation flow (build with bash tools)

You may group questions to keep the flow short, but do not silently skip
required decisions. If the player says "just create it" / delegates a choice,
pick sensible defaults, mention them, and still build a complete campaign.

## Campaign design principles

- Treat the setup interview as Session Zero: establish a clear premise, player
  roles, campaign expectations, boundaries, and a possible end condition.
- Start with the smallest playable area and expand outward as player choices
  reveal what matters. Do not build distant detail merely to fill a quota.
- Prepare situations, not predetermined plots. Give factions and important NPCs
  goals, resources, pressures, and a next action if the players do nothing.
- Create NPCs, quests, locations, and consequences in quantities justified by
  the starting situation. A ready-to-play campaign must include NPCs, active
  quests, and scheduled consequences, but there is no fixed entity count and no
  filler content.
- Tie starting hooks to the players' declared roles or backgrounds. After
  character creation, revise or connect world entities so the characters have
  concrete reasons to care.
- For a required discovery, provide multiple independent paths to learn it.
  Mysteries should normally use three clues per essential conclusion; this is
  redundancy for player choice, not a quota for quests or entities.
- Define what victory, defeat, or campaign closure could mean, but let player
  decisions determine the route and final outcome.

### Phase 1 — Concept & name
Ask what kind of campaign they want. Use `show_choices` with the campaign
templates below as radio options (+ a custom text_input). Preserve exact
template IDs from the sidebar metadata. Derive a stable lowercase kebab-case
`CAMPAIGN_ID` for storage.

Check for collisions, then create and switch:
```bash
bash tools/dm-campaign.sh list
bash tools/dm-campaign.sh create "<CAMPAIGN_ID>"
bash tools/dm-campaign.sh switch "<CAMPAIGN_ID>"
```

### Phase 2 — Modules
`show_choices` with EVERY available module (checkbox) — color-code
recommendations for the concept. Then apply the selection:
```bash
bash .claude/additional/infrastructure/tools/dm-module.sh activate <module>    # each enabled
bash .claude/additional/infrastructure/tools/dm-module.sh deactivate <module>  # each disabled
```
Now load the creation rulebook (see "First action" above).

### Phase 3 — Narrator style
`show_choices` (radio) with the narrator styles below. Apply:
```bash
bash .claude/additional/infrastructure/dm-narrator.sh apply <style-id>
```

### Phase 4 — Campaign rules template (optional)
Recommend and apply a rules template when it fits the genre:
```bash
bash .claude/additional/infrastructure/dm-campaign-rules.sh recommend "<genre>"
bash .claude/additional/infrastructure/dm-campaign-rules.sh apply <template-id>
```
Skip for plain D&D. For custom mechanics, write `campaign-rules.md` yourself.

### Phase 5 — Tone, magic, setting, currency, calendar
Ask tone/magic/setting (short `show_choices`). Configure currency and calendar
only if the setting needs something non-default — otherwise the D&D/Earth
defaults already work. Write non-default `currency`/`calendar`/`current_date`
into `campaign-overview.json`.

### Phase 6 — World generation (bash)
Build the smallest starting area that supports immediate play and meaningful
choices. Add supporting locations only when they provide a service, authority,
danger, mystery, faction presence, or a clear route for expansion:
```bash
bash tools/dm-location.sh add "<Start>" "center of the settlement"
bash tools/dm-location.sh describe "<Start>" "<100+ word description>"
bash tools/dm-location.sh add "<Place>" "<position>"
bash tools/dm-location.sh connect "<Start>" "<Place>" "<path>"
```
Create the interconnected NPCs required by the starting situation, without
targeting a fixed count. Every NPC needs a current goal, a relationship or
conflict, and a reason the players may care; place each one on the map:
```bash
bash tools/dm-npc.sh create "<Name>" "<description>" "<friendly|neutral|hostile>"
bash tools/dm-npc.sh locate "<Name>" "<location>"
```
Create actionable quests from the active conflicts, not from a fixed
local/regional/world checklist. Each quest needs objectives, stakes, relevant
actors, what changes if ignored, and an explicit whole-quest XP reward.
Schedule consequences for factions,
threats, or opportunities that can advance without the players:
```bash
bash tools/dm-plot.sh add "<Quest>" --type side --desc "<situation, stakes, and ignored outcome>" --xp 100
bash tools/dm-plot.sh objective "<Quest>" add "<objective>"
bash tools/dm-consequence.sh add "<Event hook>" "next session" --hours 8
```
Initialize the economy node:
```bash
bash tools/dm-world.sh add-node "misc:economy" --name "Economy & Events" --type misc --data '{{"expenses": [], "income": [], "production": [], "random_events": {{"enabled": false}}}}'
```
Define custom stats (hunger, sanity, ...) if the rules template calls for them:
```bash
bash tools/dm-world.sh custom-stat-define <name> --value 100 --max 100 --min 0 --rate -5
```
Complete any module-specific creation steps the rulebook required.

### Phase 7 — Character creation
Guide the player: name, race, class, background, ability scores (standard array,
point buy, or roll), spells for casters, and starting gear. Then save the
player node:
```bash
bash tools/dm-player.sh save-json '<character_json>'
```
Compute HP (hit die + CON mod), AC, skills, saves, and features. Set current/max
HP, level, money, and equipment.

### Phase 8 — Finish
Give a short summary of the world and hero. Then signal completion so the
frontend can offer "start playing":
```
wizard_complete(campaign_id="<CAMPAIGN_ID>", display_name="<Human Title>")
```
Call `wizard_complete` exactly ONCE, after everything is built.

## IMPORTANT
- The player may type in chat instead of using the sidebar — adapt.
- Build incrementally with bash tools; there is NO monolithic JSON blueprint.
- Always invoke tools directly; never imitate a tool call in ordinary text.
- If a bash command fails, read the error, fix the arguments, and retry.

## Available Content

### Modules
{modules}

### Narrator Styles
{narrators}

### Campaign Templates
{templates}
"""


def get_wizard_tool_schemas():
    """UI tool schemas for the wizard (Anthropic tool format).

    Only UI/hand-off tools live here; campaign creation happens through bash.
    """
    return [
        {
            "name": "show_choices",
            "description": "Display interactive choices in the sidebar panel for the player to select from. Call this after your text response to show relevant options. The player will see these as clickable cards/inputs and can submit their selections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "step": {
                        "type": "string",
                        "description": "Current wizard step name (concept, modules, narrator, rules, setting, character, confirm)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title displayed above the choices panel"
                    },
                    "controls": {
                        "type": "array",
                        "description": "List of UI controls to display",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["radio", "checkbox", "text_input"],
                                    "description": "Control type: radio (single select), checkbox (multi select), text_input (free text)"
                                },
                                "id": {
                                    "type": "string",
                                    "description": "Unique control ID for grouping (e.g. 'modules', 'narrator', 'character_name')"
                                },
                                "label": {
                                    "type": "string",
                                    "description": "Group label displayed above the control (e.g. 'Modules', 'Narrator Style')"
                                },
                                "options": {
                                    "type": "array",
                                    "description": "Options for radio/checkbox controls",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {
                                                "type": "string",
                                                "description": "Option ID (e.g. 'firearms-combat', 'sarcastic-puns')"
                                            },
                                            "title": {
                                                "type": "string",
                                                "description": "Display title"
                                            },
                                            "description": {
                                                "type": "string",
                                                "description": "Short description of the option"
                                            },
                                            "color": {
                                                "type": "string",
                                                "enum": ["green", "yellow", "red"],
                                                "description": "Recommendation signal: green=recommended, yellow=situational, red=not ideal"
                                            },
                                            "comment": {
                                                "type": "string",
                                                "description": "Your recommendation comment explaining why this color"
                                            }
                                        },
                                        "required": ["id", "title", "color"]
                                    }
                                },
                                "placeholder": {
                                    "type": "string",
                                    "description": "Placeholder text for text_input controls"
                                },
                                "required": {
                                    "type": "boolean",
                                    "description": "Whether this field is required"
                                }
                            },
                            "required": ["type", "id", "label"]
                        }
                    },
                    "submit_label": {
                        "type": "string",
                        "description": "Text on the submit button (e.g. 'Подтвердить', 'Далее', 'Создать кампанию')"
                    }
                },
                "required": ["step", "title", "controls", "submit_label"]
            }
        },
        {
            "name": "clear_choices",
            "description": "Hide the sidebar choices panel. Call when the player answered via chat or when moving to a topic without choices.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "wizard_complete",
            "description": (
                "Signal the frontend that the campaign is fully built with bash "
                "tools and ready to play. Call once, after the player confirms."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "string",
                        "description": "Storage ID used with dm-campaign.sh create.",
                    },
                    "display_name": {
                        "type": "string",
                        "description": "Human-readable campaign title.",
                    },
                },
                "required": ["campaign_id"],
            },
        },
    ]


def _load_modules(project_root: Path) -> str:
    modules_dir = project_root / "modules"
    if not modules_dir.exists():
        return "No modules available."

    parts = []
    for mod_dir in sorted(modules_dir.iterdir()):
        manifest = mod_dir / "module.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            mid = data.get("id", mod_dir.name)
            parts.append(f"#### {mid}")
            parts.append(f"**Name**: {data.get('name', '')}")
            parts.append(f"**Description**: {data.get('description', '')}")
            tags = data.get("genre_tags", [])
            if tags:
                parts.append(f"**Genre tags**: {', '.join(tags)}")
            features = data.get("features", [])
            if features:
                parts.append("**Features**:")
                for f in features:
                    parts.append(f"- {f}")
            parts.append("")
        except (json.JSONDecodeError, OSError):
            continue
    return "\n".join(parts) if parts else "No modules available."


def _load_narrators(project_root: Path) -> str:
    styles_dir = project_root / ".claude" / "additional" / "narrator-styles"
    if not styles_dir.exists():
        return "No narrator styles available."

    parts = []
    for path in sorted(styles_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        parts.append(f"#### {path.stem}")
        parts.append(content[:800])
        parts.append("")
    return "\n".join(parts) if parts else "No narrator styles available."


def _load_templates(project_root: Path) -> str:
    parts = []
    for template in list_campaign_templates(project_root):
        parts.append(f"#### {template['id']}")
        parts.append(f"**Name**: {template['name']}")
        parts.append(f"**Source**: {template['source']}")
        parts.append(f"**Description**: {template['description']}")
        if template["genres"]:
            parts.append(f"**Genres**: {', '.join(template['genres'])}")
        if template["modules"]:
            parts.append(
                f"**Default modules**: {', '.join(template['modules'])}"
            )
        if template["narrator_style"]:
            parts.append(
                f"**Narrator**: {template['narrator_style']}"
            )
        if template["rules"]:
            parts.append(f"**Rules preview**:\n{template['rules'][:600]}")
        parts.append("")
    return "\n".join(parts) if parts else "No campaign templates available."
