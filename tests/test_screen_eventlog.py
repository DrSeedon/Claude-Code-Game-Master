import json
import threading
from datetime import datetime, timedelta, timezone

import pytest

from lib.screen import eventlog


def test_log_writes_one_json_line_with_time_and_kind(tmp_path):
    entry = eventlog.log(tmp_path, "turn", id=3, blocks=["<p>Текст</p>"])

    files = list((tmp_path / "log").glob("*.jsonl"))
    assert len(files) == 1
    line = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert line["kind"] == "turn" and line["id"] == 3 and line["blocks"] == ["<p>Текст</p>"]
    assert line["ts"].endswith("Z") and entry["kind"] == "turn"


def test_secrets_never_reach_the_log(tmp_path):
    eventlog.log(tmp_path, "http", headers={"xi-api-key": "sk_" + "a" * 48, "X-Screen-Token": "tok", "Authorization": "Token abc"},
                 url="/audio/x.mp3?token=SECRETVALUE123&v=1", note="key sk_" + "b" * 48 + " leaked", deepgram="0123456789abcdef0123456789abcdef01234567")

    text = (next((tmp_path / "log").glob("*.jsonl"))).read_text()
    for secret in ("sk_" + "a" * 48, "sk_" + "b" * 48, "SECRETVALUE123", "0123456789abcdef0123456789abcdef01234567", "Token abc"):
        assert secret not in text
    assert "[redacted]" in text


def test_a_broken_log_never_breaks_the_app(tmp_path):
    blocker = tmp_path / "log"
    blocker.write_text("a file where the folder should be")

    assert eventlog.log(tmp_path, "turn", id=1) is None


def test_read_filters_by_kind_time_errors_and_tail(tmp_path):
    for i in range(5):
        eventlog.log(tmp_path, "tts", n=i)
    eventlog.log(tmp_path, "stt", text="привет")
    eventlog.log(tmp_path, "error", message="boom")

    assert [e["n"] for e in eventlog.read(tmp_path, kinds={"tts"}, tail=2)] == [3, 4]
    assert [e["kind"] for e in eventlog.read(tmp_path, errors=True)] == ["error"]
    assert eventlog.read(tmp_path, since=timedelta(seconds=-5)) == []
    assert len(eventlog.read(tmp_path)) == 7


def test_entries_are_split_by_day_and_read_across_days(tmp_path):
    (tmp_path / "log").mkdir()
    old = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    (tmp_path / "log" / f"{old}.jsonl").write_text(json.dumps({"ts": "2000-01-01T00:00:00.000Z", "kind": "old"}) + "\n")
    eventlog.log(tmp_path, "new")

    assert [e["kind"] for e in eventlog.read(tmp_path)] == ["old", "new"]


def test_concurrent_writers_keep_every_line_intact(tmp_path):
    def work(i):
        for j in range(25):
            eventlog.log(tmp_path, "tts", worker=i, j=j, pad="x" * 400)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert len(eventlog.read(tmp_path)) == 150


def test_summary_totals_spending_listening_and_errors(tmp_path):
    eventlog.log(tmp_path, "tts", credits=30, chars=61, cached=False)
    eventlog.log(tmp_path, "tts", credits=0, chars=40, cached=True)
    eventlog.log(tmp_path, "stt", seconds=12.5, words=[{"word": "а"}])
    eventlog.log(tmp_path, "error", message="x")
    eventlog.log(tmp_path, "turn", id=1)

    s = eventlog.summary(tmp_path)

    assert s["events"] == 5 and s["tts_credits"] == 30 and s["tts_cached"] == 1 and s["stt_seconds"] == 12.5 and s["errors"] == 1
    assert s["kinds"]["turn"] == 1


def test_world_snapshot_collects_the_values_worth_debugging(tmp_path):
    (tmp_path / "campaign-overview.json").write_text(json.dumps({"current_date": "10 июля, 1805 г.", "precise_time": "20:21",
                                                                  "player_position": {"current_location": "Двор"}}))
    nodes = {"player:active": {"type": "player", "name": "Максим", "data": {"hp": {"current": 9, "max": 9}, "money": 21500}},
             "npc:k": {"type": "npc", "name": "Катя", "data": {"party_member": True, "hp": {"current": 8, "max": 8}}},
             "quest:q": {"type": "quest", "name": "Q", "data": {"status": "active", "objectives": [{"text": "a", "done": True}, {"text": "b", "done": False}]}}}
    (tmp_path / "world.json").write_text(json.dumps({"nodes": nodes, "edges": []}))

    snap = eventlog.world_snapshot(tmp_path)

    assert snap["time"] == "20:21" and snap["location"] == "Двор" and snap["player"] == {"name": "Максим", "hp": "9/9", "money": 21500}
    assert snap["party"] == [{"name": "Катя", "hp": "8/8"}] and snap["quests"] == [{"name": "Q", "done": 1, "total": 2}]
