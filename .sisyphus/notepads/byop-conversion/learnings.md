# Learnings — BYOP Conversion

## Codebase Patterns
- Config: `app/core/config.py` uses plain `os.environ.get("VAR", "default")` — no pydantic-settings
- Services receive settings via `from app.core.config import settings`
- Background tasks: plain functions passed to `BackgroundTasks.add_task()` — args must be explicit params
- OpenAI client pattern (from llm.py line 65): `client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)`
- Transcription output: `{text: str, segments: [{start, end, text}]}` stored in `audio.mp3.json`
- Raw transcription: `audio.mp3_raw.json` contains `{words: [{word, start, end}]}` — used by SubtitleService
- Frontend: vanilla JS, no framework, state in-memory (DOMContentLoaded closure in app.js)
- Frontend API calls: `fetch()` via asyncOperation (fire-and-forget) for AI tasks

## Pollinations API Facts
- Base URL: `https://gen.pollinations.ai`
- OpenAI-compatible: use OpenAI SDK with base_url set
- Transcription endpoint: `POST /v1/audio/transcriptions`
- Models: whisper-large-v3, scribe (ElevenLabs Scribe v2)
- Auth header: `Authorization: Bearer YOUR_API_KEY`
- LLM models: `openai` (free), `openai-large` (paid)
- 402 = Insufficient balance, 401 = Bad/expired key

## BYOP Auth Flow
- Redirect: `https://enter.pollinations.ai/authorize?redirect_url=...&app_key=pk_...`
- Return: `https://myapp.com#api_key=sk_abc123` (URL fragment, not query param)
- Keys expire: 30 days

## Phase 0 Verification Results (2026-03-07)
- OpenAI SDK v2.26.0 does NOT auto-append `/v1` to base_url — must use `https://gen.pollinations.ai/v1`
- `whisper-large-v3` on Pollinations: returns `"words": []` (EMPTY) even with `timestamp_granularities=["word", "segment"]`
- `scribe` (ElevenLabs Scribe v2) on Pollinations: returns POPULATED `words` array with exact schema `{word: str, start: float, end: float}`
- `scribe` model is the ONLY viable model for word-level timestamps on Pollinations
- Both models return `segments` array with compatible schema `{start: float, end: float, text: str}` (plus extra keys like `id`, `tokens`, etc.)
- Segments have extra keys (`id`, `avg_logprob`, `compression_ratio`, `no_speech_prob`, `seek`, `temperature`, `tokens`) — harmless, ignored by codebase
- Timestamp units: SECONDS (not milliseconds) — same as Groq Whisper
- `scribe` returns `language: "eng"` (ISO 639-3) vs Groq's `language: "en"` (ISO 639-1) — cosmetic, not load-bearing
- No normalization layer needed for `model=scribe` — schema is a direct match
- CRITICAL: Must change model from `whisper-large-v3` to `scribe` in transcription.py when switching to Pollinations


## Phase 1 — endpoints.py Wiring (2026-03-07)
- `get_api_key(request)` checks `Authorization: Bearer <token>` first, falls back to `X-Pollinations-Key` header, raises 401 if neither
- Background task functions receive `api_key` as EXPLICIT last positional arg — Request object is dead after response
- Error catch order matters: `AuthenticationError` → `APIStatusError` (check `.status_code == 402`) → generic `Exception`
- `AuthenticationError` and `APIStatusError` are importable directly from `openai` (SDK v2.26.0)
- `process_project` endpoint calls `transcribe_project` and `analyze_project` — both extract `api_key` from `request` independently, which works because `process_project` passes `request` through
- `GET /config/pollinations` is a simple config endpoint — no auth needed, returns `app_key` and `auth_url`

## Phase 2 — Frontend Integration (2026-03-07)
- In api.js, when appending error handling for 401/402, use `typeof PollinationsAuth !== 'undefined'` to safely check if the module loaded, due to async/deferred script execution order.
- In app.js, placing an IIFE (Immediately Invoked Function Expression) before `DOMContentLoaded` guarantees that the globally exposed module is available when callbacks trigger.
- In frontend apps, passing Auth Bearer headers manually in fetch calls is necessary when not relying on cookies, extracting tokens from URL fragments during OAuth callbacks.