"""Page-script checks for the online screen: the party panel and the waiting state, run with node."""
import json
import shutil
import subprocess

import pytest

from lib.screen import server
from test_screen_server import _template_js


def _run(names, body):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = _template_js(names) + """
const ABIL_KEYS=['str','dex','con','int','wis','cha'];const t=k=>k;
""" + body
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def _heroes(party, character=None):
    views = {"character": character, "npcs": {"party": party}}
    return _run(["sheetHp", "hpPct", "realStats", "heroList"],
                f"const v={json.dumps(views)};console.log(JSON.stringify(heroList(v).map(h=>({{hp:h.hp,hpMax:h.hpMax,pct:hpPct(h),grid:!!h.stats}}))))")


def test_party_hp_object_shows_the_real_numbers_and_bar():
    out = _heroes([{"id": "a", "name": "A", "character_sheet": {"hp": {"current": 19, "max": 20}}}])

    assert out == [{"hp": 19, "hpMax": 20, "pct": 95, "grid": False}]


def test_party_hp_legacy_number_with_hp_max_still_works():
    out = _heroes([{"id": "a", "name": "A", "character_sheet": {"hp": 5, "hp_max": 10}}])

    assert out == [{"hp": 5, "hpMax": 10, "pct": 50, "grid": False}]


def test_placeholder_abilities_hide_the_grid_and_real_ones_show_it():
    flat = dict.fromkeys(["str", "dex", "con", "int", "wis", "cha"], 10)
    real = dict(flat, str=14)
    out = _heroes([{"id": "a", "name": "A", "character_sheet": {"stats": flat}},
                   {"id": "b", "name": "B", "character_sheet": {"stats": real}}],
                  {"name": "H", "hp": {"current": 3, "max": 4}, "stats": flat})

    assert [h["grid"] for h in out] == [False, False, True]
    assert out[0]["hp"] == 3 and out[0]["pct"] == 75


def test_an_offline_or_failed_master_clears_the_waiting_state():
    out = _run(["nextWaiting"], """
const turn={id:1,answered:0};
console.log(JSON.stringify([nextWaiting({turn,inbox_last:5,master:{state:'error'}},true),
  nextWaiting({turn,inbox_last:5,master:{state:'offline'}},false),
  nextWaiting({turn,inbox_last:5,master:{state:'thinking'}},false),
  nextWaiting({turn,inbox_last:0,master:{state:'idle'}},true),
  nextWaiting({inbox_last:0},false)]))""")

    assert out == [False, False, True, True, False]


def test_the_page_wires_the_waiting_rule_and_the_act_swap_clock():
    """The rules above are pure functions; these lines are where the page uses them."""
    page = server.TEMPLATE.read_text(encoding="utf-8")

    assert "S.waiting=nextWaiting(st,S.waiting);" in page
    # a new act's place and date show when the swap ends, not one state event later; one swap per act
    assert "renderAct(act);showClock(S.last||{});" in page and "S.last=st;" in page
    assert "st.act.id!==S.actSwap" in page
