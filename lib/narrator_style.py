"""Render the shared narrator contract from an ID or embedded campaign style."""

import re
from pathlib import Path


def render_narrator_style(project_root: Path, style) -> str:
    if not style:
        return ""
    if isinstance(style, str):
        style_id = style.strip()
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", style_id):
            raise ValueError("Invalid narrator style ID")
        path = project_root / ".claude/additional/narrator-styles" / f"{style_id}.md"
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    if not isinstance(style, dict):
        raise ValueError("Invalid narrator style: expected an ID or object")
    sections = [f"# Narrator Style: {style.get('name') or style.get('id') or 'Custom'}"]
    for key in ("description", "voice", "rules_raw"):
        if style.get(key):
            sections.append(style[key])
    if style.get("forbidden"):
        sections.append("## Forbidden\n\n" + "\n".join(
            f"- {item}" for item in style["forbidden"]
        ))
    return "\n\n".join(sections)
