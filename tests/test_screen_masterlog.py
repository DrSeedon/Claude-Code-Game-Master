"""The master console log (lib/screen/masterlog.py): append, read, tail, rotation, broken lines, redaction."""

import json
import threading

import pytest

from lib.screen import masterlog
from lib.screen.masterlog import REDACTED, append, read, redact, tail


def test_append_and_read_in_order_with_after_and_limit(tmp_path):
    first = append(tmp_path, "batch", "[screen #1] Катя (button): 1. Осмотреться", "sdk")
    append(tmp_path, "text", "Дождь стучит.", "sdk")
    append(tmp_path, "result", "ok", "hub", error=True)

    entries = read(tmp_path)
    assert [e["id"] for e in entries] == [1, 2, 3]
    assert first == entries[0] and first["kind"] == "batch" and first["master"] == "sdk" and first["ts"].endswith("Z")
    assert entries[2]["error"] is True and entries[2]["master"] == "hub"
    assert [e["id"] for e in read(tmp_path, after=1)] == [2, 3]
    assert [e["id"] for e in read(tmp_path, limit=2)] == [2, 3]
    assert read(tmp_path / "nothing") == []
    assert (tmp_path / masterlog.LOG).stat().st_mode & 0o777 == 0o600


def test_texts_are_capped_per_kind(tmp_path):
    append(tmp_path, "text", "я" * 9000)
    append(tmp_path, "tool", "x" * 5000)
    append(tmp_path, "result", "y" * 5000)
    text, tool, result = read(tmp_path)
    assert len(text["text"]) == 8000 + len(masterlog.MORE) and text["text"].endswith("…")
    assert len(tool["text"]) == 2000 + len(masterlog.MORE) and len(result["text"]) == 2000 + len(masterlog.MORE)


def test_a_broken_line_is_skipped_and_ids_keep_increasing(tmp_path):
    append(tmp_path, "note", "one")
    with open(tmp_path / masterlog.LOG, "a", encoding="utf-8") as f:
        f.write('{"id": 2, "kind": "no\n')
    append(tmp_path, "note", "two")
    assert [(e["id"], e["text"]) for e in read(tmp_path)] == [(1, "one"), (2, "two")]


def test_rotation_keeps_the_newest_megabyte_and_the_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(masterlog, "ROTATE_AT", 20_000)
    monkeypatch.setattr(masterlog, "KEEP", 10_000)
    for n in range(100):
        append(tmp_path, "result", f"{n:03d} " + "z" * 400)
    size = (tmp_path / masterlog.LOG).stat().st_size
    entries = read(tmp_path, limit=0)
    assert size <= 20_000 + 600 and entries[-1]["id"] == 100 and entries[0]["id"] > 1
    assert [e["id"] for e in entries] == list(range(entries[0]["id"], 101))
    assert append(tmp_path, "note", "after")["id"] == 101


def test_tail_reads_only_new_whole_lines_and_survives_a_rotation(tmp_path):
    append(tmp_path, "note", "one")
    offset = (tmp_path / masterlog.LOG).stat().st_size
    append(tmp_path, "note", "two")
    entries, offset2 = tail(tmp_path, offset, after=1)
    assert [e["text"] for e in entries] == ["two"] and offset2 == (tmp_path / masterlog.LOG).stat().st_size
    with open(tmp_path / masterlog.LOG, "ab") as f:
        f.write(b'{"id": 3, "kind": "note"')          # half a line: not yet
    assert tail(tmp_path, offset2, after=2) == ([], offset2)
    (tmp_path / masterlog.LOG).write_text(json.dumps({"id": 9, "kind": "note", "text": "rotated"}) + "\n")
    entries, _ = tail(tmp_path, 10_000, after=2)
    assert [e["id"] for e in entries] == [9]


def test_parallel_writers_of_one_process_get_unique_ids(tmp_path):
    threads = [threading.Thread(target=lambda: [append(tmp_path, "note", "x") for _ in range(20)]) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(e["id"] for e in read(tmp_path, limit=0)) == list(range(1, 101))


def test_a_failure_to_log_never_raises(tmp_path):
    (tmp_path / "file").write_text("not a dir")
    assert append(tmp_path / "file", "note", "x") is None
    assert append(tmp_path, "bogus", "x") is None


# ---- redaction
# Secret-shaped values are split in the source ("sk-" "ant-..."): the repository's secret guard and GitGuardian
# scan it (2026-10-28).

@pytest.mark.parametrize("secret", [
    "sk-" "ant-api03-AbCdEf0123456789_xyzXYZ-0000",
    "sk-" "proj-AbCdEf0123456789xyzXYZ0000",
    "gh" "p_AbCdEf0123456789AbCdEf0123456789",
    "github" "_pat_11ABCDEFG0123456789_abcdefghijklmnop",
    "xo" "xb-1234567890-abcdefghij",
    "AI" "zaSyA1234567890abcdefghijklmnopqrstu",
    "AK" "IAIOSFODNN7EXAMPLE",
    "0123456789abcdef0123456789abcdef01234567",
    "Zm9vYmFyMTIzNDU2Nzg5MEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZXWFla",
])
def test_token_shapes_are_redacted(secret):
    out = redact(f"before {secret} after")
    assert secret not in out and out == f"before {REDACTED} after"


def test_bearer_and_assignments_keep_their_names():
    assert redact("Authorization: Bearer abc.DEF-123_xyz") == f"Authorization: Bearer {REDACTED}"
    assert redact("curl 'https://x/?token=s3cr3t&page=2' pass" "word=hunter22 key=abcd") == \
        f"curl 'https://x/?token={REDACTED}&page=2' pass" f"word={REDACTED} key={REDACTED}"
    assert redact('{"api_key": "abc\\"def", "name": "Bram"}') == f'{{"api_key": "{REDACTED}", "name": "Bram"}}'


def test_given_secrets_are_redacted_wherever_they_appear():
    ticket, url = "Tk3_shortTicket9", "https://hub.example/hooks/abc"
    out = redact(f"ticket {ticket} posted to {url}/x", secrets=[ticket, url, None, ""])
    assert ticket not in out and url not in out and out == f"ticket {REDACTED} posted to {REDACTED}/x"


def test_normal_text_json_and_file_names_are_left_alone():
    samples = [
        "Брам бросает 1d20+3 = 17 против КС 15: успех.",
        'bash tools/dm-screen.sh turn --file - <<JSON\n{"blocks": ["<p>Дождь</p>"], "options": ["Ждать"], "key": "music"}',
        "/audio/" + "a1b2c3d4" * 8 + ".mp3",
        "world-state/campaigns/alpha/screen/turn.json and the-very-long-kebab-case-name-without-any-digits-or-caps",
        "task-runner skip-this keyboard monkey=banana? no: monkey stays",
        "Supercalifragilisticexpialidocious-AND-Antidisestablishmentarianism",
    ]
    for text in samples:
        assert redact(text) == text, text


@pytest.mark.parametrize("text, shown", [
    ("DND_AUTH_PASSWORD=hunter2", f"DND_AUTH_PASSWORD={REDACTED}"),
    ("ELEVENLABS_API_KEY=" + "0123456789abcdef" * 2, f"ELEVENLABS_API_KEY={REDACTED}"),
    ("FREESOUND_API_KEY=" + "abcdefghij0123456789" * 2, f"FREESOUND_API_KEY={REDACTED}"),
    ("HUB_TOKEN=abcdefgh12", f"HUB_TOKEN={REDACTED}"),
    ('export ANTHROPIC_AUTH_TOKEN="a b c"\nOTHER=1', f"export ANTHROPIC_AUTH_TOKEN={REDACTED}\nOTHER=1"),
    ("api" "_key: abcdefgh12345678", f"api" f"_key: {REDACTED}"),
    ("run api" "Key=xyz then", f"run api" f"Key={REDACTED} then"),
    ('{"refreshToken":"abcDEF123short", "auth": "zz"}', f'{{"refreshToken":"{REDACTED}", "auth": "{REDACTED}"}}'),
    ("Authorization: Basic dXNlcjpwYXNz", f"Authorization: Basic {REDACTED}"),
    ("git clone https://user:hunter2pass@github.com/x", f"git clone https://user:{REDACTED}@github.com/x"),
])
def test_prefixed_env_names_json_fields_basic_auth_and_url_passwords_are_redacted(text, shown):
    assert redact(text) == shown


def test_secret_looking_names_do_not_catch_plain_words():
    for text in ["monkey=banana max_tokens=5 keyboard=3", '{"input_tokens": "12", "author": "Bram", "key": "music"}',
                 "The key: open the door. Author: Tolstoy", "PATH=/usr/bin:/bin"]:
        assert redact(text) == text, text


def test_env_secrets_are_the_values_of_secret_named_variables(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('export DEEPGRAM_API_KEY="plainlowercasekey1"\nDM_ART_DAILY_LIMIT=12345678\n# comment\n',
                        encoding="utf-8")
    found = masterlog.env_secrets({"DM_SCREEN_TOKEN": "tok-value-1", "HOME": "/home/someone", "HUB_TOKEN": "short"},
                                  env_file)
    assert sorted(found) == ["plainlowercasekey1", "tok-value-1"]
    assert redact("cat .env: plainlowercasekey1", found) == f"cat .env: {REDACTED}"


def test_forged_ids_are_ignored_so_the_console_keeps_going(tmp_path):
    append(tmp_path, "note", "one")
    with open(tmp_path / masterlog.LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": 10 ** 30, "kind": "text", "master": "hub", "text": "forged"}) + "\n")
        f.write(json.dumps({"id": True, "kind": "text", "master": "hub", "text": "bool"}) + "\n")
    after = append(tmp_path, "note", "two")
    assert after["id"] == 2 and [e["text"] for e in read(tmp_path)] == ["one", "two"]


def test_a_plain_name_before_a_secret_does_not_hide_it():
    assert redact("a: token=abc12345 b") == f"a: token={REDACTED} b"
    assert redact("note: DND_AUTH_PASSWORD=x") == f"note: DND_AUTH_PASSWORD={REDACTED}"
