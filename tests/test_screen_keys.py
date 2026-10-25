import pytest

from lib.screen import keys

GOOD = "sk_" + "a1b2c3d4" * 6


def test_the_key_replaces_only_its_own_line_and_keeps_a_backup(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nELEVENLABS_API_KEY=old\nDEEPGRAM_API_KEY=keep\n")

    keys.store_key(env, GOOD)

    assert env.read_text() == f"A=1\nELEVENLABS_API_KEY={GOOD}\nDEEPGRAM_API_KEY=keep\n"
    assert (tmp_path / ".env.bak").read_text().startswith("A=1\nELEVENLABS_API_KEY=old")


def test_the_key_is_added_when_missing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1")

    keys.store_key(env, GOOD)

    assert env.read_text() == f"A=1\nELEVENLABS_API_KEY={GOOD}\n"


def test_a_new_env_file_is_created_private(tmp_path):
    env = tmp_path / ".env"

    keys.store_key(env, GOOD)

    assert env.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("bad", ["", "hello", "sk_short", "sk_" + "x" * 30 + " with space", "Token abc", "A=1\nB=2"])
def test_junk_from_the_clipboard_is_refused_and_nothing_is_written(tmp_path, bad):
    env = tmp_path / ".env"
    env.write_text("ELEVENLABS_API_KEY=old\n")

    with pytest.raises(ValueError):
        keys.store_key(env, bad)

    assert env.read_text() == "ELEVENLABS_API_KEY=old\n"


def test_permission_report_names_what_is_missing():
    def fake(method, path, body, key):
        if method == "DELETE":
            return 401, '{"detail":{"message":"The API key you used is missing the permission voices_write to execute this operation."}}'
        return 200, "{}"

    report = keys.permission_report(GOOD, call=fake)

    assert report["voices_write"] is False and report["read_voices"] is True
