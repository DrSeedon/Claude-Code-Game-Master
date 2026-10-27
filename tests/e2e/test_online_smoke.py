"""tools/e2e_online.py against a local screen server (no nginx: --local) with a stub master."""

import importlib.util
import json
from pathlib import Path

import pytest

from lib.screen import cli
from e2e_support import PASSWORD, Master, make_art

pytestmark = pytest.mark.e2e
SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "e2e_online.py"


def load_script():
    spec = importlib.util.spec_from_file_location("e2e_online", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_script_with_action(make_table, monkeypatch, capsys):
    table = make_table(gated=True)
    art = make_art(table.root / "a.png", ("#223344", "#aa8844"))
    cli.set_act(table.sdir, art, "Smoke Act", kicker="K", place="P")
    cli.set_turn(table.sdir, {"blocks": ["<p>One.</p>"], "question": "Go?", "options": ["Yes"]}, answered=0)
    master = Master(table.sdir, [lambda ev: (cli.set_act(table.sdir, art, "Second Act"),
                                             cli.set_turn(table.sdir, {"blocks": ["<p>Two.</p>"], "question": "Next?", "options": ["A", "B"]},
                                                          answered=ev["id"]))])
    table.start({})
    master.start()
    master.release()
    monkeypatch.setenv("DM_E2E_PASSWORD", PASSWORD)
    try:
        code = load_script().main(["--url", table.url, "--local", "--action", "I wait", "--who", "Aria", "--timeout", "20", "--expect-act-change"])
    finally:
        master.stop.set()
        master.join(5)
    out = capsys.readouterr().out
    summary = json.loads(out)
    assert code == 0 and summary["ok"], out
    assert summary["answer"]["options"] == 2 and summary["answer"]["act_title"] == "Second Act" and summary["answer"]["music"] is False
    assert PASSWORD not in out


def test_smoke_script_without_password(monkeypatch, capsys):
    monkeypatch.delenv("DM_E2E_PASSWORD", raising=False)
    assert load_script().main(["--url", "http://127.0.0.1:1"]) == 2
