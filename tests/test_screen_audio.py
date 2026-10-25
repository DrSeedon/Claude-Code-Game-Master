import json

import pytest

from lib.screen import audio


class FakeSpeaker:
    def __init__(self, tmp_path, left=10000):
        self.dir, self.left, self.spending = tmp_path / "screen", left, []

    def quota(self):
        return {"used": 0, "limit": 10000, "left": self.left, "account": 0}

    def spent(self, before, estimate):
        self.spending.append(estimate)
        return estimate


class FakeApi:
    def __init__(self):
        self.calls = []

    def sound(self, text, seconds=None, loop=False, **_):
        self.calls.append(("sound", text, seconds, loop))
        return b"SFX:" + text.encode()

    def music(self, prompt, length_ms, model_id="music_v1", instrumental=True):
        self.calls.append(("music", prompt, length_ms, model_id))
        return b"MUSIC:" + prompt.encode()


class NoFreesound:
    def search(self, query, kind):
        return None


@pytest.fixture
def director(tmp_path):
    api, spk = FakeApi(), FakeSpeaker(tmp_path)
    return audio.Director(tmp_path, api, spk, freesound=NoFreesound()), api, spk, tmp_path


def cue(text, kind="sfx", **extra):
    return audio.validate_cue({"cue": text, **extra}, kind, "test", blocks=3)


def test_library_finds_by_tags_and_words_and_ignores_other_kinds(tmp_path):
    lib = audio.Library(tmp_path)
    lib.add(b"x", "mp3", "sfx", "Wooden door creaks open", ["door", "creak"])
    lib.add(b"y", "ogg", "music", "Medieval tavern lute", ["tavern", "lute"])

    assert lib.find("sfx", "an old door creaking", ["door"])["title"] == "Wooden door creaks open"
    assert lib.find("sfx", "lute in a tavern", ["tavern"]) is None
    assert lib.find("music", "lute", ["tavern"])["file"].endswith(".ogg")
    assert lib.find("sfx", "explosion", []) is None


def test_the_same_prompt_is_found_exactly(tmp_path):
    lib = audio.Library(tmp_path)
    lib.add(b"x", "mp3", "sfx", "mug slammed", [], prompt="Mug slammed on a wooden table")

    assert lib.find("sfx", "mug slammed on a wooden table")["prompt"] == "Mug slammed on a wooden table"


def test_free_resolution_never_generates(director):
    d, api, spk, _ = director
    turn = {"blocks": ["<p>a</p>"], "audio": {"sfx": [cue("thunder")], "music": cue("lute jig", "music")}}

    out = d.resolve(turn, generate=False)

    assert api.calls == [] and spk.spending == [] and out["sfx"] == [] and out["music"] == "keep" and out["missing"] == ["lute jig", "thunder"]


def test_generation_happens_once_and_lands_in_the_library(director):
    d, api, spk, tmp_path = director
    turn = {"blocks": ["<p>a</p>"], "audio": {"sfx": [cue("thunder", block=0, seconds=2)], "ambience": cue("rain on a roof", "ambience")}}

    first = d.resolve(turn, generate=True)
    second = d.resolve(turn, generate=True)

    assert [c[0] for c in api.calls] == ["sound", "sound"] and api.calls[0][3] is True     # ambience (asked first) loops
    assert spk.spending == [30 * audio.SFX_CREDITS_PER_SECOND, 2 * audio.SFX_CREDITS_PER_SECOND]
    assert first == second and first["sfx"][0]["block"] == 0 and first["ambience"]["loop"] is True
    assert (tmp_path / "world-state" / "audio-library" / "files" / first["sfx"][0]["file"]).read_bytes() == b"SFX:thunder"


def test_music_is_generated_as_instrumental_music(director):
    d, api, spk, _ = director

    out = d.resolve({"blocks": ["<p>a</p>"], "audio": {"music": cue("cheerful lute jig", "music", seconds=60)}}, generate=True)

    assert api.calls == [("music", "cheerful lute jig", 60000, "music_v1")] and spk.spending == [900] and out["music"]["volume"] == 0.3


def test_null_music_means_silence_and_missing_music_keeps_playing(director):
    d, _, _, _ = director

    assert d.resolve({"blocks": ["<p>a</p>"], "audio": {"music": None}})["music"] is None
    assert d.resolve({"blocks": ["<p>a</p>"], "audio": {}})["ambience"] == "keep"


def test_not_enough_credits_skips_the_sound_and_keeps_the_turn(director):
    d, api, spk, _ = director
    spk.left = 10

    out = d.resolve({"blocks": ["<p>a</p>"], "audio": {"sfx": [cue("thunder")]}}, generate=True)

    assert api.calls == [] and out["sfx"] == [] and out["missing"] == ["thunder"]


def test_a_cue_marked_free_only_is_never_generated(director):
    d, api, _, _ = director

    d.resolve({"blocks": ["<p>a</p>"], "audio": {"sfx": [cue("thunder", generate=False)]}}, generate=True)

    assert api.calls == []


def test_plan_counts_only_what_the_library_lacks(director):
    d, _, _, tmp_path = director
    audio.Library(tmp_path).add(b"x", "mp3", "sfx", "thunder clap", ["thunder"])
    turn = {"blocks": ["<p>a</p>"], "audio": {"sfx": [cue("thunder", tags=["thunder"]), cue("glass breaks", seconds=1)]}}

    assert d.plan(turn) == {"cues": 2, "found": 1, "credits": audio.SFX_CREDITS_PER_SECOND}


def test_freesound_hits_are_downloaded_once_with_their_credit(tmp_path):
    class OneHit:
        def search(self, query, kind):
            return {"id": 42, "name": "Door creak", "username": "foley", "tags": ["door"], "duration": 2.0, "url": "https://freesound.org/s/42/",
                    "previews": {"preview-hq-mp3": "https://cdn.freesound.org/42.mp3"}}

    fetched = []

    class Response:
        def __init__(self, data):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(request, timeout=None):
        fetched.append(request.full_url)
        return Response(b"MP3DOOR")

    d = audio.Director(tmp_path, FakeApi(), FakeSpeaker(tmp_path), freesound=OneHit(), opener=opener)
    turn = {"blocks": ["<p>a</p>"], "audio": {"sfx": [cue("door creaks", tags=["door"])]}}

    first = d.resolve(turn)
    second = d.resolve(turn)

    assert fetched == ["https://cdn.freesound.org/42.mp3"] and first == second
    assert "freesound.org, CC0" in first["sfx"][0]["credit"] and first["sfx"][0]["source"] == "freesound"


def test_freesound_without_a_key_is_skipped(tmp_path):
    assert audio.Freesound(tmp_path).search("door", "sfx") is None


def test_library_remove_deletes_the_file(tmp_path):
    lib = audio.Library(tmp_path)
    entry = lib.add(b"x", "mp3", "sfx", "boom", ["boom"])

    lib.remove(entry["id"])

    assert lib.entries() == [] and not lib.path(entry).exists()
    with pytest.raises(ValueError):
        lib.remove(entry["id"])


def test_without_ffmpeg_a_sound_is_stored_as_it_came(tmp_path, monkeypatch):
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    entry = audio.Library(tmp_path).add(b"RAW", "ogg", "ambience", "wind", ["wind"])

    assert entry["file"].endswith(".ogg") and "normalized" not in entry
    assert audio.Library(tmp_path).path(entry).read_bytes() == b"RAW"


@pytest.mark.skipif(not audio.shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_a_quiet_sound_is_brought_to_the_effect_loudness(tmp_path):
    import subprocess

    quiet = tmp_path / "quiet.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-af", "volume=-40dB", str(quiet)], check=True)
    lib = audio.Library(tmp_path)

    entry = lib.add(quiet.read_bytes(), "wav", "sfx", "beep", ["beep"])

    assert entry["file"].endswith(".mp3") and entry["normalized"] == -16
    level = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(lib.path(entry)), "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    assert float(level.split("max_volume:")[1].split("dB")[0]) > -20     # it came in at about -43
