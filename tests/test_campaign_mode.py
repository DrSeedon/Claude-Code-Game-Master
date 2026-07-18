import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from lib.campaign_mode import CampaignModeManager
from lib.campaign_manager import CampaignManager


@pytest.fixture
def world_state(tmp_path):
    campaign_dir = tmp_path / "world-state" / "campaigns" / "test"
    campaign_dir.mkdir(parents=True)
    (tmp_path / "world-state" / "active-campaign.txt").write_text("test")
    (campaign_dir / "campaign-overview.json").write_text(
        json.dumps({"campaign_name": "Test"})
    )
    return tmp_path / "world-state"


def test_missing_mode_defaults_to_interactive(world_state):
    manager = CampaignModeManager(str(world_state))

    assert manager.get_mode() == "interactive"


def test_set_mode_persists_canonical_value(world_state):
    manager = CampaignModeManager(str(world_state))

    assert manager.set_mode("book") == "narrative"

    overview = json.loads(manager.overview_path.read_text())
    assert overview["play_mode"] == "narrative"


def test_dnd_alias_selects_interactive(world_state):
    manager = CampaignModeManager(str(world_state))
    manager.set_mode("narrative")

    assert manager.set_mode("dnd") == "interactive"
    assert manager.get_mode() == "interactive"


def test_unknown_mode_is_rejected(world_state):
    manager = CampaignModeManager(str(world_state))

    with pytest.raises(ValueError, match="Unknown play mode"):
        manager.set_mode("cinematic")


def test_new_campaign_enables_mode_and_visual_defaults(tmp_path):
    manager = CampaignManager(str(tmp_path / "world-state"))

    campaign_dir = manager.create("test", "Test")

    overview = json.loads((campaign_dir / "campaign-overview.json").read_text())
    assert overview["play_mode"] == "interactive"
    assert overview["cinematic_visuals"] == {
        "enabled": True,
        "frequency": "occasional",
        "aspect_ratio": "16:9",
        "presentation": "game-loading-screen",
    }


def test_campaign_manager_rejects_path_traversal(tmp_path):
    manager = CampaignManager(str(tmp_path / "world-state"))

    assert manager.create("../outside", "Unsafe") is None
    assert not (tmp_path / "outside").exists()


def test_campaign_manager_rejects_absolute_delete(tmp_path):
    manager = CampaignManager(str(tmp_path / "world-state"))
    outside = tmp_path / "outside"
    outside.mkdir()

    assert manager.delete(str(outside), confirm=True) is False
    assert outside.exists()


def test_concurrent_campaign_creation_keeps_the_winning_directory(tmp_path):
    manager = CampaignManager(str(tmp_path / "world-state"))
    ready = threading.Barrier(2)

    def create():
        ready.wait()
        return manager.create("same-name", "Same Name")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: create(), range(2)))

    assert sum(result is not None for result in results) == 1
    campaign = tmp_path / "world-state" / "campaigns" / "same-name"
    assert (campaign / "world.json").is_file()
    assert (campaign / "campaign-overview.json").is_file()
