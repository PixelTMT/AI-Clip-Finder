# Issues & Problems — BYOP Conversion

## Critical Guardrails (from Metis)
1. Schema normalization is mandatory in transcription.py — SubtitleService depends on exact word key names
2. Background task functions receive api_key as EXPLICIT ARGUMENT — not from Request (Request is dead after response sent)
3. asyncOperation in api.js must detect 401/402 specifically — not just generic error handling
4. groq stays in requirements.txt until Phase 0 verification passes (rollback path)
5. Editor page is OUT OF SCOPE — do not touch editor.html or editor.js

## Known Risks
- Pollinations verbose_json support: CONFIRMED working, but `whisper-large-v3` returns EMPTY words array
- audio.mp3_raw.json schema mismatch: RESOLVED — `scribe` model returns exact same schema, no mismatch
- 402 insufficient balance needs dedicated error path (not generic "error")

## Tasks Completed
- Phase 0 blocking gate: PASSED (2026-03-07) — `scribe` model returns compatible schema, `whisper-large-v3` does NOT (empty words)

## Phase 0 Decisions
- Must use `model="scribe"` (NOT `whisper-large-v3`) for Pollinations transcription
- No normalization layer needed — schema is a direct match with `{word, start, end}` keys
- OpenAI SDK base_url must be `https://gen.pollinations.ai/v1` (SDK does NOT auto-append /v1)
- Guardrail #1 (schema normalization) is satisfied WITHOUT extra code for `scribe` model
- Guardrail #4 (keep groq in requirements.txt) still applies until full migration verified
