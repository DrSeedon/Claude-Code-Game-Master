import pytest

from lib.campaign_context import (
    InvalidCampaignName,
    resolve_campaign_dir,
    scoped_campaign_name,
    validate_campaign_name,
)


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "../outside", "a/b", r"a\b", ".hidden", "/tmp/outside"],
)
def test_rejects_unsafe_campaign_names(name):
    with pytest.raises(InvalidCampaignName):
        validate_campaign_name(name)


def test_resolve_campaign_dir_stays_below_root(tmp_path):
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()

    assert resolve_campaign_dir(campaigns, "My Campaign") == (
        campaigns / "My Campaign"
    ).resolve()


def test_environment_override_is_process_scoped(tmp_path, monkeypatch):
    world_state = tmp_path / "world-state"
    world_state.mkdir()
    (world_state / "active-campaign.txt").write_text("global")
    monkeypatch.setenv("DM_ACTIVE_CAMPAIGN", "web-session")

    assert scoped_campaign_name(world_state) == "web-session"


def test_active_file_is_fallback(tmp_path, monkeypatch):
    world_state = tmp_path / "world-state"
    world_state.mkdir()
    (world_state / "active-campaign.txt").write_text("global")
    monkeypatch.delenv("DM_ACTIVE_CAMPAIGN", raising=False)

    assert scoped_campaign_name(world_state) == "global"
