import json

from lib.screen import clock


def campaign(tmp_path, **overview):
    (tmp_path / "campaign-overview.json").write_text(json.dumps(overview))
    return tmp_path


def test_clock_follows_the_game_time(tmp_path):
    path = campaign(tmp_path, current_date="10 July, 1805 AD", precise_time="20:15",
                    player_position={"current_location": "Courtyard"})

    first = clock.world_clock(path)
    (path / "campaign-overview.json").write_text(json.dumps(
        {"current_date": "10 July, 1805 AD", "precise_time": "21:40", "player_position": {"current_location": "Salon"}}))
    second = clock.world_clock(path)

    assert "20:15" in first["text"] and "July" in first["text"] and first["location"] == "Courtyard"
    assert "21:40" in second["text"] and second["location"] == "Salon"


def test_clock_uses_the_campaign_calendar(tmp_path):
    path = campaign(tmp_path, current_date="3 Frost, 12 Era", precise_time="08:00",
                    calendar={"epoch": "Era", "months": [{"id": "frost", "name": "Frost", "days": 30}],
                              "weekdays": ["Moonday", "Sunday"], "year_zero_weekday": 0})

    assert "Frost" in clock.world_clock(path)["text"]


def test_clock_survives_unreadable_dates(tmp_path):
    path = campaign(tmp_path, current_date="sometime in autumn", precise_time="12:00")

    assert "12:00" in clock.world_clock(path)["text"]


def test_clock_without_overview_is_none(tmp_path):
    assert clock.world_clock(tmp_path) is None
