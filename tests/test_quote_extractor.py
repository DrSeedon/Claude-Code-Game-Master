from lib.rag.quote_extractor import QuoteExtractor
from lib.world_graph import WorldGraph


class _VectorStore:
    def count(self):
        return 1


def test_quote_extractor_updates_world_graph_in_one_commit(tmp_path, monkeypatch):
    graph = WorldGraph(tmp_path)
    graph.add_node(
        "npc:marine",
        "npc",
        "Marine",
        {"context": ["Existing passage"]},
    )
    before_revision = graph.repository.revision(graph.repository.load())

    extractor = QuoteExtractor(str(tmp_path))
    extractor._vector_store = _VectorStore()
    monkeypatch.setattr(
        extractor,
        "extract_context_for_npc",
        lambda _name: ["Existing passage", "New source passage"],
    )

    assert extractor.enrich_all_npcs() == 1

    saved = graph.repository.load()
    assert saved["meta"]["revision"] == before_revision + 1
    assert saved["nodes"]["npc:marine"]["data"]["context"] == [
        "Existing passage",
        "New source passage",
    ]
