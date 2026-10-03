"""Speech to text and text to speech through Sarvam AI.

If SARVAM_API_KEY is not set, the endpoints say so and the browser falls back
to its own speech recognition and voices (Chrome on Android handles hi-IN and
pa-IN fine for a demo).
"""
import base64

import httpx

from .config import SARVAM_API_KEY

STT_URL = "https://api.sarvam.ai/speech-to-text"
TTS_URL = "https://api.sarvam.ai/text-to-speech"


def enabled():
    return bool(SARVAM_API_KEY)


def transcribe(audio_bytes, filename, lang_code):
    r = httpx.post(
        STT_URL,
        headers={"api-subscription-key": SARVAM_API_KEY},
        files={"file": (filename, audio_bytes)},
        data={"model": "saarika:v2.5", "language_code": lang_code},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("transcript", "")


def speak(text, lang_code, speaker="anushka"):
    r = httpx.post(
        TTS_URL,
        headers={"api-subscription-key": SARVAM_API_KEY, "content-type": "application/json"},
        json={
            "inputs": [text[:1400]],
            "target_language_code": lang_code,
            "speaker": speaker,
            "model": "bulbul:v2",
            "pace": 0.9,
        },
        timeout=60,
    )
    r.raise_for_status()
    audios = r.json().get("audios") or []
    return base64.b64decode(audios[0]) if audios else b""
