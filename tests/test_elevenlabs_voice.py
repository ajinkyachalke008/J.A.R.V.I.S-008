import asyncio
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from providers.tts_elevenlabs import (
    ElevenLabsTTS,
    DEFAULT_VOICE_ID,
    DEFAULT_MODEL,
    MODELS,
    _PCM,
    _MP3,
)
from memory.config_manager import (
    get_speech_output_mode,
    save_speech_output_mode,
    get_elevenlabs_voice_id,
    save_elevenlabs_voice_id,
    get_voice,
    AVAILABLE_VOICES,
)


def test_default_voice_id_preconfigured():
    """Default voice ID must match the user's specific custom ElevenLabs voice."""
    assert DEFAULT_VOICE_ID == "ibbx9zDYGvLgtYzRbqqG"
    
    tts = ElevenLabsTTS({})
    assert tts.voice_id == "ibbx9zDYGvLgtYzRbqqG"
    assert tts.model == DEFAULT_MODEL
    assert tts.model in MODELS


def test_env_api_key_override(monkeypatch):
    """ElevenLabsTTS must respect ELEVENLABS_API_KEY environment variable if cfg has no key."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "env-test-key-12345")
    tts = ElevenLabsTTS({})
    assert tts.key == "env-test-key-12345"

    # Explicit config key takes precedence
    tts_explicit = ElevenLabsTTS({"api_key": "explicit-key"})
    assert tts_explicit.key == "explicit-key"


def test_custom_voice_id_preserved():
    """Existing configured voice ID must be preserved and not overwritten."""
    tts = ElevenLabsTTS({"voice_id": "custom-voice-999"})
    assert tts.voice_id == "custom-voice-999"


def test_models_catalog_compatibility():
    """Real-time models must be available in catalog."""
    assert "eleven_flash_v2_5" in MODELS
    assert "eleven_turbo_v2_5" in MODELS
    assert "eleven_multilingual_v2" in MODELS
    assert "eleven_flash_v2" in MODELS


def test_verify_voice_success():
    """verify_voice returns structured metadata on HTTP 200."""
    tts = ElevenLabsTTS({"api_key": "test-key", "voice_id": "ibbx9zDYGvLgtYzRbqqG"})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "voice_id": "ibbx9zDYGvLgtYzRbqqG",
        "name": "JARVIS Custom",
        "category": "cloned",
        "settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = tts.verify_voice()
        assert res["ok"] is True
        assert res["status"] == "SUCCESS"
        assert res["voice_id"] == "ibbx9zDYGvLgtYzRbqqG"
        assert res["voice_name"] == "JARVIS Custom"
        assert res["availability"] == "READY"
        assert res["provider"] == "ELEVENLABS"


def test_verify_voice_errors():
    """verify_voice accurately distinguishes 401, 403, 404, and 429 errors."""
    tts = ElevenLabsTTS({"api_key": "test-key", "voice_id": "ibbx9zDYGvLgtYzRbqqG"})

    # 401 Unauthorized
    m401 = MagicMock(status_code=401, text='{"detail":{"message":"Invalid API key"}}')
    with patch("httpx.Client.get", return_value=m401):
        res = tts.verify_voice()
        assert res["ok"] is False
        assert res["status"] == "UNAUTHORIZED"

    # 403 Forbidden
    m403 = MagicMock(status_code=403, text='{"detail":{"message":"Voice access denied"}}')
    with patch("httpx.Client.get", return_value=m403):
        res = tts.verify_voice()
        assert res["ok"] is False
        assert res["status"] == "FORBIDDEN"

    # 404 Not Found
    m404 = MagicMock(status_code=404, text='{"detail":{"message":"Voice not found"}}')
    with patch("httpx.Client.get", return_value=m404):
        res = tts.verify_voice()
        assert res["ok"] is False
        assert res["status"] == "NOT_FOUND"

    # 429 Rate limited / quota
    m429 = MagicMock(status_code=429, text='{"detail":{"message":"Quota exceeded"}}')
    with patch("httpx.Client.get", return_value=m429):
        res = tts.verify_voice()
        assert res["ok"] is False
        assert res["status"] == "RATE_LIMITED"


def test_probe_output():
    """probe() uses verify_voice to format human-readable status."""
    tts = ElevenLabsTTS({"api_key": "test-key", "voice_id": "ibbx9zDYGvLgtYzRbqqG"})
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"name": "JARVIS Custom", "category": "custom"}

    with patch("httpx.Client.get", return_value=mock_resp):
        ok, msg = tts.probe()
        assert ok is True
        assert "JARVIS Custom" in msg
        assert "ibbx9zDYGvLgtYzRbqqG" in msg


def test_streaming_synthesis_pcm_chunks():
    """Streaming PCM synthesis slices bytes into 2400-byte chunks (50ms slices)."""
    async def _run():
        tts = ElevenLabsTTS({"api_key": "test-key", "voice_id": "ibbx9zDYGvLgtYzRbqqG"})

        # Produce 4800 bytes of mock 16-bit PCM audio (2 slices of 2400 bytes)
        mock_pcm_bytes = b"\x00\x01" * 2400  # 4800 bytes

        class MockStreamContext:
            def __init__(self, *args, **kwargs):
                self.status_code = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def aiter_bytes(self):
                # Stream in two 2400-byte deliveries
                yield mock_pcm_bytes[:2400]
                yield mock_pcm_bytes[2400:]

        with patch("httpx.AsyncClient.stream", side_effect=lambda *args, **kw: MockStreamContext()):
            received = []
            async for chunk in tts.speak("Good evening, sir."):
                received.append(chunk)

            total_bytes = sum(len(c) for c in received)
            assert total_bytes == 4800
            # Each yielded slice should be <= 2400 bytes
            for c in received:
                assert len(c) <= 2400

    asyncio.run(_run())


def test_stream_sentences():
    """stream_sentences splits incoming text chunks on sentence endings and yields audio."""
    async def _run():
        tts = ElevenLabsTTS({"api_key": "test-key", "voice_id": "ibbx9zDYGvLgtYzRbqqG"})

        spoken_sentences = []
        async def mock_speak(text, voice="", cl=None):
            spoken_sentences.append(text)
            yield b"\x00\x00" * 1200  # 2400 bytes mock PCM

        tts.speak = mock_speak

        async def text_generator():
            yield "Good "
            yield "evening, "
            yield "sir. "
            yield "JARVIS "
            yield "systems are online."

        audio_chunks = []
        async for pcm in tts.stream_sentences(text_generator()):
            audio_chunks.append(pcm)

        assert len(spoken_sentences) == 2
        assert spoken_sentences[0] == "Good evening, sir."
        assert spoken_sentences[1] == "JARVIS systems are online."
        assert len(audio_chunks) == 2

    asyncio.run(_run())


def test_speech_output_mode_config():
    """Speech output mode switches between gemini and elevenlabs independently of Gemini voice."""
    initial_mode = get_speech_output_mode()
    initial_gemini_voice = get_voice()

    try:
        save_speech_output_mode("elevenlabs")
        assert get_speech_output_mode() == "elevenlabs"

        # Gemini prebuilt voice must remain intact
        assert get_voice() == initial_gemini_voice
        assert get_voice() in AVAILABLE_VOICES

        # Voice ID getter returns default if unset
        assert get_elevenlabs_voice_id() == DEFAULT_VOICE_ID

        save_elevenlabs_voice_id("new-voice-id-456")
        assert get_elevenlabs_voice_id() == "new-voice-id-456"
    finally:
        save_speech_output_mode(initial_mode)
        save_elevenlabs_voice_id(DEFAULT_VOICE_ID)
