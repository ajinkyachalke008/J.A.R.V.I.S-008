"""
ElevenLabs speech synthesis — the multilingual voice.

WHY IT IS WORTH A FILE OF ITS OWN
    The system voice speaks the languages the machine has voices for, which on
    an ordinary install means one. This assistant is used in many, and people
    switch language mid-conversation. One ElevenLabs voice speaks all of them,
    with the same voice, without anything being installed or downloaded — which
    is the thing neither of the local options can do.

    It costs a key and an internet connection. That is the trade, and it is why
    this is a choice rather than the default.

THE FORMAT NEGOTIATION, WHICH IS NOT OPTIONAL
    Asking for `pcm_24000` gives audio at exactly the rate the speaker is
    already open at — no decoding, no resampling, first sample straight to the
    queue. But raw PCM output is a paid-tier feature, and a free key is refused
    with a 422 that names the tier.

    Rejecting it there would mean this provider works for some accounts and
    returns an error for others, which is not a useful thing to ship. So the PCM
    request is tried once, and an account that cannot have it drops to MP3 and
    decodes. The decoder is PyAV, which arrives with faster-whisper; when
    neither is present the failure says exactly which of the two things to do
    about it rather than reporting a format error nobody can act on.

NO LANGUAGE PARAMETER IS SENT
    The multilingual models detect the language from the text. Passing one would
    mean this file deciding what language the assistant is speaking, which is a
    decision it has no business making — the model and the system prompt own it.
"""
from __future__ import annotations

import asyncio
import json
from importlib.util import find_spec
from typing import AsyncIterator

from . import audio
from .base import DEFAULT_CAPS, Field

API = "https://api.elevenlabs.io/v1"

# Latency first. This is a conversation: a voice that arrives half a second
# sooner is worth more here than one that is slightly richer, and the flash
# models are multilingual too. The higher-quality models stay available for
# anybody who would rather have them.
DEFAULT_VOICE_ID = "ibbx9zDYGvLgtYzRbqqG"

MODELS = (
    "eleven_flash_v2_5",        # fastest, multilingual (recommended default)
    "eleven_turbo_v2_5",        # high quality, low latency
    "eleven_multilingual_v2",   # maximum expressiveness & quality
    "eleven_flash_v2",          # lightweight fallback
)
DEFAULT_MODEL = MODELS[0]

# Asked for in this order. The first is free of any conversion; the second needs
# decoding but is available on every account.
_PCM = "pcm_24000"
_MP3 = "mp3_44100_128"


class ElevenLabsTTS:
    def __init__(self, cfg: dict):
        import os
        # API key from config or environment variable override
        self.key = (cfg.get("api_key") or os.environ.get("ELEVENLABS_API_KEY") or "").strip()
        # Prepopulate with user's custom voice ID if not already configured
        self.voice_id = (cfg.get("voice_id") or DEFAULT_VOICE_ID).strip()
        self.model = (cfg.get("model") or DEFAULT_MODEL).strip()
        self.stability = _num(cfg.get("stability"), 0.5)
        self.similarity = _num(cfg.get("similarity"), 0.75)
        self.caps = dict(DEFAULT_CAPS)
        self.caps["audio_out"] = True
        self.base = API
        # None until the first request has learned what this account may have.
        self._format: str | None = None

    # ── requests ─────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {"xi-api-key": self.key, "Content-Type": "application/json"}

    def _payload(self, text: str) -> dict:
        return {
            "text": text,
            "model_id": self.model,
            # No `language_code`: the model detects it. See the module docstring.
            "voice_settings": {"stability": self.stability,
                               "similarity_boost": self.similarity},
        }

    async def _stream_once(self, cl, text: str, fmt: str) -> AsyncIterator[bytes]:
        url = f"{API}/text-to-speech/{self.voice_id}/stream"
        async with cl.stream("POST", url, headers=self._headers(),
                             params={"output_format": fmt},
                             json=self._payload(text)) as r:
            if r.status_code >= 400:
                body = (await r.aread()).decode("utf-8", "replace")
                raise _HttpError(r.status_code, body)
            async for piece in r.aiter_bytes():
                if piece:
                    yield piece

    async def speak(self, text: str, voice: str = "", cl=None) -> AsyncIterator[bytes]:
        import httpx

        if voice:
            self.voice_id = voice
        if not self.key:
            raise RuntimeError("no ElevenLabs API key is set")
        if not self.voice_id:
            raise RuntimeError("no ElevenLabs voice is chosen")
        text = (text or "").strip()
        if not text:
            return

        async def _run_stream(client):
            fmt = self._format or _PCM
            try:
                async for piece in self._emit(client, text, fmt):
                    yield piece
                self._format = fmt
                return
            except _HttpError as e:
                # 422 on the PCM request is the tier refusing the format, not a
                # bad voice or a bad key. Learn it once and never ask again.
                if fmt == _PCM and e.status in (400, 401, 422):
                    self._format = _MP3
                else:
                    raise RuntimeError(f"{e.status} {_message(e.body)}") from None

            async for piece in self._emit(client, text, _MP3):
                yield piece

        if cl is not None:
            async for chunk in _run_stream(cl):
                yield chunk
        else:
            async with httpx.AsyncClient(timeout=60.0) as local_cl:
                async for chunk in _run_stream(local_cl):
                    yield chunk

    async def stream_sentences(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Stream low-latency audio chunks by splitting text into sentences."""
        import httpx
        import re

        sentence_end_re = re.compile(r'([.!?\n]+)\s*')
        buffer = ""

        async with httpx.AsyncClient(timeout=60.0) as cl:
            async for fragment in text_stream:
                buffer += fragment
                while True:
                    match = sentence_end_re.search(buffer)
                    if not match:
                        break
                    idx = match.end()
                    sentence = buffer[:idx].strip()
                    buffer = buffer[idx:]
                    if sentence:
                        async for pcm in self.speak(sentence, cl=cl):
                            yield pcm

            if buffer.strip():
                async for pcm in self.speak(buffer.strip(), cl=cl):
                    yield pcm

    async def _emit(self, cl, text: str, fmt: str) -> AsyncIterator[bytes]:
        if fmt == _PCM:
            # Already 24 kHz mono 16-bit — exactly what the speaker wants, so it
            # goes straight through, sliced only for the interrupt granularity.
            buf = b""
            async for piece in self._stream_once(cl, text, fmt):
                buf += piece
                while len(buf) >= 2400:
                    yield buf[:2400]
                    buf = buf[2400:]
            if buf:
                yield buf
            return

        mp3 = b""
        async for piece in self._stream_once(cl, text, fmt):
            mp3 += piece
        pcm = await asyncio.to_thread(_decode_mp3, mp3)
        for piece in audio.chunk(pcm):
            yield piece

    # ── for the panel ────────────────────────────────────────────────────────
    def voices(self) -> list[tuple[str, str]]:
        """(id, name) for every voice on the account."""
        import httpx
        with httpx.Client(timeout=15.0) as cl:
            r = cl.get(f"{API}/voices", headers={"xi-api-key": self.key})
            if r.status_code >= 400:
                raise RuntimeError(f"{r.status_code} {_message(r.text)}")
            return [(v.get("voice_id", ""), v.get("name", ""))
                    for v in (r.json().get("voices") or [])]

    def verify_voice(self, voice_id: str = "") -> dict:
        """Verify voice ID against ElevenLabs account and return structured status."""
        vid = (voice_id or self.voice_id or DEFAULT_VOICE_ID).strip()
        if not self.key:
            return {
                "ok": False,
                "status": "UNAUTHENTICATED",
                "voice_id": vid,
                "message": "No API key configured. Enter your ElevenLabs API key in Settings.",
                "details": "Authentication required",
            }

        import httpx
        url = f"{API}/voices/{vid}"
        try:
            with httpx.Client(timeout=15.0) as cl:
                r = cl.get(url, headers={"xi-api-key": self.key})
                if r.status_code == 200:
                    data = r.json()
                    name = data.get("name", vid)
                    category = data.get("category", "custom")
                    settings = data.get("settings") or {}
                    return {
                        "ok": True,
                        "status": "SUCCESS",
                        "voice_id": vid,
                        "voice_name": name,
                        "category": category,
                        "availability": "READY",
                        "provider": "ELEVENLABS",
                        "model": self.model,
                        "settings": settings,
                        "message": f"Verified: '{name}' ({category}) is ready for speech synthesis.",
                    }
                elif r.status_code == 401:
                    return {
                        "ok": False,
                        "status": "UNAUTHORIZED",
                        "voice_id": vid,
                        "message": "API key refused (401 Unauthorized). Please check your key.",
                        "details": _message(r.text),
                    }
                elif r.status_code == 403:
                    return {
                        "ok": False,
                        "status": "FORBIDDEN",
                        "voice_id": vid,
                        "message": "Permission denied (403 Forbidden). Account cannot access this voice.",
                        "details": _message(r.text),
                    }
                elif r.status_code == 404:
                    return {
                        "ok": False,
                        "status": "NOT_FOUND",
                        "voice_id": vid,
                        "message": f"Voice ID '{vid}' was not found on this account (404 Not Found).",
                        "details": _message(r.text),
                    }
                elif r.status_code == 429:
                    return {
                        "ok": False,
                        "status": "RATE_LIMITED",
                        "voice_id": vid,
                        "message": "Rate limit exceeded or quota exhausted (429 Too Many Requests).",
                        "details": _message(r.text),
                    }
                else:
                    return {
                        "ok": False,
                        "status": f"HTTP_{r.status_code}",
                        "voice_id": vid,
                        "message": f"ElevenLabs API returned HTTP {r.status_code}: {_message(r.text)}",
                        "details": r.text[:160],
                    }
        except httpx.TimeoutException:
            return {
                "ok": False,
                "status": "TIMEOUT",
                "voice_id": vid,
                "message": "Connection to ElevenLabs API timed out (15s).",
                "details": "Timeout",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "NETWORK_ERROR",
                "voice_id": vid,
                "message": f"Network error contacting ElevenLabs: {e}",
                "details": str(e),
            }

    def probe(self) -> tuple[bool, str]:
        if not self.key:
            return False, "No ElevenLabs API key set."
        res = self.verify_voice()
        if not res["ok"]:
            return False, res["message"]
        name = res.get("voice_name", self.voice_id)
        note = "" if find_spec("av") else \
            "  (MP3 fallback would need PyAV — only matters on a free tier)"
        return True, f"Ready: {name} [{self.voice_id}], {self.model}{note}"

    def play_preview(self, text: str = "Good evening, sir. JARVIS systems are online. How may I assist you?", on_status=None) -> None:
        """Synthesize and play isolated audio preview using sounddevice without modifying conversation queues."""
        import numpy as np
        import sounddevice as sd

        async def _gen():
            chunks = []
            async for pcm in self.speak(text):
                chunks.append(pcm)
            return b"".join(chunks)

        if on_status:
            on_status("Synthesizing preview...")
        pcm_bytes = asyncio.run(_gen())
        if not pcm_bytes:
            if on_status:
                on_status("No audio received.")
            return

        if on_status:
            on_status("Playing preview...")
        pcm_arr = np.frombuffer(pcm_bytes, dtype=np.int16)
        sd.play(pcm_arr, samplerate=audio.SPEAKER_RATE)
        sd.wait()
        if on_status:
            on_status("Preview finished.")


# ─────────────────────────────────────────────────────────────────────────────
class _HttpError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"{status}")
        self.status, self.body = status, body


def _num(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _message(body: str) -> str:
    """The sentence out of an ElevenLabs error, which nests it two deep."""
    try:
        obj = json.loads(body)
        detail = obj.get("detail", obj)
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("status") or detail)
        return str(detail)
    except Exception:
        return " ".join((body or "").split())[:160]


def _decode_mp3(data: bytes) -> bytes:
    """MP3 -> 24 kHz mono 16-bit PCM, using PyAV.

    PyAV is a dependency of faster-whisper, so anybody running local speech
    recognition already has it. When it is missing the message says what to
    install AND what the alternative is, because "no decoder" on its own tells
    somebody nothing about why their voice stopped working.
    """
    if find_spec("av") is None:
        raise RuntimeError(
            "this account cannot receive raw PCM, so the audio arrives as MP3 "
            "and needs a decoder: pip install av — or use a paid ElevenLabs "
            "tier, or the system voice")
    import io

    import av
    import numpy as np

    out = []
    with av.open(io.BytesIO(data)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono",
                                      rate=audio.SPEAKER_RATE)
        for frame in container.decode(audio=0):
            for res in resampler.resample(frame):
                out.append(res.to_ndarray().reshape(-1))
        for res in resampler.resample(None):        # flush
            out.append(res.to_ndarray().reshape(-1))
    if not out:
        return b""
    return np.concatenate(out).astype("<i2").tobytes()


def _make(cfg: dict) -> ElevenLabsTTS:
    return ElevenLabsTTS(cfg)


PROVIDER = {
    "id": "elevenlabs",
    "kind": "tts",
    "label": "ElevenLabs",
    "hint": "One voice that speaks every language — needs a key and a connection",
    "requires": ("httpx",),
    "catalog": (
        {"id": "elevenlabs", "label": "ElevenLabs",
         "note": "cloud · one voice speaks every language", "local": False,
         "values": {}},
    ),
    "needs": (
        Field("api_key", "API key", kind="secret",
              hint="elevenlabs.io -> Profile -> API key"),
        Field("voice_id", "Voice", kind="choice", choices=(),
              default=DEFAULT_VOICE_ID,
              hint="Custom voice ID (preconfigured: ibbx9zDYGvLgtYzRbqqG) or pick from account"),
        Field("model", "Model", kind="choice", choices=MODELS,
              default=DEFAULT_MODEL, required=False,
              hint="flash is the quickest and still multilingual"),
        Field("stability", "Stability", kind="number", default=0.5,
              required=False, advanced=True, hint="0 to 1"),
        Field("similarity", "Similarity", kind="number", default=0.75,
              required=False, advanced=True, hint="0 to 1"),
    ),
    "caps": {"audio_out": True},
    "factory": _make,
}


def available() -> bool:
    return find_spec("httpx") is not None
