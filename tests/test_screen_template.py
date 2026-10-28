"""Page-script checks for the online screen: the party panel and the waiting state, run with node."""
import json
import os
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


# ---- the master console

FAKE_DOM = """
class El{constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.className='';this._text='';this.classList={add:c=>{this.className+=' '+c},remove:c=>{this.className=this.className.split(' ').filter(x=>x!==c).join(' ')}}}
  appendChild(c){this.children.push(c);return c}
  set textContent(v){this._text=String(v)}get textContent(){return this._text+this.children.map(c=>c.textContent).join('')}
  set innerHTML(v){throw new Error('innerHTML used: '+v)}insertAdjacentHTML(){throw new Error('insertAdjacentHTML used')}
  querySelector(sel){return this.children.find(c=>c.className===sel.slice(1))||null}
  remove(){}}
const document={createElement:tag=>new El(tag)};
let L=I18N.ru;const t=k=>L[k];
"""


def _console(entries):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = _template_js(["mcView", "mcNode"]) + FAKE_DOM + f"""
console.log(JSON.stringify({json.dumps(entries)}.map(e=>{{const d=mcNode(e);return {{cls:d.className,text:d.textContent,parts:d.children.map(c=>c.className),title:d.title||null}}}})))"""
    env = {**os.environ, "TZ": "UTC"}      # the entry time shows in the browser's local time
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, env=env).stdout)


def test_console_entries_render_like_claude_code():
    out = _console([
        {"id": 1, "kind": "batch", "master": "hub", "text": "[screen #1] Катя (button): 1. Ждать", "ts": "2026-10-28T12:34:56Z"},
        {"id": 2, "kind": "text", "master": "sdk", "text": "Бросаю за Брама."},
        {"id": 3, "kind": "tool", "master": "sdk", "name": "Bash", "text": "bash tools/dm-roll.sh 1d20"},
        {"id": 4, "kind": "tool", "master": "sdk", "name": "Read", "text": 'Read: {"file_path": "/x"}'},
        {"id": 5, "kind": "result", "master": "sdk", "text": "17", "error": False},
        {"id": 6, "kind": "turn", "master": "hub", "turn": 7, "text": "Дождь стучит."},
        {"id": 7, "kind": "note", "master": "driver", "text": "Стол на паузе"},
    ])
    assert [o["cls"] for o in out] == ["me batch", "me text", "me tool", "me tool", "me result", "me turn", "me note"]
    assert out[0]["text"] == "12:34› [screen #1] Катя (button): 1. Ждатьhub" and out[0]["parts"] == ["tm", "pr", "tx", "badge hub"]
    assert out[1]["text"] == "⏺ Бросаю за Брама."
    assert out[2]["text"] == "⏺ Bash(bash tools/dm-roll.sh 1d20)" and out[3]["text"] == '⏺ Read({"file_path": "/x"})'
    assert out[4]["text"] == "  ⎿ 17"
    assert out[5]["text"] == "── ход 7 опубликован ──" and out[5]["title"] == "Дождь стучит."
    assert out[6]["text"] == "Стол на паузе"


def test_console_text_is_never_html_and_long_results_collapse():
    attack = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    out = _console([{"id": 1, "kind": "text", "master": "hub", "text": attack},
                    {"id": 2, "kind": "batch", "master": "<b>x</b>", "text": attack},
                    {"id": 3, "kind": "result", "master": "sdk", "error": True, "text": "\n".join(f"line {n}" for n in range(10))}])
    assert out[0]["text"] == "⏺ " + attack and attack in out[1]["text"] and out[1]["parts"][-1] == "badge driver"
    assert out[2]["cls"] == "me result err more"
    assert out[2]["text"] == "  ⎿ " + "\n    ".join(f"line {n}" for n in range(6)) + " … +4 строк"


def test_the_page_has_a_scrollable_console_feed_and_a_paged_story_wheel():
    page = server.TEMPLATE.read_text(encoding="utf-8")
    css = page[:page.index("</style>")]

    assert '<section id="mc"' in page and 'id="mclog" tabindex="0"' in page and 'id="mcBtn"' in page and 'id="mcNew"' in page
    assert "#mclog{flex:1;min-height:0;overflow-y:auto" in css and "body.mc-ok #mcBtn{display:block}" in css
    assert "@media (max-width:760px),(orientation:portrait){#mc{top:0;right:0;bottom:0;left:0" in css
    assert "#feedlist{flex:1;display:flex;flex-direction:column;gap:.15em;overflow-y:auto" in css
    assert "while(box.children.length>200)" in page and "MC={open:false,loaded:false,loading:false,last:0,pending:[],max:500}" in page
    assert "es.addEventListener('master'" in page and "localStorage.setItem('mc'" in page and "mcState(st);" in page
    assert "story.addEventListener('wheel'" in page and "story.addEventListener('touchend'" in page and "{passive:false}" in page
    # the console builds its nodes with textContent only
    script = page[page.index("// ---- the master console"):page.index("// ---- state from the server")]
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script
    assert "https://" not in page.replace("https://x", "")    # no external resources
