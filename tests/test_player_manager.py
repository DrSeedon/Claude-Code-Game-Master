
import json

from lib.player_manager import PlayerManager


def make_campaign(tmp_path, overview_extra=None, character=None):
    campaign_dir = tmp_path / "world-state" / "campaigns" / "test-campaign"
    campaign_dir.mkdir(parents=True)
    ws = tmp_path / "world-state"
    (ws / "active-campaign.txt").write_text("test-campaign")

    overview = {
        "campaign_name": "Test Campaign",
        "time_of_day": "Day",
        "current_date": "Day 1",
        "current_character": "Hero",
    }
    if overview_extra:
        overview.update(overview_extra)
    (campaign_dir / "campaign-overview.json").write_text(
        json.dumps(overview, ensure_ascii=False)
    )

    if character is None:
        character = {
            "name": "Hero",
            "level": 1,
            "hp": {"current": 20, "max": 20},
            "gold": 100,
            "xp": 0,
            "equipment": [],
        }
    char_name = character.pop("name", "Hero")
    world = {
        "nodes": {
            "player:active": {
                "type": "player",
                "name": char_name,
                "data": character
            }
        },
        "edges": []
    }
    character["name"] = char_name
    (campaign_dir / "world.json").write_text(
        json.dumps(world, ensure_ascii=False)
    )

    return str(ws), campaign_dir


class TestModifyHp:
    def test_heal_increases_hp(self, tmp_path):
        ws, camp = make_campaign(tmp_path, character={
            "name": "Hero", "level": 1,
            "hp": {"current": 10, "max": 20},
            "gold": 0, "xp": 0, "equipment": [],
        })
        mgr = PlayerManager(ws)
        result = mgr.modify_hp("Hero", 5)
        assert result["success"] is True
        assert result["current_hp"] == 15

    def test_damage_decreases_hp(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_hp("Hero", -8)
        assert result["success"] is True
        assert result["current_hp"] == 12

    def test_hp_clamps_at_zero(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_hp("Hero", -999)
        assert result["current_hp"] == 0
        assert result["unconscious"] is True

    def test_hp_clamps_at_max(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_hp("Hero", +999)
        assert result["current_hp"] == 20

    def test_hp_persisted_to_file(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        mgr.modify_hp("Hero", -5)
        world = json.loads((camp / "world.json").read_text())
        char = world["nodes"]["player:active"]["data"]
        assert char["hp"]["current"] == 15

    def test_bloodied_flag(self, tmp_path):
        ws, camp = make_campaign(tmp_path, character={
            "name": "Hero", "level": 1,
            "hp": {"current": 20, "max": 20},
            "gold": 0, "xp": 0, "equipment": [],
        })
        mgr = PlayerManager(ws)
        result = mgr.modify_hp("Hero", -16)
        assert result["bloodied"] is True

    def test_auto_detect_name_none(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_hp(None, -3)
        assert result["success"] is True
        assert result["current_hp"] == 17


class TestModifyGold:
    def test_add_gold(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_gold("Hero", 50)
        assert result["current_gold"] == 10050  # 100gp migrated to 10000cp + 50cp

    def test_spend_gold(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_gold("Hero", -30)
        assert result["current_gold"] == 9970  # 10000cp - 30cp

    def test_gold_clamps_at_zero_not_negative(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_gold("Hero", -9999999)
        assert result["current_gold"] == 0

    def test_gold_show_without_amount(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_gold("Hero")
        assert result["success"] is True
        assert result["money"] == 10000  # 100gp = 10000cp

    def test_gold_persisted(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        mgr.modify_gold("Hero", +25)
        world = json.loads((camp / "world.json").read_text())
        char = world["nodes"]["player:active"]["data"]
        assert char["money"] == 10025  # 10000cp + 25cp

    def test_string_amount_gp(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_money("Hero", "5g")
        assert result["current_gold"] == 10500  # 10000 + 500cp

    def test_string_negative_amount(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.modify_money("Hero", "-100")
        assert result["current_gold"] == 9900  # 10000 - 100cp


class TestModifyXp:
    def test_xp_gained(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.award_xp("Hero", 150)
        assert result["success"] is True
        assert result["current_xp"] == 150
        assert result["xp_gained"] == 150

    def test_xp_level_up(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.award_xp("Hero", 300)
        assert result["level_up"] is True
        assert result["new_level"] == 2

    def test_xp_no_level_up_below_threshold(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        result = mgr.award_xp("Hero", 100)
        assert result["level_up"] is False
        assert result["new_level"] == 1

    def test_xp_persisted(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        mgr.award_xp("Hero", 200)
        world = json.loads((camp / "world.json").read_text())
        char = world["nodes"]["player:active"]["data"]
        assert char["xp"]["current"] == 200


class TestGetPlayer:
    def test_get_player_returns_data(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        char = mgr.get_player("Hero")
        assert char is not None
        assert char["name"] == "Hero"

    def test_get_player_none_uses_active(self, tmp_path):
        ws, camp = make_campaign(tmp_path)
        mgr = PlayerManager(ws)
        char = mgr.get_player(None)
        assert char is not None
        assert char["name"] == "Hero"

    def test_get_player_no_active_character_returns_none(self, tmp_path):
        ws, camp = make_campaign(tmp_path, overview_extra={"current_character": None})
        world = json.loads((camp / "world.json").read_text())
        del world["nodes"]["player:active"]
        (camp / "world.json").write_text(json.dumps(world))
        mgr = PlayerManager(ws)
        result = mgr.get_player(None)
        assert result is None
