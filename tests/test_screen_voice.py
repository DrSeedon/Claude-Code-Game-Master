import io
import json

import pytest

from lib.screen import voice


def word(text, conf=0.99, speaker=0, punctuated=None):
    return {"word": text, "punctuated_word": punctuated or text, "confidence": conf, "speaker": speaker}


def test_format_words_single_speaker_uses_punctuated_words():
    words = [word("привет", punctuated="Привет,"), word("мир", punctuated="мир.")]

    assert voice.format_words(words) == "Привет, мир."


def test_format_words_marks_low_confidence():
    words = [word("показать"), word("товар", conf=0.3)]

    assert voice.format_words(words) == "показать товар(?)"


def test_format_words_labels_speakers_only_when_several():
    words = [word("да", speaker=0), word("нет", speaker=1), word("ладно", speaker=1)]

    assert voice.format_words(words) == "Спикер 1: да Спикер 2: нет ладно"


def test_format_words_empty_is_empty_string():
    assert voice.format_words([]) == ""


def test_format_words_is_one_line():
    assert "\n" not in voice.format_words([word("а", punctuated="а\n")])


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_transcribe_sends_voicetype_parameters_and_returns_text():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["type"] = request.get_header("Content-type")
        seen["data"] = request.data
        payload = {"results": {"channels": [{"alternatives": [{"words": [word("привет")]}]}]}}
        return _Response(json.dumps(payload).encode())

    text = voice.transcribe(b"audio", "audio/flac", "KEY", opener=opener)

    assert text == "привет"
    assert "model=nova-3" in seen["url"] and "language=ru" in seen["url"]
    assert "smart_format=true" in seen["url"] and "punctuate=true" in seen["url"]
    assert seen["auth"] == "Token KEY"
    assert seen["type"] == "audio/flac"
    assert seen["data"] == b"audio"


def test_transcribe_without_key_fails_loudly():
    with pytest.raises(voice.VoiceUnavailable):
        voice.transcribe(b"audio", "audio/flac", "")


def test_load_api_key_prefers_environment(tmp_path):
    (tmp_path / ".env").write_text("DEEPGRAM_API_KEY=from-file\n")

    assert voice.load_api_key(tmp_path, {"DEEPGRAM_API_KEY": "from-env"}) == "from-env"


def test_load_api_key_reads_project_env_file(tmp_path):
    (tmp_path / ".env").write_text("OTHER=1\nDEEPGRAM_API_KEY=from-file\n")

    assert voice.load_api_key(tmp_path, {}) == "from-file"


def test_load_api_key_missing_returns_none(tmp_path):
    assert voice.load_api_key(tmp_path, {}) is None


def test_transcriber_sends_raw_recording_when_cleaning_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    (tmp_path / ".env").write_text("DEEPGRAM_API_KEY=k\n")
    sent = []

    def broken_cleaner(audio):
        raise ValueError("ffmpeg could not decode")

    def sender(audio, content_type, key):
        sent.append((audio, content_type, key))
        return "ок"

    run = voice.make_transcriber(tmp_path, cleaner=broken_cleaner, sender=sender)

    assert run(b"raw-webm", "audio/webm") == "ок"
    assert sent == [(b"raw-webm", "audio/webm", "k")]


def test_transcriber_without_key_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    run = voice.make_transcriber(tmp_path, cleaner=lambda a: a, sender=lambda *a: "x")

    with pytest.raises(voice.VoiceUnavailable):
        run(b"x", "audio/webm")


def test_detailed_transcription_keeps_every_word_with_confidence_and_timing():
    payload = {"metadata": {"request_id": "dg-77", "duration": 3.2, "models": ["m"]},
               "results": {"channels": [{"alternatives": [{"confidence": 0.93, "words": [
                   {"word": "привет", "punctuated_word": "Привет,", "confidence": 0.99, "speaker": 0, "start": 0.1, "end": 0.5},
                   {"word": "мир", "punctuated_word": "мир.", "confidence": 0.4, "speaker": 0, "start": 0.6, "end": 0.9}]}]}]}}

    def opener(request, timeout):
        return _Response(json.dumps(payload).encode())

    details = voice.transcribe_detailed(b"audio", "audio/flac", "KEY", opener=opener)

    assert details["text"] == "Привет, мир.(?)"
    assert details["seconds"] == 3.2 and details["request_id"] == "dg-77" and details["confidence"] == 0.93
    assert details["words"][1] == {"word": "мир.", "confidence": 0.4, "speaker": 0, "start": 0.6, "end": 0.9}


def test_transcriber_marks_the_raw_fallback(tmp_path):
    (tmp_path / ".env").write_text("DEEPGRAM_API_KEY=k\n")

    def broken(audio):
        raise ValueError("cannot decode")

    run = voice.make_transcriber(tmp_path, cleaner=broken, sender=lambda audio, ctype, key: {"text": "ок", "words": []})

    assert run(b"raw", "audio/webm")["fallback"] is True
