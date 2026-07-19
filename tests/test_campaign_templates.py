import json

from backend.campaign_templates import (
    get_campaign_template,
    list_campaign_templates,
    save_campaign_template,
)


def test_lists_built_in_and_user_templates(tmp_path):
    built_in = (
        tmp_path
        / ".claude"
        / "additional"
        / "campaign-rules-templates"
    )
    built_in.mkdir(parents=True)
    (built_in / "builtin.md").write_text(
        "## id\nbuiltin\n\n"
        "## name\nBuilt In\n\n"
        "## description\nBase rules\n\n"
        "## genres\nfantasy, strategy\n\n"
        "## rules\nKeep moving.\n",
        encoding="utf-8",
    )
    result = save_campaign_template(
        {
            "id": "my-template",
            "name": "My Template",
            "modules": ["mass-combat"],
        },
        tmp_path,
    )

    templates = list_campaign_templates(tmp_path)

    assert result["success"] is True
    assert [template["id"] for template in templates] == [
        "my-template",
        "builtin",
    ]
    assert get_campaign_template("builtin", tmp_path)["rules"] == "Keep moving."
    assert get_campaign_template("my-template", tmp_path)["source"] == "user"


def test_save_updates_user_template_atomically(tmp_path):
    save_campaign_template(
        {"id": "editable", "name": "First"},
        tmp_path,
    )
    result = save_campaign_template(
        {"id": "editable", "name": "Second", "genres": ["sci-fi"]},
        tmp_path,
    )

    path = tmp_path / "world-state" / "campaign-templates" / "editable.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert result["success"] is True
    assert data["name"] == "Second"
    assert not (path.parent / ".editable.tmp").exists()


def test_save_rejects_unsafe_id(tmp_path):
    result = save_campaign_template(
        {"id": "../escape", "name": "Bad"},
        tmp_path,
    )

    assert result["success"] is False
    assert not (tmp_path / "world-state" / "escape.json").exists()


def test_built_in_template_cannot_be_overwritten(tmp_path):
    built_in = (
        tmp_path
        / ".claude"
        / "additional"
        / "campaign-rules-templates"
    )
    built_in.mkdir(parents=True)
    (built_in / "locked.md").write_text(
        "## id\nlocked\n\n## name\nLocked\n",
        encoding="utf-8",
    )

    result = save_campaign_template(
        {"id": "locked", "name": "Overwrite"},
        tmp_path,
    )

    assert result["success"] is False
    assert "cannot be overwritten" in result["error"]
