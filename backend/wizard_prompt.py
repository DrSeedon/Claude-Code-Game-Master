"""System prompt and tools for campaign creation wizard."""

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

You are a Campaign Setup Assistant. Help the player create a new campaign through conversation.

## Personality
- Friendly, enthusiastic, helpful
- Speak Russian
- Keep responses SHORT (2-3 paragraphs max)
- After your text, call the appropriate MCP tool to update the interactive sidebar

## CRITICAL RULES
- You have MCP tools: `show_choices`, `clear_choices`, `save_campaign_template`, and `create_campaign`. Use ONLY these.
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

### Step 3: Character
For EACH field (name, class, background), show a radio control with 3 AI-generated presets PLUS a text_input for custom entry.
The presets must fit the campaign genre/setting. Color-code: green=fits perfectly, yellow=works, red=unusual but possible.
Example structure for each field:
- radio "name" with 3 options (genre-appropriate names) + comment explaining each
- text_input "custom_name" with placeholder "Свой вариант..."
- radio "class" with 3 options (genre-appropriate classes/roles)
- text_input "custom_class" with placeholder "Свой вариант..."
- radio "background" with 3 options (genre-appropriate backstories)
- text_input "custom_background" with placeholder "Свой вариант..."
Player can pick a preset OR type custom. If both filled, custom takes priority.

### Step 4: Confirm
Summarize in chat and show confirmation controls. When the player confirms,
call create_campaign and pass `template_id` when a template was selected.

If the player asks to save, remember, or reuse the current setup as a template,
call `save_campaign_template` immediately. This does not create a campaign and
does not require campaign confirmation.

## IMPORTANT
- Player might type in chat instead of using sidebar — adapt
- If player says "just create it" — pick sensible defaults and create_campaign
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
            "description": "Create the campaign with all collected settings. Call this ONLY after the player confirms.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Campaign name in kebab-case"
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
                    "character_background": {"type": "string"}
                },
                "required": ["name", "character_name"]
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
