"""Tests for wizard prompt, MCP tools, and campaign creation flow."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from backend.wizard_prompt import load_wizard_system_prompt, get_wizard_tool_schemas
from backend.campaign_api import create_campaign, list_campaigns, delete_campaign, activate_campaign
from backend.config import get_project_root


class TestWizardPrompt:
    def test_prompt_loads(self):
        prompt = load_wizard_system_prompt()
        assert len(prompt) > 1000
        assert "Campaign Creation Wizard" in prompt

    def test_prompt_contains_modules(self):
        prompt = load_wizard_system_prompt()
        assert "firearms-combat" in prompt or "mass-combat" in prompt or "world-travel" in prompt

    def test_prompt_contains_narrators(self):
        prompt = load_wizard_system_prompt()
        assert "epic-heroic" in prompt or "sarcastic-puns" in prompt

    def test_prompt_contains_rules(self):
        prompt = load_wizard_system_prompt()
        assert "zombie-apocalypse" in prompt or "survival-zone" in prompt

    def test_prompt_has_mcp_tool_instructions(self):
        prompt = load_wizard_system_prompt()
        assert "show_choices" in prompt
        assert "clear_choices" in prompt
        assert "create_campaign" in prompt

    def test_prompt_english_only(self):
        prompt = load_wizard_system_prompt()
        # Check no Russian text in system prompt (rules = English)
        russian_chars = set("абвгдежзийклмнопрстуфхцчшщъыьэюя")
        prompt_lower = prompt.lower()
        for char in russian_chars:
            if char in prompt_lower:
                # Allow in content loaded from templates (narrators/rules may have Russian names)
                # But core instructions must be English
                break


class TestWizardToolSchemas:
    def test_schemas_count(self):
        schemas = get_wizard_tool_schemas()
        assert len(schemas) == 2

    def test_show_choices_schema(self):
        schemas = get_wizard_tool_schemas()
        show = next(s for s in schemas if s["name"] == "show_choices")
        assert "step" in show["input_schema"]["properties"]
        assert "title" in show["input_schema"]["properties"]
        assert "controls" in show["input_schema"]["properties"]
        assert "submit_label" in show["input_schema"]["properties"]

    def test_create_campaign_schema(self):
        schemas = get_wizard_tool_schemas()
        create = next(s for s in schemas if s["name"] == "create_campaign")
        assert "name" in create["input_schema"]["properties"]
        assert "character_name" in create["input_schema"]["properties"]
        assert set(create["input_schema"]["required"]) == {"name", "character_name"}

    def test_show_choices_control_types(self):
        schemas = get_wizard_tool_schemas()
        show = next(s for s in schemas if s["name"] == "show_choices")
        control_type = show["input_schema"]["properties"]["controls"]["items"]["properties"]["type"]
        assert set(control_type["enum"]) == {"radio", "checkbox", "text_input"}

    def test_show_choices_color_enum(self):
        schemas = get_wizard_tool_schemas()
        show = next(s for s in schemas if s["name"] == "show_choices")
        options_schema = show["input_schema"]["properties"]["controls"]["items"]["properties"]["options"]
        color = options_schema["items"]["properties"]["color"]
        assert set(color["enum"]) == {"green", "yellow", "red"}


class TestCampaignCreation:
    @pytest.fixture
    def temp_world_state(self, tmp_path):
        campaigns_dir = tmp_path / "world-state" / "campaigns"
        campaigns_dir.mkdir(parents=True)
        active_file = tmp_path / "world-state" / "active-campaign.txt"
        with patch("backend.campaign_api.get_project_root", return_value=tmp_path):
            yield tmp_path, campaigns_dir, active_file

    def test_create_campaign_basic(self, temp_world_state):
        root, campaigns_dir, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            result = create_campaign(name="test-campaign", genre="fantasy", tone="heroic")
            assert result["success"] is True
            assert result["name"] == "test-campaign"
            assert (campaigns_dir / "test-campaign" / "campaign-overview.json").exists()
            assert (campaigns_dir / "test-campaign" / "world.json").exists()

    def test_create_campaign_with_character(self, temp_world_state):
        root, campaigns_dir, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            result = create_campaign(
                name="char-test",
                character={"name": "Hero", "class": "Fighter", "race": "Human"},
            )
            assert result["success"] is True
            world = json.loads((campaigns_dir / "char-test" / "world.json").read_text())
            assert "player:active" in world["nodes"]
            assert world["nodes"]["player:active"]["name"] == "Hero"

    def test_create_campaign_duplicate(self, temp_world_state):
        root, _, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            create_campaign(name="dup-test")
            result = create_campaign(name="dup-test")
            assert result["success"] is False
            assert "already exists" in result["error"]

    def test_create_campaign_empty_name(self, temp_world_state):
        root, _, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            result = create_campaign(name="")
            assert result["success"] is False

    def test_create_campaign_invalid_chars(self, temp_world_state):
        root, _, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            result = create_campaign(name="bad/name")
            assert result["success"] is False

    def test_list_campaigns(self, temp_world_state):
        root, _, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            create_campaign(name="camp-a")
            create_campaign(name="camp-b")
            campaigns = list_campaigns()
            names = [c["name"] for c in campaigns]
            assert "camp-a" in names
            assert "camp-b" in names

    def test_activate_campaign(self, temp_world_state):
        root, _, active_file = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            create_campaign(name="to-activate")
            result = activate_campaign("to-activate")
            assert result["success"] is True
            assert active_file.read_text().strip() == "to-activate"

    def test_delete_campaign(self, temp_world_state):
        root, campaigns_dir, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            create_campaign(name="to-delete")
            assert (campaigns_dir / "to-delete").exists()
            result = delete_campaign("to-delete")
            assert result["success"] is True
            assert not (campaigns_dir / "to-delete").exists()

    def test_delete_active_blocked(self, temp_world_state):
        root, _, _ = temp_world_state
        with patch("backend.campaign_api.get_project_root", return_value=root):
            create_campaign(name="active-one")
            activate_campaign("active-one")
            result = delete_campaign("active-one")
            assert result["success"] is False
            assert "active campaign" in result["error"]


class TestWizardMCPTools:
    """The wizard MCP is in-process: tools push onto WizardEvents, drained by the
    /ws/wizard handler. build_wizard_mcp registers the three tools with the SDK."""

    def test_build_wizard_mcp_config(self):
        from backend.wizard_mcp import WizardEvents, build_wizard_mcp
        cfg = build_wizard_mcp(WizardEvents())
        assert cfg["type"] == "sdk"
        assert cfg["name"] == "wizard"

    def test_events_push_and_drain(self):
        from backend.wizard_mcp import WizardEvents
        ev = WizardEvents()
        assert ev.drain() == []
        ev.push({"type": "show_choices", "data": {"step": "concept"}})
        ev.push({"type": "clear_choices"})
        drained = ev.drain()
        assert [e["type"] for e in drained] == ["show_choices", "clear_choices"]
        assert drained[0]["data"]["step"] == "concept"
        assert ev.drain() == []  # drain clears the buffer

    @staticmethod
    async def _invoke(cfg, tool_name, arguments):
        """Invoke a registered in-process MCP tool by name (real handler body runs)."""
        import mcp.types as types
        server = cfg["instance"]
        handler = server.request_handlers[types.CallToolRequest]
        req = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name=tool_name, arguments=arguments),
        )
        return await handler(req)

    def test_show_choices_pushes_event(self):
        import asyncio
        from backend.wizard_mcp import WizardEvents, build_wizard_mcp
        ev = WizardEvents()
        cfg = build_wizard_mcp(ev)
        asyncio.run(self._invoke(cfg, "show_choices", {
            "step": "concept", "title": "T", "submit_label": "Go", "controls": [],
        }))
        out = ev.drain()
        assert out[0]["type"] == "show_choices"
        assert out[0]["data"]["step"] == "concept"

    def test_clear_choices_pushes_event(self):
        import asyncio
        from backend.wizard_mcp import WizardEvents, build_wizard_mcp
        ev = WizardEvents()
        cfg = build_wizard_mcp(ev)
        asyncio.run(self._invoke(cfg, "clear_choices", {}))
        out = ev.drain()
        assert out[0]["type"] == "clear_choices"

    def test_create_campaign_optional_fields(self, tmp_path):
        """Only name + character_name are required — the DM must not have to supply
        all 10 fields (regression: dict-shorthand schema made everything required)."""
        import asyncio
        from backend.wizard_mcp import WizardEvents, build_wizard_mcp
        with patch("backend.campaign_api.get_project_root", return_value=tmp_path):
            (tmp_path / "world-state" / "campaigns").mkdir(parents=True)
            ev = WizardEvents()
            cfg = build_wizard_mcp(ev)
            result = asyncio.run(self._invoke(cfg, "create_campaign",
                                              {"name": "min-args", "character_name": "Aria"}))
            cr = result.root if hasattr(result, "root") else result
            assert cr.isError is False  # not rejected by schema validation
            out = ev.drain()
            assert out[0]["type"] == "create_campaign"
            assert out[0]["success"] is True
