"""The play screen in a real browser: gate, live link, turns, options, free text, who, party HP, act change, sound, picture mode."""

import http.client
import json
import urllib.parse

import pytest

from lib.screen import cli, inbox
from e2e_support import PASSWORD, TOKEN, Master, make_art

pytestmark = pytest.mark.e2e

VIEWS = {
    "character": {"id": "pc", "name": "Aria Vale", "race": "Elf", "class": "Ranger", "level": 3, "ac": 15,
                  "hp": {"current": 31, "max": 40}, "stats": {"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 14, "cha": 8}},
    "npcs": {"party": [{"id": "bram", "name": "Bram Stone",
                        "character_sheet": {"race": "Dwarf", "class": "Fighter", "level": 3, "ac": 17, "hp": {"current": 19, "max": 20},
                                            "stats": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}}}]},
}
TURN1 = {"blocks": ["<h1>The Tavern</h1>", "<p>Rain taps the shutters.</p>"], "question": "What do you do?",
         "options": ["Ask the barkeep", "Study the map", "Leave"]}
TURN2 = {"blocks": ["<p>The barkeep leans in.</p>"], "question": "And then?", "options": ["Pay", "Refuse"],
         "audio": {"music": {"cue": "calm tavern music", "tags": ["tavern"]}}}
TURN3 = {"blocks": ["<p>Dawn over the hills.</p>"], "question": "Onward?", "options": ["March", "Rest"]}


def http_call(base, method, path, body=None, headers=None):
    """One request without redirects; returns (status, headers, body bytes)."""
    host, port = urllib.parse.urlparse(base).netloc.split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, response, data


def options(page):
    """The option labels without their number badge."""
    return page.evaluate("[...document.querySelectorAll('#opts .opt')].map(b => b.lastChild.textContent)")


def test_gate_login_over_http(make_table):
    table = make_table(gated=True)
    make_art(table.sdir / "art.png", ("#334455", "#775533"))
    cli.set_act(table.sdir, table.sdir / "art.png", "Gate Act", kicker="K", place="P")
    table.start(VIEWS)
    form = {"Content-Type": "application/x-www-form-urlencoded"}

    status, _, page = http_call(table.url, "GET", "/login")
    assert status == 200 and b'name="password"' in page
    assert http_call(table.url, "GET", "/_auth")[0] == 401

    status, _, page = http_call(table.url, "POST", "/login", "password=nope", form)
    assert status == 401 and b'role="alert"' in page

    status, response, _ = http_call(table.url, "POST", "/login", "password=" + PASSWORD, form)
    cookie = response.getheader("Set-Cookie", "")
    assert status == 303 and response.getheader("Location") == "/" and cookie.startswith("screen_login=")
    signed = {"Cookie": cookie.split(";")[0]}
    assert http_call(table.url, "GET", "/_auth", headers=signed)[0] == 204
    status, response, _ = http_call(table.url, "GET", "/login", headers=signed)
    assert status == 303 and response.getheader("Location") == "/"
    status, _, page = http_call(table.url, "GET", "/", headers=signed)
    assert status == 200 and f'data-token="{TOKEN}"'.encode() in page


def test_gate_login_in_browser(make_table, page):
    table = make_table(gated=True)
    make_art(table.sdir / "art.png", ("#334455", "#775533"))
    cli.set_act(table.sdir, table.sdir / "art.png", "Gate Act", kicker="GATED", place="P")
    cli.set_turn(table.sdir, TURN1, answered=0)
    table.start(VIEWS)

    page.goto(table.url + "/login")
    page.fill("#pw", "wrong-password")
    page.click("button[type=submit]")
    page.wait_for_selector(".err:not(:empty)")
    assert page.url.endswith("/login") and page.query_selector("#live") is None

    page.fill("#pw", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_selector("#live.on")
    assert page.url == table.url + "/"
    assert page.inner_text("#kick") == "GATED"


def test_play_flow(make_table, director_for, page):
    table = make_table()
    art1, art2 = make_art(table.root / "one.png", ("#223344", "#aa8844")), make_art(table.root / "two.png", ("#552222", "#222266"))
    director, entry = director_for(table.root)
    cli.set_act(table.sdir, art1, "Rainy Tavern", kicker="ACT ONE", place="The Gilded Mug", date="Day 1", lang="en")
    cli.set_turn(table.sdir, TURN1, answered=0)
    master = Master(table.sdir, [
        lambda ev: (cli.set_turn(table.sdir, TURN2, answered=ev["id"]), activity_roll(table.sdir)),
        lambda ev: (cli.set_act(table.sdir, art2, "Open Road", kicker="ACT TWO", place="The King's Road", date="Day 2"),
                    cli.set_turn(table.sdir, TURN3, answered=ev["id"])),
    ])
    table.start(VIEWS, director=director)
    master.start()
    try:
        flow(table, page, master, entry, art2)
    finally:
        master.stop.set()
        master.join(5)
    assert not master.errors, master.errors
    assert not page.js_errors, page.js_errors


def activity_roll(sdir):
    from lib.screen import activity
    activity.append_activity(sdir, "roll", "Perception: d20 (14) + 3 = 17 vs DC 15, success")


def flow(table, page, master, entry, art2):
    from playwright.sync_api import expect

    page.goto(table.url + "/")
    expect(page.locator("#live")).to_have_class("on", timeout=10000)

    # the act and the first turn
    expect(page.locator("#kick")).to_have_text("ACT ONE")
    expect(page.locator("#place")).to_have_text("The Gilded Mug")
    expect(page.locator("#date")).to_have_text("Day 1")
    assert page.title() == "Rainy Tavern"
    expect(page.locator("#opts .opt")).to_have_count(3)
    assert options(page) == TURN1["options"]
    expect(page.locator("#q")).to_have_text("What do you do?")
    assert "Rain taps" in page.inner_text("#story")

    # the side panel: party hp is an object {current,max}; the all-10 placeholder grid stays hidden
    expect(page.locator("#side .hero")).to_have_count(2)
    side = page.inner_text("#side")
    assert "19/20" in side and "31/40" in side and "[object Object]" not in side, side
    heroes = page.locator("#side .hero")
    assert heroes.nth(0).locator(".ab").count() == 6 and heroes.nth(1).locator(".ab").count() == 0
    assert [b.inner_text() for b in page.locator("#who button").all()] == ["Aria", "Bram", "Everyone"]

    # a button action as Bram: the page waits, the master answers with the next turn
    page.click("#who button[data-n=Bram]")
    page.click("#opts .opt >> nth=0")
    expect(page.locator("body")).to_have_class("waiting", timeout=5000)
    first = inbox.read_events(table.sdir)[0]
    assert (first["who"], first["source"], first["text"]) == ("Bram", "button", "1. Ask the barkeep")
    master.release()
    expect(page.locator("#opts .opt")).to_have_count(2, timeout=10000)
    assert options(page) == TURN2["options"]
    expect(page.locator("body")).not_to_have_class("waiting")
    assert "barkeep leans" in page.inner_text("#story")
    expect(page.locator("#feedlist .fi.roll")).to_contain_text("Perception")

    # the music cue: /api/audio resolves it to the library file and the page's background player gets that source
    status, _, body = http_call(table.url, "GET", f"/api/audio?token={TOKEN}")
    music = json.loads(body)["audio"]["music"]
    assert status == 200 and music["file"] == entry["file"] and music["url"] == "/library/" + entry["file"]
    status, response, data = http_call(table.url, "GET", f"{music['url']}?token={TOKEN}")
    assert status == 200 and response.getheader("Content-Type") == "audio/wav" and data[:4] == b"RIFF"
    page.wait_for_function(f"() => BG.music && BG.music.src.includes('{entry['file']}')", timeout=10000)

    # free text with Enter as Aria
    page.click("#who button[data-n=Aria]")
    page.fill("#txt", "I bribe the guard quietly")
    page.press("#txt", "Enter")
    expect(page.locator("body")).to_have_class("waiting", timeout=5000)
    second = inbox.read_events(table.sdir)[1]
    assert (second["who"], second["source"], second["text"]) == ("Aria", "text", "I bribe the guard quietly")
    assert page.input_value("#txt") == ""
    master.release()

    # a new act: kicker, place and art change, then the new turn
    expect(page.locator("#kick")).to_have_text("ACT TWO", timeout=10000)
    expect(page.locator("#place")).to_have_text("The King's Road")
    expect(page.locator("#date")).to_have_text("Day 2")
    expect(page.locator("#opts .opt")).to_have_count(2)
    assert options(page) == TURN3["options"]
    assert "v=2" in page.get_attribute("#art", "src")
    assert page.evaluate("document.getElementById('art').complete && document.getElementById('art').naturalWidth") == 640
    assert http_call(table.url, "GET", "/art.png")[2] == art2.read_bytes()
    expect(page.locator("body")).not_to_have_class("waiting")

    # picture mode
    page.click("#pic")
    expect(page.locator("body")).to_have_class("clear")
    page.click("#pic")
    expect(page.locator("body")).not_to_have_class("clear")

    assert page.get_attribute("body", "data-err") is None
