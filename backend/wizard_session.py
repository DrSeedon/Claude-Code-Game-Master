"""Persistent wizard drafts — survive WS reconnect.

Unlike GameSession (background turns + broker), a wizard draft is single-user and
interactive, so turns run inline in the WS handler. This module only owns the two
things that must outlive a socket: the SDK provider (its session_id lets the CLI
resume the conversation) and an append-only event log (for history replay on
reconnect). A draft lives under world-state/wizard-drafts/<id>/.
"""

import shutil
from pathlib import Path
from typing import Dict

from backend.providers.claude_sdk import ClaudeSDKProvider

_drafts: Dict[str, "WizardDraft"] = {}


def _draft_dir(project_root: Path, session_id: str) -> Path:
    return project_root / "world-state" / "wizard-drafts" / session_id


class WizardDraft:
    """Provider + event-log dir for one wizard session, keyed by session_id."""

    def __init__(self, session_id: str, project_root: Path, model_name: str):
        self.session_id = session_id
        self.project_root = project_root
        self.provider = ClaudeSDKProvider(project_root=project_root, model_name=model_name)
        self.dir = _draft_dir(project_root, session_id)
        self.running = False  # inline turn lock — reject overlapping sends


def get_or_create_draft(session_id: str, project_root: Path, model_name: str) -> "WizardDraft":
    draft = _drafts.get(session_id)
    if draft is None:
        draft = WizardDraft(session_id, project_root, model_name)
        _drafts[session_id] = draft
    return draft


def delete_draft(session_id: str, project_root: Path) -> bool:
    """Drop the in-memory draft and its on-disk event log. Returns True if anything existed."""
    existed = _drafts.pop(session_id, None) is not None
    d = _draft_dir(project_root, session_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        existed = True
    return existed
