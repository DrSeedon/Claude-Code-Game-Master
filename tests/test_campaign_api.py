"""Unit tests for campaign API functions."""

import pytest
import json
from backend.campaign_api import (
    list_campaigns,
    create_campaign,
    activate_campaign,
    delete_campaign,
    get_campaign,
)


@pytest.fixture
def temp_project_root(tmp_path, monkeypatch):
    """Create temporary project root with campaigns directory."""
    # Mock get_project_root to return temp directory
    monkeypatch.setattr(
        "backend.campaign_api.get_project_root",
        lambda: tmp_path
    )

    # Create world-state/campaigns structure
    campaigns_dir = tmp_path / "world-state" / "campaigns"
    campaigns_dir.mkdir(parents=True)

    return tmp_path


def test_list_campaigns_empty(temp_project_root):
    """Test listing campaigns returns empty list when no campaigns exist."""
    result = list_campaigns()
    assert isinstance(result, list)
    assert len(result) == 0


def test_list_campaigns_multiple(temp_project_root):
    """Test listing campaigns returns all campaign directories."""
    # Create test campaign directories
    campaigns_dir = temp_project_root / "world-state" / "campaigns"

    # Campaign 1
    campaign1_dir = campaigns_dir / "test-campaign-1"
    campaign1_dir.mkdir()
    overview1 = {
        "name": "test-campaign-1",
        "genre": "fantasy",
        "tone": "heroic",
        "description": "Test campaign 1",
        "created_at": "2026-04-01T10:00:00Z"
    }
    (campaign1_dir / "campaign-overview.json").write_text(
        json.dumps(overview1), encoding="utf-8"
    )

    # Campaign 2
    campaign2_dir = campaigns_dir / "test-campaign-2"
    campaign2_dir.mkdir()
    overview2 = {
        "name": "test-campaign-2",
        "genre": "sci-fi",
        "tone": "dark",
        "description": "Test campaign 2",
        "created_at": "2026-04-01T11:00:00Z"
    }
    (campaign2_dir / "campaign-overview.json").write_text(
        json.dumps(overview2), encoding="utf-8"
    )

    # Test list_campaigns returns both
    result = list_campaigns()
    assert isinstance(result, list)
    assert len(result) == 2

    # Verify campaign data structure
    assert result[0]["name"] == "test-campaign-1"
    assert result[0]["genre"] == "fantasy"
    assert result[0]["active"] == False
    assert "created_at" in result[0]

    assert result[1]["name"] == "test-campaign-2"
    assert result[1]["genre"] == "sci-fi"


def test_create_campaign_success(temp_project_root):
    """Test POST /api/campaigns creates directory with world.json."""
    result = create_campaign(
        name="new-campaign",
        genre="fantasy",
        tone="heroic",
        description="A new adventure"
    )

    assert result["success"] == True
    assert result["name"] == "new-campaign"
    assert result["genre"] == "fantasy"

    # Verify directory created
    campaign_dir = temp_project_root / "world-state" / "campaigns" / "new-campaign"
    assert campaign_dir.exists()
    assert campaign_dir.is_dir()

    # Verify world.json exists
    world_file = campaign_dir / "world.json"
    assert world_file.exists()
    world_data = json.loads(world_file.read_text(encoding="utf-8"))
    assert "nodes" in world_data
    assert "edges" in world_data

    # Verify campaign-overview.json exists
    overview_file = campaign_dir / "campaign-overview.json"
    assert overview_file.exists()
    overview_data = json.loads(overview_file.read_text(encoding="utf-8"))
    assert overview_data["name"] == "new-campaign"
    assert overview_data["genre"] == "fantasy"


def test_create_campaign_duplicate(temp_project_root):
    """Test creating duplicate campaign returns error."""
    # Create first campaign
    create_campaign(name="duplicate-test")

    # Try to create again
    result = create_campaign(name="duplicate-test")

    assert result["success"] == False
    assert "already exists" in result["error"]


def test_create_campaign_invalid_name(temp_project_root):
    """Test creating campaign with invalid characters returns error."""
    result = create_campaign(name="invalid/name")

    assert result["success"] == False
    assert "invalid characters" in result["error"]


@pytest.mark.parametrize("name", ["..", ".hidden", "../outside", "/tmp/outside"])
def test_campaign_api_rejects_path_traversal(temp_project_root, name):
    result = create_campaign(name=name)

    assert result["success"] is False


def test_activate_campaign_success(temp_project_root):
    """Test activating campaign updates active-campaign.txt."""
    # Create a campaign first
    create_campaign(name="test-activation")

    # Activate it
    result = activate_campaign("test-activation")

    assert result["success"] == True
    assert result["name"] == "test-activation"

    # Verify active-campaign.txt updated
    active_file = temp_project_root / "world-state" / "active-campaign.txt"
    assert active_file.exists()
    assert active_file.read_text(encoding="utf-8") == "test-activation"


def test_activate_campaign_not_found(temp_project_root):
    """Test activating non-existent campaign returns error."""
    result = activate_campaign("non-existent")

    assert result["success"] == False
    assert "not found" in result["error"]


def test_delete_campaign_success(temp_project_root):
    """Test deleting campaign removes directory."""
    # Create a campaign
    create_campaign(name="to-delete")

    campaign_dir = temp_project_root / "world-state" / "campaigns" / "to-delete"
    assert campaign_dir.exists()

    # Delete it
    result = delete_campaign("to-delete")

    assert result["success"] == True
    assert not campaign_dir.exists()


def test_delete_campaign_active_blocked(temp_project_root):
    """Test deleting active campaign is prevented."""
    # Create and activate a campaign
    create_campaign(name="active-campaign")
    activate_campaign("active-campaign")

    # Try to delete it
    result = delete_campaign("active-campaign")

    assert result["success"] == False
    assert "active campaign" in result["error"].lower()


def test_get_campaign_success(temp_project_root):
    """Test getting single campaign info."""
    # Create a campaign
    create_campaign(
        name="info-test",
        genre="fantasy",
        description="Test description"
    )

    # Get its info
    result = get_campaign("info-test")

    assert "error" not in result
    assert result["name"] == "info-test"
    assert result["genre"] == "fantasy"
    assert result["description"] == "Test description"


def test_get_campaign_not_found(temp_project_root):
    """Test getting non-existent campaign returns error."""
    result = get_campaign("does-not-exist")

    assert "error" in result
    assert "not found" in result["error"]
