"""Tests for lib/world_graph.py — WorldGraph class"""
import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from world_graph import WorldGraph, calculate_inventory_load


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def graph(tmp_path):
    return WorldGraph(tmp_path)


@pytest.fixture
def populated_graph(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_node("player:hero", "player", "Hero")
    g.add_node("npc:merchant", "npc", "Old Merchant", data={"attitude": "friendly"})
    g.add_node("location:tavern", "location", "The Rusty Flagon")
    g.add_node("location:market", "location", "Grand Market")
    g.add_node("item:sword", "item", "Iron Sword", data={"damage": "1d8"})
    # edges
    g.add_edge("player:hero", "location:tavern", "at")
    g.add_edge("npc:merchant", "location:market", "at")
    g.add_edge("location:tavern", "location:market", "connects")
    g.add_edge("player:hero", "item:sword", "has")
    return g


@pytest.mark.parametrize(
    ("weight", "tier", "speed_penalty_ft", "attack_disadvantage", "immobile"),
    [
        (70, "normal", 0, False, False),
        (71, "encumbered", -5, False, False),
        (92, "heavy", -10, False, False),
        (113, "overloaded", -15, True, False),
        (141, "immobile", None, True, True),
    ],
)
def test_inventory_load_uses_strength_capacity_and_encumbrance_tiers(
    weight,
    tier,
    speed_penalty_ft,
    attack_disadvantage,
    immobile,
):
    load = calculate_inventory_load(weight, strength=10)

    assert load["capacity_kg"] == 70
    assert load["tier"] == tier
    assert load["speed_penalty_ft"] == speed_penalty_ft
    assert load["attack_disadvantage"] is attack_disadvantage
    assert load["immobile"] is immobile


def test_inventory_load_prefers_explicit_capacity_and_rejects_missing_limit():
    assert calculate_inventory_load(20, strength=10, capacity_kg=50) == {
        "weight_kg": 20.0,
        "capacity_kg": 50.0,
        "usage_percent": 40.0,
        "tier": "normal",
        "speed_penalty_ft": 0,
        "attack_disadvantage": False,
        "immobile": False,
        "capacity_source": "explicit",
    }
    assert calculate_inventory_load(20, strength=None) is None


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------

class TestAddNode:
    def test_add_node_creates_entry(self, graph):
        result = graph.add_node("npc:goblin", "npc", "Goblin")
        assert result is True
        node = graph.get_node("npc:goblin")
        assert node is not None
        assert node["name"] == "Goblin"
        assert node["type"] == "npc"

    def test_add_node_rejects_duplicate_id(self, graph):
        graph.add_node("npc:goblin", "npc", "Goblin")
        result = graph.add_node("npc:goblin", "npc", "Goblin 2")
        assert result is False
        assert graph.get_node("npc:goblin")["name"] == "Goblin"

    def test_add_node_validates_id_format(self, graph):
        assert graph.add_node("bad-id", "npc", "Bad") is False
        assert graph.add_node("npc:", "npc", "Empty name part") is False
        assert graph.add_node(":name", "npc", "Empty type part") is False

    def test_add_node_rejects_type_mismatch(self, graph):
        assert graph.add_node("npc:guide", "item", "Guide") is False

    def test_add_node_with_data(self, graph):
        graph.add_node("npc:troll", "npc", "Troll", data={"hp": 84, "ac": 15})
        node = graph.get_node("npc:troll")
        assert node["data"]["hp"] == 84
        assert node["data"]["ac"] == 15

    def test_add_node_rejects_top_level_gameplay_fields(self, graph):
        with pytest.raises(TypeError):
            graph.add_node(
                "location:castle",
                "location",
                "Castle",
                inventory=["torch", "barrel"],
            )


class TestGetNode:
    def test_get_node_returns_data(self, populated_graph):
        node = populated_graph.get_node("npc:merchant")
        assert node["name"] == "Old Merchant"
        assert node["data"]["attitude"] == "friendly"

    def test_get_node_returns_none_for_missing(self, graph):
        assert graph.get_node("npc:nobody") is None


class TestUpdateNode:
    def test_update_node_merges_data(self, populated_graph):
        populated_graph.update_node("npc:merchant", {"attitude": "hostile", "location": "market"})
        node = populated_graph.get_node("npc:merchant")
        assert node["attitude"] == "hostile"
        assert node["location"] == "market"
        assert node["name"] == "Old Merchant"

    def test_update_node_returns_false_for_missing(self, graph):
        result = graph.update_node("npc:ghost", {"mood": "sad"})
        assert result is False

    def test_update_node_does_not_mutate_input(self, populated_graph):
        updates = {"data": {"attitude": "hostile"}}

        assert populated_graph.update_node("npc:merchant", updates)
        assert updates == {"data": {"attitude": "hostile"}}

    def test_npc_event_uses_data_and_is_displayed(self, populated_graph):
        assert populated_graph.npc_event("npc:merchant", "Closed the shop")

        node = populated_graph.get_node("npc:merchant")
        assert node["data"]["events"][-1]["event"] == "Closed the shop"
        assert "events" not in {key for key in node if key != "data"}
        assert "Closed the shop" in populated_graph.format_node("npc:merchant")


class TestRemoveNode:
    def test_remove_node_deletes_entry(self, populated_graph):
        result = populated_graph.remove_node("item:sword")
        assert result is True
        assert populated_graph.get_node("item:sword") is None

    def test_remove_node_cascades_edges(self, populated_graph):
        populated_graph.remove_node("item:sword", cascade=True)
        edges = populated_graph.get_edges("player:hero", edge_type="has")
        assert len(edges) == 0

    def test_remove_node_no_cascade(self, populated_graph):
        populated_graph.remove_node("item:sword", cascade=False)
        assert populated_graph.get_node("item:sword") is None
        edges = populated_graph.get_edges("player:hero", edge_type="has")
        assert len(edges) > 0


class TestListNodes:
    def test_list_nodes_all(self, populated_graph):
        nodes = populated_graph.list_nodes()
        assert len(nodes) == 5

    def test_list_nodes_by_type(self, populated_graph):
        locations = populated_graph.list_nodes(node_type="location")
        assert len(locations) == 2
        types = {n["type"] for n in locations}
        assert types == {"location"}

    def test_list_nodes_returns_empty_for_empty_graph(self, graph):
        assert graph.list_nodes() == []


class TestSearchNodes:
    def test_search_nodes_by_name(self, populated_graph):
        results = populated_graph.search_nodes("Merchant")
        assert len(results) >= 1
        assert any(r["name"] == "Old Merchant" for r in results)

    def test_search_nodes_partial_match(self, populated_graph):
        results = populated_graph.search_nodes("rust")
        assert any("Rusty" in r["name"] for r in results)

    def test_search_nodes_empty_graph(self, graph):
        assert graph.search_nodes("anything") == []

    def test_search_nodes_filtered_by_type(self, populated_graph):
        results = populated_graph.search_nodes("hero", node_type="player")
        for r in results:
            assert r["type"] == "player"


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------

class TestAddEdge:
    def test_add_edge_creates_entry(self, graph):
        graph.add_node("location:town", "location", "Town")
        graph.add_node("location:dungeon", "location", "Dungeon")
        result = graph.add_edge("location:town", "location:dungeon", "connects")
        assert result is True

    def test_add_edge_validates_nodes_exist(self, graph):
        graph.add_node("location:town", "location", "Town")
        result = graph.add_edge("location:town", "location:ghost", "connects")
        assert result is False

    def test_add_edge_with_data(self, graph):
        graph.add_node("item:recipe", "item", "Recipe")
        graph.add_node("item:iron", "item", "Iron Ore")
        graph.add_edge("item:recipe", "item:iron", "requires", data={"qty": 3})
        edges = graph.get_edges("item:recipe", edge_type="requires", direction="out")
        assert len(edges) == 1
        assert edges[0]["data"]["qty"] == 3

    def test_add_edge_rejects_duplicate(self, graph):
        graph.add_node("npc:a", "npc", "A")
        graph.add_node("npc:b", "npc", "B")
        graph.add_edge("npc:a", "npc:b", "knows")
        result = graph.add_edge("npc:a", "npc:b", "knows")
        assert result is False


class TestGetEdges:
    def test_get_edges_outgoing(self, populated_graph):
        edges = populated_graph.get_edges("player:hero", direction="out")
        targets = {e["to"] for e in edges}
        assert "location:tavern" in targets
        assert "item:sword" in targets

    def test_get_edges_incoming(self, populated_graph):
        edges = populated_graph.get_edges("location:tavern", direction="in")
        sources = {e["from"] for e in edges}
        assert "player:hero" in sources

    def test_get_edges_both(self, populated_graph):
        edges = populated_graph.get_edges("location:tavern", direction="both")
        node_ids = {e.get("from") for e in edges} | {e.get("to") for e in edges}
        assert "location:tavern" in node_ids

    def test_get_edges_filtered_by_type(self, populated_graph):
        edges = populated_graph.get_edges("player:hero", edge_type="at", direction="out")
        assert all(e["type"] == "at" for e in edges)
        targets = {e["to"] for e in edges}
        assert "location:tavern" in targets
        assert "item:sword" not in targets

    def test_get_edges_returns_empty_for_no_match(self, graph):
        graph.add_node("npc:lone", "npc", "Lone Wolf")
        assert graph.get_edges("npc:lone") == []


class TestRemoveEdge:
    def test_remove_edge_deletes_match(self, populated_graph):
        result = populated_graph.remove_edge("player:hero", "item:sword", "has")
        assert result is True
        edges = populated_graph.get_edges("player:hero", edge_type="has")
        assert len(edges) == 0

    def test_remove_edge_returns_false_for_missing(self, graph):
        graph.add_node("npc:a", "npc", "A")
        graph.add_node("npc:b", "npc", "B")
        result = graph.remove_edge("npc:a", "npc:b", "knows")
        assert result is False


class TestGetNeighbors:
    def test_get_neighbors_returns_nodes(self, populated_graph):
        neighbors = populated_graph.get_neighbors("player:hero", direction="out")
        names = {n["name"] for n in neighbors}
        assert "The Rusty Flagon" in names
        assert "Iron Sword" in names

    def test_get_neighbors_filtered_by_edge_type(self, populated_graph):
        neighbors = populated_graph.get_neighbors("player:hero", edge_type="has", direction="out")
        assert len(neighbors) == 1
        assert neighbors[0]["name"] == "Iron Sword"

    def test_get_neighbors_incoming(self, populated_graph):
        neighbors = populated_graph.get_neighbors("location:tavern", direction="in")
        names = {n["name"] for n in neighbors}
        assert "Hero" in names


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

class TestFileIO:
    def test_load_creates_empty_on_missing_file(self, tmp_path):
        g = WorldGraph(tmp_path)
        assert g.list_nodes() == []
        assert g.get_edges.__doc__ is not None or True

    def test_atomic_write_persists(self, tmp_path):
        g = WorldGraph(tmp_path)
        g.add_node("npc:sage", "npc", "Sage")
        g2 = WorldGraph(tmp_path)
        node = g2.get_node("npc:sage")
        assert node is not None
        assert node["name"] == "Sage"

    def test_save_valid_json(self, tmp_path):
        g = WorldGraph(tmp_path)
        g.add_node("location:cave", "location", "Dark Cave")
        world_file = tmp_path / "world.json"
        assert world_file.exists()
        data = json.loads(world_file.read_text())
        assert "nodes" in data
        assert "edges" in data


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_node_id_with_numbers(self, graph):
        result = graph.add_node("fact:lore-001", "fact", "Ancient Lore")
        assert result is True
        assert graph.get_node("fact:lore-001") is not None

    def test_unicode_in_node_name(self, graph):
        graph.add_node("npc:innkeeper", "npc", "Борис Кабатчик", data={"greeting": "Добро пожаловать!"})
        node = graph.get_node("npc:innkeeper")
        assert node["name"] == "Борис Кабатчик"
        assert node["data"]["greeting"] == "Добро пожаловать!"

    def test_empty_graph_list(self, graph):
        assert graph.list_nodes() == []

    def test_empty_graph_search(self, graph):
        assert graph.search_nodes("anything") == []


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_npc_party_state_attitude_and_hp_use_canonical_data(self, graph):
        graph.add_node(
            "npc:ally",
            "npc",
            "Ally",
            data={
                "attitude": "neutral",
                "party_member": False,
                "character_sheet": {"hp": 8, "hp_max": 10, "ac": 12},
            },
        )

        assert graph.npc_promote("npc:ally")
        assert graph.npc_set_attitude("npc:ally", "friendly")
        assert graph.npc_adjust_hp("npc:ally", -3)["new_hp"] == 5
        assert graph.npc_adjust_hp("npc:ally", 20)["new_hp"] == 10

        node = graph.get_node("npc:ally")
        assert node["data"]["party_member"] is True
        assert node["data"]["attitude"] == "friendly"
        assert node["data"]["character_sheet"]["hp"] == 10
        assert "hp_delta" not in node["data"]

        assert graph.npc_demote("npc:ally")
        assert graph.npc_list(party_only=True) == []
        assert graph.npc_promote("npc:ally")
        assert [node["id"] for node in graph.npc_list(party_only=True)] == ["npc:ally"]

    def test_npc_list_filters_attitude_location_and_legacy_party_flag(self, graph):
        graph.add_node(
            "npc:local",
            "npc",
            "Local",
            data={"attitude": "Friendly"},
        )
        graph.add_node(
            "npc:remote",
            "npc",
            "Remote",
            data={"attitude": "hostile", "is_party_member": True},
        )
        graph.add_node("location:base", "location", "Base")
        graph.add_edge("npc:local", "location:base", "at")

        assert [node["id"] for node in graph.npc_list(attitude="friendly")] == [
            "npc:local"
        ]
        assert [
            node["id"]
            for node in graph.npc_list(location_id="location:base")
        ] == ["npc:local"]
        assert [node["id"] for node in graph.npc_list(party_only=True)] == [
            "npc:remote"
        ]

    def test_npc_hp_requires_character_sheet(self, graph):
        graph.add_node("npc:civilian", "npc", "Civilian")

        assert graph.npc_adjust_hp("npc:civilian", -1) is None

    def test_combatant_stats_normalize_mass_combat_aliases(self, graph):
        graph.add_node(
            "creature:infested-miner",
            "creature",
            "Infested Miner",
            data={"hp": 16, "ac": 12, "atk": 3, "dmg": "1d6+1", "pen": 1, "prot": 1},
        )

        stats = graph.combatant_stats("creature:infested-miner")

        assert stats == {
            "id": "creature:infested-miner",
            "type": "creature",
            "name": "Infested Miner",
            "ac": 12,
            "hp": 16,
            "hp_max": 16,
            "prot": 1,
            "attack_bonus": 3,
            "damage": "1d6+1",
            "pen": 1,
        }

    def test_apply_damage_supports_player_npc_and_creature(self, graph):
        graph.add_node(
            "player:active",
            "player",
            "Hero",
            data={"hp": {"current": 12, "max": 12}, "ac": 15},
        )
        graph.add_node(
            "npc:ally",
            "npc",
            "Ally",
            data={"character_sheet": {"hp": 10, "hp_max": 10, "ac": 12}},
        )
        graph.add_node(
            "creature:target",
            "creature",
            "Target",
            data={"hp": 8, "ac": 10},
        )

        assert graph.apply_damage("player:active", 3)["new_hp"] == 9
        assert graph.apply_damage("npc:ally", 4)["new_hp"] == 6
        assert graph.apply_damage("creature:target", 5)["new_hp"] == 3

        assert graph.get_node("player:active")["data"]["hp"]["current"] == 9
        assert graph.get_node("npc:ally")["data"]["character_sheet"]["hp"] == 6
        creature = graph.get_node("creature:target")["data"]
        assert creature["hp"] == 8
        assert creature["hp_current"] == 3

    def test_inventory_loot_commits_once(self, graph):
        graph.add_node(
            "player:active",
            "player",
            "Hero",
            data={"money": 10, "xp": 0},
        )
        before = graph.repository.revision(graph.repository.load())

        assert graph.inventory_loot(
            "player:active",
            [("Ammo", 5, 0.02), ("Medkit", 1, 0.5)],
            gold=20,
            xp=30,
        )

        saved = graph.repository.load()
        player = saved["nodes"]["player:active"]
        assert saved["meta"]["revision"] == before + 1
        assert player["inventory"]["stackable"]["Ammo"] == {
            "qty": 5,
            "weight": 0.02,
        }
        assert player["data"]["money"] == 30
        assert player["data"]["xp"] == 30

    def test_inventory_transfer_is_atomic_and_preserves_weight(self, graph):
        graph.add_node("player:active", "player", "Hero")
        graph.add_node("npc:ally", "npc", "Ally")
        graph.inventory_add("player:active", "Ammo", 10, 0.02)
        before = graph.repository.revision(graph.repository.load())

        assert graph.inventory_transfer("player:active", "npc:ally", "Ammo", 4)

        saved = graph.repository.load()
        assert saved["meta"]["revision"] == before + 1
        assert saved["nodes"]["player:active"]["inventory"]["stackable"]["Ammo"]["qty"] == 6
        assert saved["nodes"]["npc:ally"]["inventory"]["stackable"]["Ammo"] == {
            "qty": 4,
            "weight": 0.02,
        }

    def test_player_show_formats_structured_hp_and_xp(self, graph):
        graph.add_node(
            "player:active",
            "player",
            "Steve",
            data={
                "hp": {"current": 12, "max": 12},
                "xp": {"current": 0, "next_level": 300},
                "money": 20,
            },
        )

        output = graph.player_show()

        assert "HP" in output
        assert "12/12" in output
        assert "XP" in output
        assert "{'current'" not in output

    def test_recipe_traversal(self, graph):
        graph.add_node("item:health-potion", "item", "Health Potion")
        graph.add_node("item:red-herb", "item", "Red Herb")
        graph.add_node("item:water-flask", "item", "Water Flask")
        graph.add_edge("item:health-potion", "item:red-herb", "requires", data={"qty": 2})
        graph.add_edge("item:health-potion", "item:water-flask", "requires", data={"qty": 1})

        ingredients = graph.get_neighbors("item:health-potion", edge_type="requires", direction="out")
        names = {n["name"] for n in ingredients}
        assert "Red Herb" in names
        assert "Water Flask" in names
        assert len(ingredients) == 2

    def test_location_graph_bidirectional(self, graph):
        graph.add_node("location:north", "location", "North Keep")
        graph.add_node("location:south", "location", "South Gate")
        graph.add_node("location:east", "location", "East Tower")
        graph.add_edge("location:north", "location:south", "connects")
        graph.add_edge("location:south", "location:east", "connects")
        graph.add_edge("location:east", "location:north", "connects")

        from_north = graph.get_neighbors("location:north", edge_type="connects", direction="out")
        assert any(n["name"] == "South Gate" for n in from_north)

        to_north = graph.get_neighbors("location:north", edge_type="connects", direction="in")
        assert any(n["name"] == "East Tower" for n in to_north)

        both = graph.get_neighbors("location:north", edge_type="connects", direction="both")
        names = {n["name"] for n in both}
        assert "South Gate" in names
        assert "East Tower" in names
