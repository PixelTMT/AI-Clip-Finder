# Decisions — BYOP Conversion

## ADR-1: Auth Mode
BYOP Only. All AI features require Pollinations auth. $0 server cost.

## ADR-2: Transcription Provider
Migrate from Groq to Pollinations whisper-large-v3 (with scribe fallback).
Phase 0 is a blocking gate to verify schema compatibility.

## ADR-3: Identity Model Under HOSTING
Keep cookie-based user_id for project ownership. BYOP key is for AI calls only.
Two independent systems — do NOT conflate them.

## ADR-4: App Key Placement
POLLINATIONS_APP_KEY in `.env` → read by backend settings → served to frontend via `GET /config/pollinations`.
This is a publishable key (pk_), not a secret.

## ADR-5: Default LLM Model
Changed from `openai-large` (paid) to `openai` (free-tier GPT-5 Mini).
Operators can override via LLM_MODEL env var.
