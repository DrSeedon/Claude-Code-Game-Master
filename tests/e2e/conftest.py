"""Browser end-to-end tests of the play screen: a real server on 127.0.0.1, a stub master thread, headless Chrome.

Skipped unless DM_SCREEN_E2E=1 and playwright with a browser is available. Run with
    DM_SCREEN_E2E=1 uv run --group e2e pytest -q tests/e2e
Nothing here reaches the network or spends credits: no speaker, a stub transcriber, a tiny local sound library.
"""

import glob
import json
import os
from pathlib import Path

import pytest

from lib.screen import audio, gate

from e2e_support import BROWSER_ARGS, PASSWORD, NoFreesound, Table, silent_wav


def pytest_collection_modifyitems(config, items):
    if os.environ.get("DM_SCREEN_E2E") == "1":
        return
    skip = pytest.mark.skip(reason="set DM_SCREEN_E2E=1 to run the browser end-to-end tests")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def make_table(tmp_path, monkeypatch):
    tables = []

    def build(gated=False):
        if gated:
            login = tmp_path / "login.json"
            login.write_text(json.dumps({"password": gate.hash_password(PASSWORD), "key": os.urandom(32).hex()}))
            monkeypatch.setenv("DM_SCREEN_LOGIN_FILE", str(login))
        else:
            monkeypatch.delenv("DM_SCREEN_LOGIN_FILE", raising=False)
        monkeypatch.setenv("DM_SCREEN_SPEND_FILE", str(tmp_path / "spend.json"))
        table = Table(tmp_path / ("gated" if gated else "open"))
        tables.append(table)
        return table

    yield build
    for table in tables:
        if hasattr(table, "httpd"):
            table.close()


@pytest.fixture
def director_for():
    """A Director over a temp library holding one silent music file for the cue 'calm tavern music'; returns (director, entry)."""

    def build(root):
        director = audio.Director(root, api=None, speaker=None, freesound=NoFreesound())
        data = silent_wav(Path(root) / "silence.wav")
        entry = director.library.add(data, "wav", "music", "Tavern", tags=["tavern"], prompt="calm tavern music", loop=True, normalized=False)
        return director, entry

    return build


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as play:
        launched, errors = None, []
        attempts = [{"channel": "chrome"}] + [{"executable_path": path} for path in sorted(glob.glob(os.path.expanduser(
            "~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")), reverse=True)]
        for options in attempts:
            try:
                launched = play.chromium.launch(headless=True, args=BROWSER_ARGS, **options)
                break
            except Exception as exc:
                errors.append(str(exc).splitlines()[0])
        if launched is None:
            pytest.skip("no usable browser: " + "; ".join(errors))
        yield launched
        launched.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.js_errors = []
    page.on("pageerror", lambda exc: page.js_errors.append(str(exc)))
    yield page
    context.close()

