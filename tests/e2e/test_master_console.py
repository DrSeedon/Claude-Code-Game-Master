"""The master console in a real browser (DM_SCREEN_MASTER_CONSOLE=1): open it, read the entries as text, scroll up,
get the "new" chip for a fresh entry; the feed scrolls; the story's wheel turns pages. Screenshots for a look at the
design go to .playtest/console-*.png."""

import json
import re
from pathlib import Path

import pytest

from lib.screen import activity, cli, masterlog
from e2e_support import make_art

pytestmark = pytest.mark.e2e

SHOTS = Path(__file__).resolve().parents[2] / ".playtest"
VIEWS = {"character": {"id": "pc", "name": "Aria Vale", "race": "Elf", "class": "Ranger", "level": 3, "ac": 15,
                       "hp": {"current": 31, "max": 40}}}
LONG = "".join(f"<p>{n}. Дождь стучит по ставням, и в таверне пахнет мокрой шерстью и дымом очага. Бармен вытирает кружку.</p>"
               for n in range(1, 40))
TURN = {"blocks": ["<h1>Таверна</h1>", LONG], "question": "Что делаете?", "options": ["Спросить бармена", "Изучить карту"]}
ATTACK = '<img src=x onerror="document.title=\'pwned\'">'


def fill_console(sdir):
    for n in range(1, 13):
        master = "hub" if n % 2 else "sdk"
        masterlog.append(sdir, "batch", f"[screen #{n}] Катя (button): {n}. Осмотреться", master)
        masterlog.append(sdir, "text", f"Бросаю Внимательность за Брама, затем описываю зал. {ATTACK if n == 3 else ''}", master)
        masterlog.append(sdir, "tool", f"bash tools/dm-roll.sh 1d20+3 --label 'Внимательность {n}'", master, name="Bash")
        masterlog.append(sdir, "result", "\n".join([f"🎲 1d20+3: {10 + n}"] + [f"строка вывода {i}" for i in range(9)]), master,
                         error=n == 5)
        masterlog.append(sdir, "turn", "Дождь стучит по ставням.", master, turn=n)
    masterlog.append(sdir, "note", "Мастер на хабе не ответил (no turn in 300s): ход играет запасной мастер")


def build(make_table, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_MASTER_CONSOLE", "1")
    table = make_table()
    art = make_art(table.root / "one.png", ("#223344", "#aa8844"))
    cli.set_act(table.sdir, art, "Rainy Tavern", kicker="АКТ ПЕРВЫЙ", place="Позолоченная кружка", date="День 1", lang="ru")
    cli.set_turn(table.sdir, TURN, answered=0)
    for n in range(30):
        activity.append_activity(table.sdir, "roll" if n % 3 == 0 else "info", f"Строка ленты {n}: проверка Внимательности 1d20 = {n}")
    fill_console(table.sdir)
    (table.root / "online-play-status.json").write_text(json.dumps({"campaign": "e2e", "state": "thinking"}))
    table.start(VIEWS)
    return table


def test_the_master_console_scrolls_and_shows_new_entries(make_table, page, monkeypatch):
    from playwright.sync_api import expect

    table = build(make_table, monkeypatch)
    SHOTS.mkdir(exist_ok=True)
    page.goto(table.url + "/")
    expect(page.locator("#live")).to_have_class("on", timeout=10000)
    expect(page.locator("#mcBtn")).to_be_visible()
    expect(page.locator("#mc")).to_be_hidden()

    page.click("#mcBtn")
    expect(page.locator("#mc")).to_be_visible()
    expect(page.locator("#mclog .me")).to_have_count(61)
    expect(page.locator("#mcthink")).to_be_visible()
    # text, never HTML: the attack shows as its own characters and runs nothing
    assert ATTACK in page.inner_text("#mclog") and page.title() != "pwned" and page.locator("#mclog img").count() == 0
    assert page.locator("#mclog .me.tool").first.inner_text().endswith("⏺ Bash(bash tools/dm-roll.sh 1d20+3 --label 'Внимательность 1')")
    assert page.locator("#mclog .badge.hub").count() == 6 and page.locator("#mclog .badge.sdk").count() == 6
    # stuck to the bottom on open
    assert page.evaluate("(()=>{const l=document.getElementById('mclog');return l.scrollHeight-l.scrollTop-l.clientHeight<24})()")
    page.wait_for_timeout(700)      # the slide-in and the entries' rise
    page.screenshot(path=str(SHOTS / "console-desktop.png"))

    # a long result opens on a click
    entry = page.locator("#mclog .me.result.more").first.get_attribute("data-id")
    page.click(f"#mclog .me[data-id='{entry}']")
    assert "строка вывода 8" in page.inner_text(f"#mclog .me[data-id='{entry}']")

    # the wheel scrolls the console up; a new entry then shows the chip instead of jumping
    page.hover("#mclog")
    page.mouse.wheel(0, -4000)
    page.wait_for_function("document.getElementById('mclog').scrollTop<50")
    masterlog.append(table.sdir, "text", "Новая мысль мастера, пока игрок листает вверх.", "hub")
    expect(page.locator("#mcNew")).to_be_visible(timeout=5000)
    assert page.evaluate("document.getElementById('mclog').scrollTop") < 50
    page.click("#mcNew")
    expect(page.locator("#mcNew")).to_be_hidden()
    expect(page.locator("#mclog .me").last).to_contain_text("⏺ Новая мысль мастера, пока игрок листает вверх.")
    # at the bottom, the next entry just appears
    masterlog.append(table.sdir, "note", "Стол на паузе")
    expect(page.locator("#mclog .me").last).to_contain_text("Стол на паузе", timeout=5000)
    expect(page.locator("#mcNew")).to_be_hidden()

    # keyboard: Escape closes, M opens again; the state is remembered across a reload
    page.keyboard.press("Escape")
    expect(page.locator("#mc")).to_be_hidden()
    page.keyboard.press("m")
    expect(page.locator("#mc")).to_be_visible()
    page.reload()
    expect(page.locator("#mc")).to_be_visible(timeout=10000)
    expect(page.locator("#mclog .me")).to_have_count(63)
    page.click("#mcx")
    expect(page.locator("#mc")).to_be_hidden()

    # the feed scrolls with its history; the story's wheel turns a page and the pager follows
    assert page.evaluate("document.querySelectorAll('#feedlist .fi:not(.think-now)').length") == 30
    assert page.evaluate("(()=>{const l=document.getElementById('feedlist');return l.scrollHeight>l.clientHeight})()")
    page.hover("#feedlist")
    page.mouse.wheel(0, -2000)
    page.wait_for_function("document.getElementById('feedlist').scrollTop<5")
    expect(page.locator("#pg")).to_have_text(re.compile(r"^1/[2-9]"), timeout=5000)
    page.hover("#story")
    page.mouse.wheel(0, 300)
    expect(page.locator("#pg")).to_have_text(re.compile(r"^2/"), timeout=5000)
    page.wait_for_timeout(400)
    page.mouse.wheel(0, -300)
    expect(page.locator("#pg")).to_have_text(re.compile(r"^1/"), timeout=5000)
    assert not page.js_errors, page.js_errors


def test_the_console_is_a_full_drawer_on_a_phone(make_table, browser, monkeypatch):
    from playwright.sync_api import expect

    table = build(make_table, monkeypatch)
    SHOTS.mkdir(exist_ok=True)
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    phone = context.new_page()
    errors = []
    phone.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        phone.goto(table.url + "/")
        expect(phone.locator("#live")).to_have_class("on", timeout=10000)
        expect(phone.locator("#mcBtn")).to_be_in_viewport()
        phone.wait_for_timeout(1500)    # the turn's rise animation
        phone.screenshot(path=str(SHOTS / "console-phone-closed.png"))
        phone.click("#mcBtn")
        expect(phone.locator("#mclog .me")).to_have_count(61)
        phone.wait_for_timeout(700)     # the drawer's slide-in
        box = phone.locator("#mc").bounding_box()
        assert box["x"] == 0 and box["y"] == 0 and box["width"] == 390 and box["height"] == 844
        phone.screenshot(path=str(SHOTS / "console-phone.png"))
        phone.click("#mcx")
        expect(phone.locator("#mc")).to_be_hidden()
    finally:
        context.close()
    assert not errors, errors


def test_without_the_flag_there_is_no_console(make_table, page, monkeypatch):
    from playwright.sync_api import expect

    table = make_table()
    monkeypatch.delenv("DM_SCREEN_MASTER_CONSOLE", raising=False)
    cli.set_turn(table.sdir, TURN, answered=0)
    masterlog.append(table.sdir, "text", "секрет сюжета", "sdk")
    table.start(VIEWS)
    page.goto(table.url + "/")
    expect(page.locator("#live")).to_have_class("on", timeout=10000)
    expect(page.locator("#mcBtn")).to_be_hidden()
    page.keyboard.press("m")
    expect(page.locator("#mc")).to_be_hidden()
    assert "секрет" not in page.content()
