from concurrent.futures import ThreadPoolExecutor

import pytest

from lib.screen import inbox


def test_append_assigns_increasing_ids(tmp_path):
    first = inbox.append_event(tmp_path, "Максим", "button", "1. Показать товар")
    second = inbox.append_event(tmp_path, "Катя", "voice", "Давайте выгрузим")

    assert (first["id"], second["id"]) == (1, 2)
    assert second["who"] == "Катя" and second["source"] == "voice"


def test_read_events_after_id(tmp_path):
    for i in range(3):
        inbox.append_event(tmp_path, "Оба", "text", f"ход {i}")

    assert [e["text"] for e in inbox.read_events(tmp_path, after_id=1)] == ["ход 1", "ход 2"]


def test_read_events_without_file_is_empty(tmp_path):
    assert inbox.read_events(tmp_path) == []


def test_concurrent_appends_keep_unique_ids(tmp_path):
    with ThreadPoolExecutor(8) as pool:
        events = list(pool.map(lambda i: inbox.append_event(tmp_path, "Оба", "text", f"t{i}"), range(40)))

    assert sorted(e["id"] for e in events) == list(range(1, 41))


def test_rejects_empty_text(tmp_path):
    with pytest.raises(ValueError):
        inbox.append_event(tmp_path, "Оба", "text", "   ")


def test_rejects_unknown_source(tmp_path):
    with pytest.raises(ValueError):
        inbox.append_event(tmp_path, "Оба", "telepathy", "привет")


def test_text_is_trimmed_and_limited(tmp_path):
    event = inbox.append_event(tmp_path, "Оба", "text", "  " + "а" * 5000 + "  ")

    assert len(event["text"]) == inbox.MAX_TEXT


def test_format_line_is_one_readable_line(tmp_path):
    event = inbox.append_event(tmp_path, "Максим", "voice", "Показать товар\nи цену")

    line = inbox.format_line(event)

    assert "\n" not in line
    assert line.startswith("[screen #1] Максим (voice): ")
    assert "Показать товар и цену" in line
