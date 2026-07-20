"""System prompt and tools for campaign creation wizard."""

import json
from copy import deepcopy
from pathlib import Path
from backend.config import get_project_root
from backend.campaign_templates import list_campaign_templates
from backend.campaign_setup import CAMPAIGN_SETUP_SCHEMA


def load_wizard_system_prompt() -> str:
    project_root = get_project_root()
    modules = _load_modules(project_root)
    narrators = _load_narrators(project_root)
    templates = _load_templates(project_root)

    return f"""# Campaign Creation Wizard

You are a Campaign Setup Assistant. Help the player create a new campaign through conversation.

## Personality
- Friendly, enthusiastic, helpful
- Speak Russian
- Keep responses SHORT (2-3 paragraphs max)
- After your text, call the appropriate MCP tool to update the interactive sidebar

## CRITICAL RULES
- You have MCP tools: `show_choices`, `clear_choices`, `load_creation_rules`,
  `save_campaign_template`, and `create_campaign`. Use ONLY these.
- Do NOT use Read, Write, Bash, Edit, ToolSearch, AskUserQuestion, or any other tools.
- YOU control the sidebar panel. Call show_choices to display options, clear_choices to hide them.
- When the player submits from sidebar, it auto-clears. Do NOT call clear_choices after a submit — just call show_choices for the next step.
- Only call clear_choices when you want to hide choices without the player submitting (e.g. player typed in chat instead).
- If the player asks a question about current choices, answer WITHOUT clearing — keep choices visible.

## Message sources
- Messages starting with `[Sidebar selection for step "..."]` = player clicked submit in sidebar. The sidebar auto-cleared. Proceed to next step.
- Messages starting with `[Sidebar skip for step "..."]` = player clicked skip. Move on.
- Messages starting with `[System: ...]` = system context about current UI state.
- All other messages = player typed in chat. Sidebar choices (if any) are still visible.

## Option colors for show_choices
- "green" = highly recommended for this campaign
- "yellow" = could work, situational
- "red" = probably not a good fit, but still available
- Always add "comment" explaining WHY this color

## Workflow

### Step 1: Concept
The web client initially shows the real campaign template catalogue and installed
modules. Preserve exact template and module IDs from sidebar metadata. If the
player types instead, ask what kind of campaign and call show_choices with
campaign templates as radio + custom text.

### Step 2: Settings
Based on concept, show_choices with EVERY available module (checkbox) + narrator
style (radio). Color-code recommendations. Never claim modules are unavailable
when the Available Modules section below is non-empty. Preserve all modules the
player selected in Step 1.

### Step 3: Compile creation rules
As soon as template and module selection are final, call `load_creation_rules`
with the exact selected module IDs and template ID. This is mandatory even when
no optional modules are selected. Never create a campaign before this call.
Treat its result as the authoritative campaign-creation contract:
- CORE `/new-game` and character creation always apply;
- only selected modules contribute module-specific creation rules;
- module rules augment CORE and never replace world/character preparation.

### Step 4: Guided setup
Ask the remaining setup questions required by the compiled rules. Group related
questions to keep the flow short, but do not silently skip required decisions.
At minimum resolve:
- setting, starting premise, tone, currency, calendar, initial date and time;
- complete character sheet: name, race, class/role, background, abilities, HP,
  AC, skills/saves, features, starting equipment and inventory;
- every selected module's creation choices, configuration, reference entities,
  and starting resources.

If the player delegates a decision or says "just create it", choose sensible
defaults, show them in the final summary, and still produce the complete setup.
For a non-fantasy role, create genre-appropriate equivalents of normal D&D
character fields rather than leaving the sheet empty.

### Step 5: Build the campaign blueprint
Before confirmation, prepare one complete `setup` object for `create_campaign`.
It must contain:
- a playable player sheet and non-empty starting inventory;
- starting location plus at least three connected locations;
- six located NPCs, three quests, three consequences, and `misc:economy`;
- campaign metadata and Session 0;
- config and reference nodes required by every selected module.

Use valid WorldGraph IDs (`type:kebab-id`). Put gameplay entities in nodes and
edges, metadata in overview, and module-private config in module_data. Never put
config for an unselected module into the blueprint.

#### player.data mandatory fields checklist
Every single one is validated and will reject creation if missing:
- `race` (string), `class` (string), `background` (string)
- `level` (integer >= 1)
- `hp`: object with `current` and `max` (both positive numbers, current <= max)
- `ac` (positive number)
- `stats`: object with keys str, dex, con, int, wis, cha (all positive numbers)
- `skills`: object with at least one entry (skill name to modifier number)
- `saves`: object with keys str, dex, con, int, wis, cha (modifier numbers)
- `save_proficiencies`: array of ability name strings (e.g. ["con", "wis"])
- `proficiency_bonus` (number, e.g. 2 at level 1)
- `xp`: object with `current` (>= 0) and `next_level` (> 0)
- `money` (number in base currency units)
- `conditions`: array (usually empty at start)
- `features`: array of strings (at least one class/racial feature)
- `equipment`: object with at least one entry (e.g. weapons array, armor string)

#### Node data mandatory fields by type
- **location**: `description` (non-empty string)
- **npc**: `description`, `attitude` (friendly/neutral/hostile)
- **quest**: `description`, `status` (active/completed/failed), `objectives` (array of objects with name and completed fields)
- **consequence**: `description`, `trigger` (what activates it), `status` (pending/triggered/resolved)
- **misc:economy**: `expenses`, `income`, `production`, `random_events` (all must be present)

### Step 6: Confirm and create
Summarize the actual generated world, character, and module setup, then show
confirmation controls. When the player confirms, call `create_campaign` once.
Pass:
- `campaign_id`: stable lowercase kebab-case storage ID, preferably the selected
  template ID when it is unused;
- `display_name`: human-readable title, which may contain spaces, Unicode, and
  punctuation;
- the exact selected module IDs and template ID;
- the complete `setup` blueprint.

Do not retry with a mutated display title. If creation fails, explain the exact
validation error, correct only the blueprint or campaign ID, and ask for
confirmation again when the correction changes player-visible setup.

If the player asks to save, remember, or reuse the current setup as a template,
call `save_campaign_template` immediately. This does not create a campaign and
does not require campaign confirmation.

## IMPORTANT
- Player might type in chat instead of using sidebar — adapt
- If player says "just create it" — pick sensible defaults, compile the rules,
  build a complete blueprint, then create it
- Be flexible — skip steps if player gives all info at once
- Always use the MCP tools directly; never imitate a tool call in ordinary text

## Available Content

### Modules
{modules}

### Narrator Styles
{narrators}

### Campaign Templates
{templates}
"""


def get_wizard_tool_schemas():
    return [
        {
            "name": "show_choices",
            "description": "Display interactive choices in the sidebar panel for the player to select from. Call this after your text response to show relevant options. The player will see these as clickable cards/inputs and can submit their selections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "step": {
                        "type": "string",
                        "description": "Current wizard step name (concept, settings, character, confirm)"
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
            "name": "load_creation_rules",
            "description": (
                "Compile authoritative CORE and selected-module creation rules "
                "before asking setup questions or creating a campaign."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exact selected module IDs.",
                    },
                    "template_id": {
                        "type": "string",
                        "description": "Selected template ID, or empty string.",
                    },
                },
                "required": ["modules"],
            },
        },
        {
            "name": "save_campaign_template",
            "description": "Persist the current wizard configuration as a reusable user campaign template without creating a campaign.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Stable kebab-case template ID"
                    },
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "genres": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "genre": {"type": "string"},
                    "tone": {"type": "string"},
                    "recommended_for": {"type": "string"},
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "narrator_style": {"type": "string"},
                    "rules": {"type": "string"},
                    "character_name": {"type": "string"},
                    "character_class": {"type": "string"},
                    "character_background": {"type": "string"}
                },
                "required": ["id", "name"]
            }
        },
        {
            "name": "create_campaign",
            "description": (
                "Validate and atomically create a ready-to-play campaign. Call "
                "only after loading creation rules, building the full blueprint, "
                "and receiving player confirmation."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "string",
                        "description": "Stable lowercase kebab-case storage ID."
                    },
                    "display_name": {
                        "type": "string",
                        "description": "Human-readable campaign title."
                    },
                    "genre": {"type": "string"},
                    "tone": {"type": "string"},
                    "description": {"type": "string"},
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "narrator_style": {"type": "string"},
                    "rules": {"type": "string"},
                    "template_id": {"type": "string"},
                    "character_name": {"type": "string"},
                    "character_class": {"type": "string"},
                    "character_race": {"type": "string"},
                    "character_background": {"type": "string"},
                    "setup": deepcopy(CAMPAIGN_SETUP_SCHEMA),
                },
                "required": [
                    "campaign_id",
                    "display_name",
                    "character_name",
                    "modules",
                    "setup"
                ]
            }
        }
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
