
import json

from lib.session_manager import SessionManager

EMPTY_WORLD = {
    "meta": {"version": 2, "schema": "graph"},
    "nodes": {},
    "edges": []
}


def make_world_state(tmp_path, overview_extra=None, with_player=True):
    ws = tmp_path / "world-state"
    camp = ws / "campaigns" / "test-campaign"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("test-campaign")

    overview = {
        "campaign_name": "Test Campaign",
        "time_of_day": "Day",
        "current_date": "Day 1",
        "current_character": "Hero",
    }
    if overview_extra:
        overview.update(overview_extra)
    (camp / "campaign-overview.json").write_text(
        json.dumps(overview, ensure_ascii=False)
    )

    world = dict(EMPTY_WORLD)
    world["nodes"] = {}
    if with_player:
        world["nodes"]["player:active"] = {
            "type": "player",
            "name": "Hero",
            "data": {
                "name": "Hero",
                "level": 1,
                "hp": {"current": 20, "max": 20},
                "gold": 100,
                "money": 100,
                "current_location": "",
            }
        }
    (camp / "world.json").write_text(json.dumps(world, ensure_ascii=False))

    return str(ws), camp


class TestMoveParty:
    def test_move_updates_current_location(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        result = mgr.move_party("Tavern")
        assert result["current_location"] == "Tavern"

    def test_move_records_previous_location(self, tmp_path):
        ws, camp = make_world_state(tmp_path, overview_extra={
            "player_position": {"current_location": "Forest"}
        })
        mgr = SessionManager(ws)
        result = mgr.move_party("Castle")
        assert result["previous_location"] == "Forest"

    def test_move_prefers_world_graph_location_over_stale_metadata(self, tmp_path):
        ws, camp = make_world_state(tmp_path, overview_extra={
            "player_position": {"current_location": "Stale Camp"}
        })
        world = json.loads((camp / "world.json").read_text())
        world["nodes"]["player:active"]["data"]["current_location"] = "Graph Camp"
        world["nodes"]["location:graph-camp"] = {
            "type": "location",
            "name": "Graph Camp",
            "data": {"description": ""},
        }
        (camp / "world.json").write_text(json.dumps(world))

        result = SessionManager(ws).move_party("Forward Base")

        assert result["previous_location"] == "Graph Camp"
        saved = json.loads((camp / "world.json").read_text())
        connections = {
            (edge["from"], edge["to"])
            for edge in saved["edges"]
            if edge["type"] == "connected"
        }
        assert ("location:graph-camp", "location:forward-base") in connections

    def test_move_persists_to_campaign_file(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        mgr.move_party("Dungeon")
        data = json.loads((camp / "campaign-overview.json").read_text())
        assert data["player_position"]["current_location"] == "Dungeon"

    def test_move_updates_player_node_location(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        mgr.move_party("Marketplace")
        world = json.loads((camp / "world.json").read_text())
        assert world["nodes"]["player:active"]["data"]["current_location"] == "Marketplace"

    def test_move_auto_creates_location_in_world_graph(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        mgr.move_party("New Place")
        world = json.loads((camp / "world.json").read_text())
        location_nodes = [n for n in world["nodes"].values() if n.get("type") == "location"]
        names = [n["name"] for n in location_nodes]
        assert "New Place" in names

    def test_move_creates_bidirectional_connection(self, tmp_path):
        ws, camp = make_world_state(tmp_path, overview_extra={
            "player_position": {"current_location": "Town"}
        })
        world = json.loads((camp / "world.json").read_text())
        world["nodes"]["location:town"] = {
            "type": "location", "name": "Town",
            "data": {"description": ""}
        }
        (camp / "world.json").write_text(json.dumps(world))

        mgr = SessionManager(ws)
        mgr.move_party("Forest")

        world2 = json.loads((camp / "world.json").read_text())
        edges = world2["edges"]
        connected_pairs = {(e["from"], e["to"]) for e in edges if e["type"] == "connected"}
        assert ("location:town", "location:forest") in connected_pairs
        assert ("location:forest", "location:town") in connected_pairs

    def test_move_relocates_party_member_npcs_only(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        world = json.loads((camp / "world.json").read_text())
        world["nodes"].update({
            "npc:companion": {
                "type": "npc", "name": "Companion",
                "data": {"party_member": True},
            },
            "npc:legacy-companion": {
                "type": "npc", "name": "Legacy Companion",
                "data": {"is_party_member": True},
            },
            "npc:shopkeeper": {
                "type": "npc", "name": "Shopkeeper",
                "data": {"party_member": False},
            },
            "location:old-camp": {
                "type": "location", "name": "Old Camp", "data": {},
            },
        })
        world["edges"] = [
            {"from": "npc:companion", "to": "location:old-camp", "type": "at"},
            {"from": "npc:legacy-companion", "to": "location:old-camp", "type": "at"},
            {"from": "npc:shopkeeper", "to": "location:old-camp", "type": "at"},
        ]
        (camp / "world.json").write_text(json.dumps(world))

        result = SessionManager(ws).move_party("New Camp")

        moved_world = json.loads((camp / "world.json").read_text())
        at_edges = {
            (edge["from"], edge["to"])
            for edge in moved_world["edges"]
            if edge["type"] == "at"
        }
        assert ("npc:companion", "location:new-camp") in at_edges
        assert ("npc:legacy-companion", "location:new-camp") in at_edges
        assert ("npc:shopkeeper", "location:old-camp") in at_edges
        assert set(result["moved_party_members"]) == {
            "npc:companion", "npc:legacy-companion"
        }


class TestGetContext:
    def test_get_full_context_returns_string(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        ctx = mgr.get_full_context()
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_get_full_context_contains_campaign_name(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        ctx = mgr.get_full_context()
        assert "Test Campaign" in ctx

    def test_get_full_context_contains_character_info(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        ctx = mgr.get_full_context()
        assert "Hero" in ctx

    def test_get_full_context_contains_play_mode_and_visuals(self, tmp_path):
        ws, camp = make_world_state(tmp_path, overview_extra={
            "play_mode": "narrative",
            "cinematic_visuals": {
                "enabled": True,
                "frequency": "occasional",
                "aspect_ratio": "16:9",
            },
        })
        mgr = SessionManager(ws)

        ctx = mgr.get_full_context()

        assert "Play mode: narrative" in ctx
        assert "Cinematic visuals: enabled (occasional, 16:9)" in ctx

    def test_get_status_returns_dict(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        status = mgr.get_status()
        assert isinstance(status, dict)
        assert "locations_count" in status
        assert "npcs_count" in status

    def test_count_items_from_worldgraph(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        world = json.loads((camp / "world.json").read_text())
        world["nodes"]["npc:goblin"] = {"type": "npc", "name": "Goblin", "data": {}}
        world["nodes"]["npc:troll"] = {"type": "npc", "name": "Troll", "data": {}}
        (camp / "world.json").write_text(json.dumps(world))

        mgr = SessionManager(ws)
        status = mgr.get_status()
        assert status["npcs_count"] == 2


class TestSessionStartEnd:
    def test_start_session_returns_summary(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        summary = mgr.start_session()
        assert isinstance(summary, dict)
        assert "timestamp" in summary

    def test_start_session_creates_log(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        mgr.start_session()
        log = camp / "session-log.md"
        assert log.exists()
        assert "Session Started:" in log.read_text()

    def test_end_session_logs_summary(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        mgr.start_session()
        mgr.end_session("Fought dragons and won")
        log = (camp / "session-log.md").read_text()
        assert "Fought dragons and won" in log

    def test_session_count_increments(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        mgr.start_session()
        assert mgr._get_session_number() == 1
        mgr.start_session()
        assert mgr._get_session_number() == 2


class TestSaveRestore:
    def test_create_save_includes_world(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        filename = mgr.create_save("test-save")
        save_path = camp / "saves" / filename
        save_data = json.loads(save_path.read_text())
        assert "world" in save_data["snapshot"]
        assert save_data["snapshot"]["world"] is not None

    def test_save_restore_includes_module_data(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        module_data = camp / "module-data"
        module_data.mkdir()
        state_file = module_data / "combat-state.json"
        state_file.write_text(json.dumps({"round": 4, "active": True}))
        mgr = SessionManager(ws)
        filename = mgr.create_save("with-modules")

        state_file.write_text(json.dumps({"round": 9, "active": True}))
        (module_data / "stale.json").write_text(json.dumps({"stale": True}))

        assert mgr.restore_save(filename) is True
        assert json.loads(state_file.read_text()) == {"round": 4, "active": True}
        assert not (module_data / "stale.json").exists()

    def test_restore_save_restores_world(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        filename = mgr.create_save("restore-test")

        world = json.loads((camp / "world.json").read_text())
        world["nodes"]["location:test"] = {"type": "location", "name": "Test", "data": {}}
        (camp / "world.json").write_text(json.dumps(world))

        mgr.restore_save(filename)
        restored = json.loads((camp / "world.json").read_text())
        assert "location:test" not in restored["nodes"]

    def test_restore_rejects_legacy_flat_files_without_writing(self, tmp_path):
        ws, camp = make_world_state(tmp_path)
        mgr = SessionManager(ws)
        before_world = (camp / "world.json").read_text()
        before_overview = (camp / "campaign-overview.json").read_text()

        save_data = {
            "name": "legacy",
            "created": "2024-01-01T00:00:00+00:00",
            "session_number": 1,
            "snapshot": {
                "campaign_overview": {"campaign_name": "Test Campaign"},
                "npcs": {"Goblin": {"attitude": "hostile"}},
                "locations": {},
                "facts": {},
                "consequences": {},
            }
        }
        save_path = camp / "saves" / "legacy.json"
        save_path.parent.mkdir(exist_ok=True)
        save_path.write_text(json.dumps(save_data))

        result = mgr.restore_save("legacy")
        assert result is False
        assert (camp / "world.json").read_text() == before_world
        assert (camp / "campaign-overview.json").read_text() == before_overview
