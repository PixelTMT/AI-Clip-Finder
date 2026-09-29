"""Verifies AI calls use the endpoints/models from settings, not a hardcoded host.

Regression guard for the bug where transcription silently posted to
``LLM_BASE_URL`` (whose value was shadowed by a machine-wide environment
variable) instead of the configured transcription endpoint.
"""

import os
import sys
import tempfile
from pathlib import Path

# Allow running as a standalone script from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.llm as llm_module
import app.services.transcription as transcription_module
from app.core.config import settings

captured = {}


class _FakeTranscription:
    def model_dump(self):
        return {
            "text": "hi",
            "segments": [{"start": 0.0, "end": 1.0, "text": "hi"}],
            "words": [{"word": "hi", "start": 0.0, "end": 1.0}],
        }


class _FakeTranscriptions:
    def create(self, **kwargs):
        captured["transcribe_kwargs"] = kwargs
        return _FakeTranscription()


class _FakeAudio:
    transcriptions = _FakeTranscriptions()


class _FakeMessage:
    content = "[]"


class _FakeChoice:
    message = _FakeMessage()


class _FakeCompletion:
    choices = [_FakeChoice()]


class _FakeChatCompletions:
    def create(self, **kwargs):
        captured["llm_kwargs"] = kwargs
        return _FakeCompletion()


class _FakeChat:
    completions = _FakeChatCompletions()


class _RecordingOpenAI:
    """Records constructor args, then mimics the client surface the services use."""

    def __init__(self, base_url=None, api_key=None):
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        self.audio = _FakeAudio()
        self.chat = _FakeChat()


def test_transcription_and_llm_use_resolved_settings():
    original_transcription_client = transcription_module.OpenAI
    original_llm_client = llm_module.OpenAI
    transcription_module.OpenAI = _RecordingOpenAI
    llm_module.OpenAI = _RecordingOpenAI
    try:
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "audio.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake")
            transcription_module.transcribe_audio(audio_path, api_key="sk_key")
        assert captured["base_url"] == settings.TRANSCRIBE_BASE_URL, captured
        assert captured["api_key"] == "sk_key", captured
        assert captured["transcribe_kwargs"]["model"] == settings.TRANSCRIBE_MODEL, captured

        llm_module.analyze_transcript({"text": "hi", "segments": []}, api_key="sk_key")
        assert captured["base_url"] == settings.LLM_BASE_URL, captured
        assert captured["api_key"] == "sk_key", captured
        assert captured["llm_kwargs"]["model"] == settings.LLM_MODEL, captured
    finally:
        transcription_module.OpenAI = original_transcription_client
        llm_module.OpenAI = original_llm_client


if __name__ == "__main__":
    print(f"resolved llm         : {settings.LLM_BASE_URL} model={settings.LLM_MODEL}")
    print(
        f"resolved transcribe  : {settings.TRANSCRIBE_BASE_URL} "
        f"model={settings.TRANSCRIBE_MODEL}"
    )
    test_transcription_and_llm_use_resolved_settings()
    print("OK: transcription routing checks passed")
