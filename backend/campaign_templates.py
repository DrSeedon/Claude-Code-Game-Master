"""Built-in and user campaign template catalogue."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from backend.config import get_project_root


TEMPLATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
TEMPLATE_FIELDS = {
    "id",
    "name",
    "description",
    "genres",
    "genre",
    "tone",
    "recommended_for",
    "modules",
    "narrator_style",
    "rules",
    "character_name",
    "character_class",
    "character_background",
}


def _built_in_dir(project_root: Path) -> Path:
    return (
        project_root
        / ".claude"
        / "additional"
        / "campaign-rules-templates"
    )


def _user_dir(project_root: Path) -> Path:
    return project_root / "world-state" / "campaign-templates"


def _parse_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    return [
        item.strip()
        for item in value.replace("\n", ",").split(",")
        if item.strip()
    ]


def _parse_markdown(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    for section in re.split(r"^## ", text, flags=re.MULTILINE):
        lines = section.strip().splitlines()
        if not lines:
            continue
        sections[lines[0].strip().lower()] = "\n".join(lines[1:]).strip()

    template_id = sections.get("id", path.stem).strip()
    return {
        "id": template_id,
        "name": sections.get("name", template_id).strip(),
        "description": sections.get("description", "").strip(),
        "genres": _parse_list(sections.get("genres", "")),
        "genre": sections.get("genre", "").strip(),
        "tone": sections.get("tone", "").strip(),
        "recommended_for": sections.get("recommended_for", "").strip(),
        "modules": _parse_list(sections.get("modules", "")),
        "narrator_style": sections.get("narrator_style", "").strip(),
        "rules": sections.get("rules", "").strip(),
        "character_name": sections.get("character_name", "").strip(),
        "character_class": sections.get("character_class", "").strip(),
        "character_background": sections.get(
            "character_background",
            "",
        ).strip(),
        "source": "built-in",
    }


def _normalize_user_template(data: dict[str, Any], path: Path) -> dict[str, Any]:
    template_id = str(data.get("id") or path.stem).strip()
    if not TEMPLATE_ID_RE.fullmatch(template_id):
        raise ValueError(f"Invalid campaign template id: {template_id!r}")
    return {
        "id": template_id,
        "name": str(data.get("name") or template_id).strip(),
        "description": str(data.get("description") or "").strip(),
        "genres": _parse_list(data.get("genres") or data.get("genre", "")),
        "genre": str(data.get("genre") or "").strip(),
        "tone": str(data.get("tone") or "").strip(),
        "recommended_for": str(data.get("recommended_for") or "").strip(),
        "modules": _parse_list(data.get("modules", [])),
        "narrator_style": str(data.get("narrator_style") or "").strip(),
        "rules": str(data.get("rules") or "").strip(),
        "character_name": str(data.get("character_name") or "").strip(),
        "character_class": str(data.get("character_class") or "").strip(),
        "character_background": str(
            data.get("character_background") or ""
        ).strip(),
        "source": "user",
    }


def list_campaign_templates(
    project_root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    root = Path(project_root or get_project_root())
    templates: dict[str, dict[str, Any]] = {}

    built_in_dir = _built_in_dir(root)
    if built_in_dir.exists():
        for path in sorted(built_in_dir.glob("*.md")):
            try:
                template = _parse_markdown(path)
            except (OSError, ValueError):
                continue
            templates[template["id"]] = template

    user_dir = _user_dir(root)
    if user_dir.exists():
        for path in sorted(user_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                template = _normalize_user_template(data, path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            templates[template["id"]] = template

    return sorted(
        templates.values(),
        key=lambda item: (item["source"] != "user", item["name"].casefold()),
    )


def get_campaign_template(
    template_id: str,
    project_root: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    return next(
        (
            template
            for template in list_campaign_templates(project_root)
            if template["id"] == template_id
        ),
        None,
    )


def save_campaign_template(
    template: dict[str, Any],
    project_root: Optional[Path] = None,
) -> dict[str, Any]:
    root = Path(project_root or get_project_root())
    template_id = str(template.get("id") or "").strip()
    if not TEMPLATE_ID_RE.fullmatch(template_id):
        return {
            "success": False,
            "error": (
                "Template id must use lowercase letters, digits, and hyphens."
            ),
        }

    built_in_path = _built_in_dir(root) / f"{template_id}.md"
    if built_in_path.exists():
        return {
            "success": False,
            "error": f"Built-in template '{template_id}' cannot be overwritten.",
        }

    data = {
        key: template[key]
        for key in TEMPLATE_FIELDS
        if key in template
    }
    data["id"] = template_id
    data["name"] = str(data.get("name") or template_id).strip()
    data["modules"] = _parse_list(data.get("modules", []))
    data["genres"] = _parse_list(data.get("genres", []))

    user_dir = _user_dir(root)
    user_dir.mkdir(parents=True, exist_ok=True)
    target = user_dir / f"{template_id}.json"
    temporary = user_dir / f".{template_id}.tmp"
    try:
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    except OSError as exc:
        return {"success": False, "error": str(exc)}

    saved = _normalize_user_template(data, target)
    return {"success": True, "template": saved, "path": str(target)}
