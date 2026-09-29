# Plan: BYOP (Bring Your Own Pollen) Conversion

## Objective
Convert AI-Clip-Finder from server-side API keys to BYOP model where users authenticate with Pollinations, get their own API key, and pay for their own AI usage. Server cost: $0.

## Scope

### IN
- Frontend BYOP auth flow (connect button, redirect, key storage)
- Backend API key passthrough (endpoints accept user key, forward to services)
- Transcription migration: Groq SDK → Pollinations API (OpenAI SDK)
- LLM service: accept dynamic API key instead of server-side config
- Config cleanup: remove server-side AI keys, add POLLINATIONS_APP_KEY
- Error handling: 401 (expired key), 402 (insufficient balance)
- Schema normalization layer for transcription response compatibility

### OUT
- Editor page (editor.html/editor.js) — consumes already-processed data, no AI calls
- Media processing pipeline (FFmpeg, compression, rendering)
- Subtitle service internals (SubtitleService, SentenceBuilder) — only the data contract matters
- HOSTING mode identity model changes — cookie-based user_id preserved as-is
- Clip render service — no AI dependency

## Architecture Decision Records

### ADR-1: Auth Mode
**Decision**: BYOP Only. All AI features (transcribe + analyze) require Pollinations auth.
**Rationale**: $0 server cost, no key management, self-regulating usage.

### ADR-2: Transcription Provider
**Decision**: Migrate from Groq to Pollinations whisper-large-v3 (with scribe fallback).
**Rationale**: Single provider, single API key, unified billing for user.
**Risk**: verbose_json word-level timestamps unconfirmed → mitigated by schema normalization layer and Phase 0 verification.

### ADR-3: Identity Model Under HOSTING
**Decision**: Keep cookie-based user_id for project ownership. BYOP key is for AI calls only.
**Rationale**: Simplest to implement, no project migration needed, separation of concerns (identity ≠ billing).

### ADR-4: App Key Placement
**Decision**: POLLINATIONS_APP_KEY in `.env`, read by backend, served to frontend via a config endpoint or embedded in HTML template.
**Rationale**: User requested env-based config. Backend reads it and can inject into HTML or serve via `/config` endpoint. Not a secret (publishable key).

### ADR-5: Default LLM Model
**Decision**: Change default LLM_MODEL from `openai-large` (paid) to `openai` (free-tier GPT-5 Mini).
**Rationale**: With BYOP, user pays. Defaulting to a paid model without clear consent is poor UX. Operators can override via env.

## Key Files (Modification Map)

| File | Change Type | Description |
|------|-------------|-------------|
| `app/core/config.py` | MODIFY | Add POLLINATIONS_APP_KEY, remove GROQ_API_KEY dependency, change LLM_MODEL default |
| `app/services/transcription.py` | REWRITE | Replace Groq SDK with OpenAI SDK pointing to Pollinations, add schema normalization |
| `app/services/llm.py` | MODIFY | Accept api_key parameter, instantiate client per-call |
| `app/api/endpoints.py` | MODIFY | Extract API key from request headers, pass to background tasks, add 401 guard |
| `app/static/index.html` | MODIFY | Add BYOP auth button and status indicator in header |
| `app/static/js/app.js` | MODIFY | Add auth flow (redirect, key parse, localStorage), key injection in API calls, 401/402 handlers |
| `app/static/js/api.js` | MODIFY | Add API key header injection, 401/402 specific error handling |
| `app/static/css/style.css` | MODIFY | Styles for auth button and status indicator |
| `requirements.txt` | MODIFY | Remove groq dependency |
| `.env.example` | MODIFY | Update env vars |
| `README.md` | MODIFY | Update setup instructions, remove Groq references |

## Constraints & Guardrails

1. **Schema Normalization Is Mandatory**: Transcription response MUST be normalized to canonical shape `{text, segments[{start,end,text}]}` with raw saved as `{words[{word,start,end}]}` regardless of upstream format.
2. **API Key Must Be Function Argument**: Background tasks (`process_transcribe_background`, `process_analyze_background`) receive api_key as explicit parameter — NOT read from Request object (Request is invalid after response sent).
3. **No Secret Keys In Frontend**: Only publishable `pk_` keys in frontend. User's `sk_` key stored in localStorage, transmitted via header.
4. **Groq Stays In requirements.txt Until Verification**: Keep `groq` package commented until Pollinations transcription schema is verified in Phase 0.
5. **Editor Page Is Read-Only Scope**: No modifications to editor.html or editor.js.

---

## Phase 0: Verification Gate (BLOCKING)

> **Nothing in Phase 1-3 may proceed until Phase 0 passes.**

### Task 0.1: Verify Pollinations Transcription API Schema
**File**: Create `tests/verify_pollinations_transcription.py` (temporary test script)
**What**:
1. Use the OpenAI SDK with `base_url="https://gen.pollinations.ai"` and a valid API key
2. Call `client.audio.transcriptions.create()` with a sample MP3 file, model `whisper-large-v3`
3. Try `response_format="verbose_json"` — if rejected, try without it
4. Log the FULL raw response JSON
5. Verify the response contains:
   - Top-level `text` field (string)
   - `segments` array with objects having `start` (float), `end` (float), `text` (string)
   - `words` array with objects having `word` (string), `start` (float), `end` (float)
6. Compare against current Groq output in `data/projects/*/audio.mp3_raw.json` (if any exist)

**Expected Outcome**: Either PASS (schema matches) or FAIL (schema differs, document exact differences).

**If FAIL**: Create a normalization mapping document showing:
- Source key → Target key for each field
- Any missing fields and how to derive them
- Whether `scribe` model provides better compatibility

**QA**:
- Script runs without error
- Output logged to console shows raw response structure
- Comparison document produced if schema differs

### Task 0.2: Verify Pollinations Transcription Word Timestamps
**File**: Same script as Task 0.1
**What**:
1. Specifically verify that word-level timestamps are available
2. Check key names: `word` vs `text`, `start` vs `start_time`, `end` vs `end_time`
3. Verify timestamp precision (float seconds, not milliseconds)
4. Check if words array is at top level or nested under segments

**Expected Outcome**: Document confirming word-level timestamp availability and exact schema.

**QA**:
- Word-level timestamps confirmed present
- Key names and types documented
- Timestamp unit confirmed as seconds (float)

---

## Phase 1: Backend — API Key Passthrough & Transcription Migration

### Task 1.1: Update Config Settings
**File**: `app/core/config.py`
**What**:
1. Add `POLLINATIONS_APP_KEY = os.environ.get("POLLINATIONS_APP_KEY", "")` — publishable key for auth redirect
2. Add `POLLINATIONS_BASE_URL = os.environ.get("POLLINATIONS_BASE_URL", "https://gen.pollinations.ai")` — single source of truth for Pollinations base URL (replaces LLM_BASE_URL for clarity, but keep LLM_BASE_URL as alias)
3. Change `LLM_MODEL` default from `"openai-large"` to `"openai"` (free-tier)
4. Remove the hardcoded `LLM_API_KEY` default — it's now per-user
5. Keep `LLM_BASE_URL` defaulting to `"https://gen.pollinations.ai/v1"` (backward compat)
6. Remove `GROQ_API_KEY` dependency (no longer imported anywhere)

**Pattern Reference**: Current `config.py` lines 12-15 for env var style.

**QA**:
- `settings.POLLINATIONS_APP_KEY` returns value from env
- `settings.LLM_MODEL` defaults to `"openai"`
- No reference to `GROQ_API_KEY` in config
- `settings.LLM_BASE_URL` still defaults to Pollinations

### Task 1.2: Add API Key Extraction Utility
**File**: `app/api/endpoints.py`
**What**:
1. Create a helper function `get_api_key(request: Request) -> str` that:
   - Checks `Authorization` header for `Bearer sk_...` format
   - Falls back to `X-Pollinations-Key` custom header
   - Raises `HTTPException(status_code=401, detail="Pollinations API key required. Connect with Pollinations first.")` if neither present
2. This function is called in `/transcribe` and `/analyze` endpoints BEFORE starting background tasks

**Pattern Reference**: Current `get_user_project()` helper at endpoints.py line 22 for style.

**QA**:
- Request with `Authorization: Bearer sk_test` → returns `"sk_test"`
- Request with `X-Pollinations-Key: sk_test` → returns `"sk_test"`
- Request with neither header → raises 401
- Request with `Authorization: Bearer pk_test` → still returns it (validation is Pollinations' job)

### Task 1.3: Update Transcribe Endpoint to Accept API Key
**File**: `app/api/endpoints.py`
**What**:
1. In `transcribe_project()` (line 252): call `api_key = get_api_key(request)` before starting background task
2. Pass `api_key` as argument to `process_transcribe_background()`:
   ```python
   background_tasks.add_task(
       process_transcribe_background, project_id, video_path, audio_path, api_key
   )
   ```
3. Update `process_transcribe_background()` signature (line 210) to accept `api_key: str` parameter
4. Pass `api_key` to `transcription.transcribe_audio(audio_path, api_key=api_key)`

**QA**:
- Endpoint without API key header returns 401
- Endpoint with valid header starts background task
- `api_key` is passed through to transcription service

### Task 1.4: Update Analyze Endpoint to Accept API Key
**File**: `app/api/endpoints.py`
**What**:
1. In `analyze_project()` (line 348): call `api_key = get_api_key(request)` before starting background task
2. Pass `api_key` as argument to `process_analyze_background()`:
   ```python
   background_tasks.add_task(
       process_analyze_background, project_id, project_path, video_path,
       transcript, custom_prompt, clip_count, api_key
   )
   ```
3. Update `process_analyze_background()` signature (line 289) to accept `api_key: str` parameter
4. Pass `api_key` to `llm.analyze_transcript(transcript, custom_instructions=custom_prompt, clip_count=clip_count, api_key=api_key)`

**QA**:
- Endpoint without API key header returns 401
- Endpoint with valid header starts background task
- `api_key` is passed through to LLM service

### Task 1.5: Rewrite Transcription Service for Pollinations
**File**: `app/services/transcription.py`
**What**:
1. Replace `from groq import Groq` with `from openai import OpenAI`
2. Update `transcribe_audio()` signature: `def transcribe_audio(file_path: str, api_key: str) -> dict`
3. Create OpenAI client pointing to Pollinations:
   ```python
   client = OpenAI(
       base_url=settings.LLM_BASE_URL.replace("/v1", ""),  # needs base without /v1 for audio
       api_key=api_key
   )
   ```
   Note: Check if Pollinations audio endpoint uses `/v1/audio/transcriptions` — if so, keep `/v1` in base_url.
4. Call transcription:
   ```python
   transcription = client.audio.transcriptions.create(
       file=open(file_path, "rb"),
       model="whisper-large-v3",
       response_format="verbose_json",
       timestamp_granularities=["word", "segment"],
       language="en",
       temperature=0.0
   )
   ```
5. Add schema normalization function `normalize_transcription_response(data: dict) -> dict` that:
   - Ensures `text` key exists (string)
   - Ensures `segments` array exists with `{start, end, text}` objects
   - Ensures top-level (or extracts from segments) `words` array with `{word, start, end}` objects
   - Handles key name differences (e.g., `start_time` → `start`)
   - Logs warnings for any fields that needed normalization
6. Apply normalization before caching
7. Keep the caching pattern (check for `.json` cache, write `_raw.json` and `.json`)

**Critical**: The `_raw.json` file must contain the `words` array — this is consumed by `SubtitleService.load_raw_transcript()` and `clip_endpoints.py` line 43.

**Pattern Reference**: Current `llm.py` line 65 for OpenAI client instantiation.

**QA**:
- Function accepts `api_key` parameter
- Uses OpenAI SDK, not Groq SDK
- Points to Pollinations base URL
- Output contains `text`, `segments[{start,end,text}]`
- Raw output contains `words[{word,start,end}]`
- Cache files written correctly
- Invalid API key results in exception (caught by background task handler)

### Task 1.6: Update LLM Service to Accept Dynamic API Key
**File**: `app/services/llm.py`
**What**:
1. Update `analyze_transcript()` signature (line 60) to accept `api_key: str` parameter:
   ```python
   def analyze_transcript(
       transcript_data: dict,
       custom_instructions: Optional[str] = None,
       clip_count: Optional[int] = None,
       api_key: str = "dummy",
   ) -> list:
   ```
2. Update client instantiation (line 65) to use the passed api_key:
   ```python
   client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=api_key)
   ```
3. Keep everything else unchanged — model, temperature, prompts, response parsing all stay the same.

**QA**:
- Function accepts `api_key` parameter
- Client uses passed `api_key` not `settings.LLM_API_KEY`
- `settings.LLM_BASE_URL` still used for base URL
- All existing JSON parsing and validation logic preserved
- `if __name__ == "__main__"` block still works (may need a test key or skip)

### Task 1.7: Add Frontend Config Endpoint
**File**: `app/api/endpoints.py`
**What**:
1. Add a new endpoint `GET /config/pollinations` that returns public configuration:
   ```python
   @router.get("/config/pollinations")
   async def get_pollinations_config():
       return {
           "app_key": settings.POLLINATIONS_APP_KEY,
           "auth_url": "https://enter.pollinations.ai/authorize",
       }
   ```
2. This allows the frontend to build the auth redirect URL dynamically without hardcoding the app_key in JS.

**QA**:
- Endpoint returns JSON with `app_key` and `auth_url`
- No authentication required for this endpoint
- Does not expose secret keys

### Task 1.8: Add Specific Error Handling for Pollinations API Errors
**File**: `app/api/endpoints.py`
**What**:
1. In `process_transcribe_background()`: wrap the transcription call in a try/except that catches `openai.AuthenticationError` (401) and `openai.APIStatusError` with status 402:
   ```python
   from openai import AuthenticationError, APIStatusError

   try:
       transcript = transcription.transcribe_audio(audio_path, api_key=api_key)
   except AuthenticationError:
       storage.update_project_status(project_id, "error", "API key expired or invalid. Please reconnect with Pollinations.")
       storage.set_active_operation(project_id, type=OperationType.TRANSCRIBE, status=OperationStatus.FAILED, message="auth_expired")
       return
   except APIStatusError as e:
       if e.status_code == 402:
           storage.update_project_status(project_id, "error", "Insufficient Pollinations balance. Please add funds.")
           storage.set_active_operation(project_id, type=OperationType.TRANSCRIBE, status=OperationStatus.FAILED, message="insufficient_balance")
           return
       raise
   ```
2. Apply same pattern in `process_analyze_background()`
3. Use specific `message` values (`"auth_expired"`, `"insufficient_balance"`) that the frontend can detect and show actionable UI.

**QA**:
- 401 from Pollinations → project status error with "auth_expired" message
- 402 from Pollinations → project status error with "insufficient_balance" message
- Other errors → standard error handling preserved

---

## Phase 2: Frontend — BYOP Auth Flow & Key Management

### Task 2.1: Add Auth UI Elements to Header
**File**: `app/static/index.html`
**What**:
1. In the `<header>` element (line 10-16), add auth elements BEFORE the upload section:
   ```html
   <div id="auth-section">
     <button id="btn-connect-pollinations" class="auth-btn">
       Connect with Pollinations
     </button>
     <div id="auth-status" class="hidden">
       <span class="auth-indicator"></span>
       <span id="auth-status-text">Connected</span>
       <button id="btn-disconnect" class="auth-disconnect-btn" title="Disconnect">×</button>
     </div>
   </div>
   ```
2. The `#btn-connect-pollinations` is visible when NOT authenticated
3. The `#auth-status` is visible when authenticated (shows status + disconnect button)
4. The `#upload-section` should be visually grouped with auth (both in header)

**QA**:
- Auth button visible on page load (no key in localStorage)
- Auth status hidden on page load
- Elements are properly nested in header

### Task 2.2: Add Auth Styles
**File**: `app/static/css/style.css`
**What**:
1. Add styles for `.auth-btn` — prominent, branded button (green/teal Pollinations color)
2. Add styles for `#auth-status` — compact inline status with green dot indicator
3. Add styles for `.auth-disconnect-btn` — small × button
4. Add styles for `.auth-indicator` — small green circle (connected) or red (expired)
5. Add disabled state styles for `#upload-section` and action buttons when not authenticated

**Pattern Reference**: Follow existing `.action-btn` style patterns in current CSS.

**QA**:
- Button is visually prominent in header
- Connected state shows green indicator
- Styles match dark-mode theme of existing app

### Task 2.3: Implement Auth Flow in app.js
**File**: `app/static/js/app.js`
**What**:
1. At the TOP of the `DOMContentLoaded` handler, add auth state management:
   ```javascript
   // Auth State
   const AUTH_KEY = 'pollinations_api_key';
   const AUTH_EXPIRY_KEY = 'pollinations_key_expiry';

   function getApiKey() {
       return localStorage.getItem(AUTH_KEY);
   }

   function setApiKey(key) {
       localStorage.setItem(AUTH_KEY, key);
       // Keys expire in 30 days from issuance
       const expiry = new Date();
       expiry.setDate(expiry.getDate() + 30);
       localStorage.setItem(AUTH_EXPIRY_KEY, expiry.toISOString());
       updateAuthUI();
   }

   function clearApiKey() {
       localStorage.removeItem(AUTH_KEY);
       localStorage.removeItem(AUTH_EXPIRY_KEY);
       updateAuthUI();
   }

   function isAuthenticated() {
       const key = getApiKey();
       if (!key) return false;
       const expiry = localStorage.getItem(AUTH_EXPIRY_KEY);
       if (expiry && new Date(expiry) < new Date()) {
           clearApiKey();
           return false;
       }
       return true;
   }
   ```

2. Add auth UI update function:
   ```javascript
   function updateAuthUI() {
       const connectBtn = document.getElementById('btn-connect-pollinations');
       const authStatus = document.getElementById('auth-status');
       const authText = document.getElementById('auth-status-text');
       const uploadSection = document.getElementById('upload-section');

       if (isAuthenticated()) {
           connectBtn.classList.add('hidden');
           authStatus.classList.remove('hidden');
           uploadSection.style.opacity = '1';
           uploadSection.style.pointerEvents = 'auto';

           // Show expiry info
           const expiry = localStorage.getItem(AUTH_EXPIRY_KEY);
           if (expiry) {
               const days = Math.ceil((new Date(expiry) - new Date()) / (1000*60*60*24));
               authText.textContent = `Connected · ${days}d left`;
           }
       } else {
           connectBtn.classList.remove('hidden');
           authStatus.classList.add('hidden');
           // Don't disable upload — project creation doesn't need auth, only AI calls do
       }

       // Update AI action buttons
       updateAIButtonStates();
   }
   ```

3. Add connect button handler:
   ```javascript
   async function connectWithPollinations() {
       // Fetch app_key from backend config
       const res = await fetch('/config/pollinations');
       const config = await res.json();

       const params = new URLSearchParams({
           redirect_url: window.location.origin + window.location.pathname,
       });
       if (config.app_key) {
           params.set('app_key', config.app_key);
       }
       window.location.href = `${config.auth_url}?${params}`;
   }
   ```

4. Add URL fragment parser (runs on page load):
   ```javascript
   // Check for API key in URL fragment (after Pollinations redirect)
   function checkAuthRedirect() {
       const hash = window.location.hash;
       if (hash && hash.includes('api_key=')) {
           const params = new URLSearchParams(hash.slice(1));
           const apiKey = params.get('api_key');
           if (apiKey) {
               setApiKey(apiKey);
               showToast('Connected with Pollinations!', 'success');
               // Clean URL fragment
               history.replaceState(null, '', window.location.pathname);
           }
       }
   }
   ```

5. Add disconnect handler:
   ```javascript
   document.getElementById('btn-disconnect').onclick = () => {
       if (confirm('Disconnect from Pollinations? AI features will be unavailable.')) {
           clearApiKey();
           showToast('Disconnected from Pollinations', 'info');
       }
   };
   ```

6. Add `updateAIButtonStates()` function that disables Transcribe and Find Clips buttons when not authenticated, showing tooltip "Connect with Pollinations first"

7. Wire up: call `checkAuthRedirect()` then `updateAuthUI()` at top of DOMContentLoaded.

8. Wire up: `document.getElementById('btn-connect-pollinations').onclick = connectWithPollinations;`

**QA**:
- On fresh load (no key): Connect button visible, AI buttons show "connect first" tooltip
- After auth redirect with `#api_key=sk_test`: key stored in localStorage, status shows "Connected · 30d left", Connect button hidden
- Disconnect: clears localStorage, Connect button reappears
- Expired key: detected on page load, auto-cleared, Connect button shown

### Task 2.4: Inject API Key Into API Calls
**File**: `app/static/js/app.js`
**What**:
1. Update `startTranscription()` to include API key header:
   ```javascript
   async function startTranscription(projectId) {
       if (!isAuthenticated()) {
           showToast('Connect with Pollinations first', 'error');
           return;
       }
       asyncOperation(`/projects/${projectId}/transcribe`, {
           method: 'POST',
           headers: { 'Authorization': `Bearer ${getApiKey()}` }
       });
   }
   ```
2. Update `startAnalysis()` similarly:
   ```javascript
   async function startAnalysis(projectId, customPrompt, clipCount) {
       if (!isAuthenticated()) {
           showToast('Connect with Pollinations first', 'error');
           return;
       }
       const params = new URLSearchParams();
       if (customPrompt) params.append('custom_prompt', customPrompt);
       if (clipCount) params.append('clip_count', clipCount);
       asyncOperation(`/projects/${projectId}/analyze?${params.toString()}`, {
           method: 'POST',
           headers: { 'Authorization': `Bearer ${getApiKey()}` }
       });
   }
   ```
3. Other API calls (createProject, uploadVideo, fetchProjects, deleteProject) do NOT need the key — they are local operations.

**QA**:
- Transcribe request includes `Authorization: Bearer sk_...` header
- Analyze request includes `Authorization: Bearer sk_...` header
- Upload, create, delete, list do NOT include the header
- Calling transcribe/analyze without auth shows toast error

### Task 2.5: Add 401/402 Error Handling in asyncOperation
**File**: `app/static/js/api.js`
**What**:
1. Update `asyncOperation` to detect auth-related errors:
   ```javascript
   function asyncOperation(url, options = {}) {
       fetch(url, options)
           .then(response => {
               if (response.status === 401) {
                   // API key expired or invalid
                   if (typeof clearApiKey === 'function') clearApiKey();
                   if (window.showToast) window.showToast(
                       'Session expired. Please reconnect with Pollinations.',
                       'error',
                       10000
                   );
                   return;
               }
               if (response.status === 402) {
                   if (window.showToast) window.showToast(
                       'Insufficient Pollinations balance. Please add funds at enter.pollinations.ai',
                       'error',
                       10000
                   );
                   return;
               }
               if (!response.ok) {
                   return response.text().then(text => {
                       console.error(`Async operation failed [${url}]: ${text}`);
                       if (window.showToast) window.showToast(`Operation failed: ${text}`, 'error');
                   });
               }
               if (window.showToast) window.showToast('Operation started', 'success');
           })
           .catch(err => {
               console.error(`Network error in async operation [${url}]:`, err);
               if (window.showToast) window.showToast(`Network error: ${err.message}`, 'error');
           });
   }
   ```

2. Also detect `"auth_expired"` and `"insufficient_balance"` in the polling status messages (in `app.js` `selectProject()` where error banner is displayed):
   ```javascript
   if (project.active_operation && project.active_operation.status === 'failed') {
       const msg = project.active_operation.message;
       if (msg === 'auth_expired') {
           clearApiKey();
           showToast('Session expired. Please reconnect.', 'error');
       } else if (msg === 'insufficient_balance') {
           showToast('Insufficient balance. Top up at enter.pollinations.ai', 'error');
       }
   }
   ```

**QA**:
- 401 response → clears key, shows reconnect toast
- 402 response → shows insufficient balance toast with link
- Other errors → existing behavior preserved
- Background task failure with "auth_expired" message → clears key in frontend

---

## Phase 3: Config Cleanup & Documentation

### Task 3.1: Update .env.example
**File**: `.env.example`
**What**:
Replace current contents with:
```env
# Pollinations BYOP Configuration
POLLINATIONS_APP_KEY=pk_your_app_key_here

# LLM Settings (optional overrides)
LLM_BASE_URL=https://gen.pollinations.ai/v1
LLM_MODEL=openai

# Hosting Mode
HOSTING=true
```

Remove `GROQ_API_KEY`, `LLM_API_KEY` entries.

**QA**:
- No secret API keys in example
- POLLINATIONS_APP_KEY present with pk_ prefix
- LLM_MODEL defaults to free tier

### Task 3.2: Update requirements.txt
**File**: `requirements.txt`
**What**:
1. Remove the `groq` line
2. Keep `openai` (already present, used for both LLM and now transcription)
3. All other dependencies unchanged

Final contents:
```
fastapi
uvicorn[standard]
filelock
pydantic
python-multipart
openai
python-dotenv
```

**QA**:
- `groq` not present
- `openai` present
- All other deps preserved

### Task 3.3: Update README.md
**File**: `README.md`
**What**:
1. Update "Key Features" section: Replace "High-Speed Transcription: Integrates with Groq (Whisper-v3)" with "BYOP Transcription: Users connect their Pollinations account for AI-powered transcription"
2. Update "Tech Stack > AI Services" section: Remove Groq reference, update to "Transcription: Pollinations Whisper / Scribe", "Analysis: Pollinations LLMs (user-provided key)"
3. Update "Getting Started > Configure Environment" section: Remove GROQ_API_KEY, show POLLINATIONS_APP_KEY
4. Add a "BYOP (Bring Your Own Pollen)" section explaining:
   - Users connect with Pollinations to enable AI features
   - All AI costs borne by user
   - Keys expire in 30 days, re-auth required
   - Link to enter.pollinations.ai for app key registration
5. Update Configuration table: Remove GROQ_API_KEY, add POLLINATIONS_APP_KEY

**QA**:
- No Groq references in README
- BYOP flow explained
- Setup instructions reflect new env vars

### Task 3.4: Update Dockerfile
**File**: `Dockerfile`
**What**:
1. No changes needed — the Dockerfile doesn't reference Groq or API keys
2. Verify: `requirements.txt` is copied and installed (confirmed at line 14-18)
3. The `.env` file is NOT copied into the Docker image (confirmed by examining COPY commands)
4. For Docker deployments, env vars are passed at runtime (`-e POLLINATIONS_APP_KEY=pk_...`)

**QA**:
- Docker build succeeds with updated requirements.txt
- No hardcoded API keys in image

---

## Final Verification Wave

### Task V.1: End-to-End Flow Test
**What**: Manual verification checklist (agent-executable via browser automation if playwright available):
1. Start server: `uv run uvicorn app.main:app --reload`
2. Open `http://localhost:8000` — verify Connect button visible
3. Click Connect → verify redirect to `enter.pollinations.ai/authorize?redirect_url=...&app_key=pk_...`
4. After auth redirect → verify key stored, status shows "Connected"
5. Create project, upload video → verify upload works (no auth needed)
6. Click Transcribe → verify Authorization header sent, transcription starts
7. After transcription → verify transcript displayed with segments
8. Click Find Clips → verify Authorization header sent, analysis starts
9. After analysis → verify clips displayed with thumbnails
10. Open editor → verify subtitles work (word-level timestamps present)
11. Click Disconnect → verify Connect button returns, AI buttons show tooltip

### Task V.2: Error Flow Test
**What**:
1. Try Transcribe without connecting → verify toast "Connect with Pollinations first"
2. Connect with expired/invalid key → verify 401 handling, auto-disconnect
3. Verify error banner shows actionable message for auth failures

### Task V.3: Dependency Cleanup Verification
**What**:
1. `grep -r "groq" app/` → verify zero results
2. `grep -r "GROQ" app/` → verify zero results
3. `grep -r "GROQ" .env.example` → verify zero results
4. `python -c "from app.services.transcription import transcribe_audio"` → verify import works
5. `python -c "from app.services.llm import analyze_transcript"` → verify import works

---

## Implementation Order (Critical Path)

```
Phase 0 (BLOCKING GATE)
  └─ Task 0.1 + 0.2: Verify Pollinations transcription schema
      │
      ├─ PASS → Continue to Phase 1
      └─ FAIL → Build normalization layer based on findings, then continue

Phase 1 (Backend — sequential)
  ├─ Task 1.1: Config settings
  ├─ Task 1.2: API key extraction utility
  ├─ Task 1.3: Transcribe endpoint update
  ├─ Task 1.4: Analyze endpoint update
  ├─ Task 1.5: Transcription service rewrite ← HIGHEST RISK
  ├─ Task 1.6: LLM service update
  ├─ Task 1.7: Config endpoint
  └─ Task 1.8: Error handling

Phase 2 (Frontend — can partially parallel with Phase 1)
  ├─ Task 2.1: Auth UI elements
  ├─ Task 2.2: Auth styles
  ├─ Task 2.3: Auth flow logic
  ├─ Task 2.4: API key injection
  └─ Task 2.5: 401/402 handling

Phase 3 (Cleanup — after Phase 1+2)
  ├─ Task 3.1: .env.example
  ├─ Task 3.2: requirements.txt
  ├─ Task 3.3: README.md
  └─ Task 3.4: Dockerfile verification

Final Verification Wave
  ├─ Task V.1: E2E flow
  ├─ Task V.2: Error flows
  └─ Task V.3: Dependency cleanup
```

## Commit Message
```
feat(byop): convert AI services to Bring Your Own Pollen model

- Replace Groq transcription with Pollinations API (whisper-large-v3)
- Add BYOP auth flow (connect button, redirect, localStorage key)
- Pass user API key from frontend to backend per-request
- Add 401/402 error handling for expired keys and insufficient balance
- Remove groq dependency, consolidate on OpenAI SDK
- Change default LLM model to free-tier (openai)
```
