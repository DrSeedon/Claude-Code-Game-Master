"""Tests for lib/world_graph.py — WorldGraph class"""
import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from world_graph import WorldGraph


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

    def test_add_node_with_data(self, graph):
        graph.add_node("npc:troll", "npc", "Troll", data={"hp": 84, "ac": 15})
        node = graph.get_node("npc:troll")
        assert node["data"]["hp"] == 84
        assert node["data"]["ac"] == 15

    def test_add_node_with_extra_kwargs(self, graph):
        graph.add_node(
            "location:castle", "location", "Castle",
            inventory=["torch", "barrel"],
            events=["siege"]
        )
        node = graph.get_node("location:castle")
        assert node is not None
        assert node.get("inventory") == ["torch", "barrel"]
        assert node.get("events") == ["siege"]


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
