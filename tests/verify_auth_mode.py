import importlib
import os
import sys
from pathlib import Path

# Allow running as a standalone script from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from starlette.requests import Request

import app.api.endpoints as endpoints_module
import app.core.config as config_module

_ORIGINAL_ENV = {
    k: os.environ.get(k)
    for k in (
        "HOSTING",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "TRANSCRIBE_API_KEY",
        "TRANSCRIBE_BASE_URL",
        "TRANSCRIBE_MODEL",
    )
}


def set_env(hosting: str, llm_key: str) -> None:
    """Apply env vars and reload the config/endpoints modules to re-evaluate BYOP."""
    os.environ["HOSTING"] = hosting
    os.environ["LLM_API_KEY"] = llm_key
    importlib.reload(config_module)
    importlib.reload(endpoints_module)


def restore_env() -> None:
    for key, value in _ORIGINAL_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(config_module)
    importlib.reload(endpoints_module)


def make_request(headers: dict | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": raw, "query_string": b""})


def test_byop_activation_truth_table():
    """BYOP is on only when HOSTING=true and no server-side LLM_API_KEY exists."""
    cases = [
        ("true", "", True),
        ("true", "sk_server_key", False),
        ("false", "", False),
        ("false", "sk_server_key", False),
    ]
    for hosting, llm_key, expected in cases:
        set_env(hosting, llm_key)
        actual = config_module.settings.BYOP
        assert actual is expected, f"HOSTING={hosting} LLM_API_KEY={llm_key!r}: {actual} != {expected}"


def test_server_key_mode_ignores_client_header():
    """BYOP off: server key is used, client headers are irrelevant."""
    set_env("false", "sk_server_key")
    key = endpoints_module.get_api_key(make_request({"Authorization": "Bearer sk_user_key"}))
    assert key == "sk_server_key", key


def test_server_key_mode_without_configured_key_is_loud():
    """BYOP off and no key at all: sentinel returned, no silent empty string."""
    set_env("false", "")
    key = endpoints_module.get_api_key(make_request())
    assert key == "no-key-configured", key


def test_byop_mode_requires_client_key():
    """BYOP on: bearer header wins, else 401."""
    set_env("true", "")
    key = endpoints_module.get_api_key(make_request({"Authorization": "Bearer sk_user_key"}))
    assert key == "sk_user_key", key

    key = endpoints_module.get_api_key(make_request({"X-Pollinations-Key": "sk_alt"}))
    assert key == "sk_alt", key

    try:
        endpoints_module.get_api_key(make_request())
    except HTTPException as exc:
        assert exc.status_code == 401, exc.status_code
    else:
        raise AssertionError("expected 401 when BYOP is active and no key is sent")


def test_transcription_uses_dedicated_settings_with_llm_fallback():
    """Transcription reads TRANSCRIBE_* settings, falling back to the LLM ones."""
    os.environ["HOSTING"] = "false"
    os.environ["LLM_API_KEY"] = "sk_llm"
    os.environ["LLM_BASE_URL"] = "http://llm.local/v1"
    os.environ.pop("TRANSCRIBE_API_KEY", None)
    os.environ.pop("TRANSCRIBE_BASE_URL", None)
    os.environ.pop("TRANSCRIBE_MODEL", None)
    importlib.reload(config_module)
    importlib.reload(endpoints_module)

    request = make_request()
    assert endpoints_module.get_api_key(request) == "sk_llm"
    assert endpoints_module.get_api_key(request, transcribe=True) == "sk_llm"
    assert config_module.settings.TRANSCRIBE_BASE_URL == "http://llm.local/v1"
    assert config_module.settings.TRANSCRIBE_MODEL == "whisper-large-v3"

    os.environ["TRANSCRIBE_API_KEY"] = "sk_transcribe"
    os.environ["TRANSCRIBE_BASE_URL"] = "http://transcribe.local/v1"
    os.environ["TRANSCRIBE_MODEL"] = "scribe"
    importlib.reload(config_module)
    importlib.reload(endpoints_module)

    request = make_request()
    assert endpoints_module.get_api_key(request) == "sk_llm", "analysis key must not change"
    assert endpoints_module.get_api_key(request, transcribe=True) == "sk_transcribe"
    assert config_module.settings.TRANSCRIBE_BASE_URL == "http://transcribe.local/v1"
    assert config_module.settings.TRANSCRIBE_MODEL == "scribe"


if __name__ == "__main__":
    try:
        test_byop_activation_truth_table()
        test_server_key_mode_ignores_client_header()
        test_server_key_mode_without_configured_key_is_loud()
        test_byop_mode_requires_client_key()
        test_transcription_uses_dedicated_settings_with_llm_fallback()
    finally:
        restore_env()
    print("OK: auth mode checks passed")
