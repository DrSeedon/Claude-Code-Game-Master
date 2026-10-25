"""Speech to text for the screen microphone: same Deepgram recipe as the VoiceType desktop app."""

import json
import os
import subprocess
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

DEEPGRAM_URL = ("https://api.deepgram.com/v1/listen?model=nova-3&language=ru&smart_format=true"
                "&punctuate=true&diarize_model=latest")
LOW_CONFIDENCE = 0.5
# adeclip repairs clipped peaks, loudnorm evens out quiet and loud speakers (A/B-tested in VoiceType)
CLEAN_FILTER = "adeclip,highpass=f=80,loudnorm=I=-18:TP=-2:LRA=11"


class VoiceUnavailable(RuntimeError):
    """No API key or no audio tooling: the microphone button cannot work."""


def load_api_key(project_root, environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("DEEPGRAM_API_KEY"):
        return environ["DEEPGRAM_API_KEY"]
    env_file = Path(project_root) / ".env"
    if env_file.is_file():
        return dotenv_values(env_file).get("DEEPGRAM_API_KEY") or None
    return None


def format_words(words, low_conf=LOW_CONFIDENCE):
    """One line only: a newline typed into a chat would send the message mid-sentence."""
    multi = len({w.get("speaker", 0) for w in words}) > 1
    parts, last = [], None
    for w in words:
        token = (w.get("punctuated_word") or w["word"]).replace("\n", " ")
        if w.get("confidence", 1) < low_conf:
            token += "(?)"
        if multi and w.get("speaker", 0) != last:
            token = f"Спикер {w.get('speaker', 0) + 1}: {token}"
            last = w.get("speaker", 0)
        parts.append(token)
    return " ".join(parts)


def clean_audio(data):
    """Browser recording (webm/opus or similar) to a normalized mono 16 kHz FLAC."""
    try:
        run = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", "pipe:0", "-af", CLEAN_FILTER, "-ac", "1", "-ar", "16000",
             "-f", "flac", "pipe:1"], input=data, capture_output=True, timeout=60)
    except FileNotFoundError as exc:
        raise VoiceUnavailable("ffmpeg is not installed") from exc
    if run.returncode != 0 or not run.stdout:
        raise ValueError("could not decode the recording: " + run.stderr.decode(errors="replace")[:200])
    return run.stdout


def transcribe(audio, content_type, api_key, opener=urllib.request.urlopen):
    if not api_key:
        raise VoiceUnavailable("DEEPGRAM_API_KEY is not set (put it in the project .env)")
    request = urllib.request.Request(DEEPGRAM_URL, data=audio, method="POST")
    request.add_header("Authorization", f"Token {api_key}")
    request.add_header("Content-Type", content_type)
    with opener(request, timeout=30) as response:
        result = json.loads(response.read().decode())
    words = result["results"]["channels"][0]["alternatives"][0]["words"]
    return format_words(words)


def make_transcriber(project_root, cleaner=clean_audio, sender=transcribe):
    """Transcriber for the server: clean the browser recording, then ask Deepgram.

    If cleaning fails the raw recording is sent as it is (same fallback as VoiceType)."""
    def run(audio, content_type):
        key = load_api_key(project_root)
        if not key:
            raise VoiceUnavailable("DEEPGRAM_API_KEY is not set (put it in the project .env)")
        try:
            return sender(cleaner(audio), "audio/flac", key)
        except ValueError:
            return sender(audio, content_type, key)
    return run
