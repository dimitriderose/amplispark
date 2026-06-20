Run a brutal multi-agent code review and fix all bugs found.

## Steps

1. Get the full diff of all changes:
   ```bash
   git diff HEAD
   git diff --cached
   ```

2. Identify which domains have changes. Spawn a reviewer for each domain that has changed files.
   Every reviewer must FIX bugs directly in the file — do not just report them.

   ### Backend Reviewer (BE)
   Review all changed Python files in `backend/` EXCEPT `backend/agents/`:
   - Unhandled exceptions that should surface as HTTP errors
   - Missing auth checks or brand ownership verification
   - N+1 Firestore query patterns
   - Race conditions in concurrent writes (use transactions where needed)
   - Incorrect HTTP status codes (400 bad input, 401 unauth, 403 forbidden, 404 not found, 500 unexpected)
   - Missing input validation on user-supplied data
   - Broken soft-delete logic (posts must use `status: "deleted"` + `deleted_at`, not hard delete)
   - Blocking calls inside async functions

   ### Frontend Reviewer (FE)
   Review all changed TypeScript/TSX files in `frontend/`:
   - Missing loading and error states on any async operation
   - Unhandled promise rejections
   - Memory leaks — missing cleanup in `useEffect` (event listeners, subscriptions, timers)
   - XSS risks via `dangerouslySetInnerHTML`
   - Missing `key` props in lists
   - Careless use of `any` or `unknown` TypeScript types
   - API calls that don't handle both success and error responses

   ### Context Reviewer (Prompts/Agents)
   Review all changed files in `backend/agents/`:
   - Prompt injection — user input concatenated into prompts without sanitisation
   - Missing output format validation and fallback when LLM returns malformed JSON
   - Temperature too high for deterministic/analytical tasks (should be ≤0.15)
   - Grounding tool calls that may fail silently
   - Missing retry logic for flaky LLM calls

   ### DBA Reviewer
   Review changed files in `backend/models/` and `backend/services/firestore_client.py`:
   - Missing field defaults that would break reads on existing documents
   - Collection scans instead of indexed field queries
   - Multi-document writes missing transactional wrappers
   - Sensitive data stored without encryption

   ### Network Engineer
   Review changes in `backend/routers/voice.py`, `backend/middleware.py`, `backend/server.py`, and frontend API code:
   - WebSocket connections not properly closed on error or disconnect
   - Missing reconnect logic on the frontend for WebSocket/SSE streams
   - CORS origins too broad (wildcard in production) or too restrictive (blocking valid origins)
   - SSE streams missing keepalive heartbeats (causes proxy timeout after 60s)
   - Missing timeout handling on long-running requests
   - Vite proxy config mismatches vs production routing

   ### Audio Engineer
   Review changes in `backend/routers/voice.py`, `backend/agents/voice_coach.py`, and frontend audio code:
   - Audio stream not properly closed when session ends
   - Missing error handling when Gemini Live connection drops mid-session
   - Audio buffer overflow risks
   - Incorrect sample rate or encoding format for Gemini Live
   - Frontend `AudioContext` not suspended/closed on component unmount
   - `AudioContext` created without user gesture (violates browser autoplay policy)

   ### GCP DevOps Engineer
   Review changes in `cloudbuild.yaml`, `backend/Dockerfile`, `scripts/deploy.sh`, `terraform/`:
   - Memory/CPU limits insufficient for new workloads (current: 2Gi / 2 CPU)
   - Missing health check endpoint if new routes are added
   - Secrets passed as plain env vars that should use Secret Manager
   - Docker layers not optimised (pip install before copying source code)
   - Cloud Run min instances 0 causing cold-start latency for latency-sensitive voice sessions
   - IAM permissions broader than necessary

   ### Software Architect
   Review ALL changed files — read `docs/TDD.md` first for architectural context:
   - **Logging:** Every request handler logs at entry and exit. Errors include full context (brand_id, user_id, operation). Format is consistent with existing `middleware.py` patterns.
   - **Error handling:** All external calls (Gemini API, Firestore, GCS, Resend) wrapped in try/except. No bare `except Exception` that swallows errors silently.
   - **Security:** No user-supplied data in prompts without sanitisation. Brand ownership verified via middleware. No secrets in logs or API responses.
   - **Architecture fit:** New code follows existing patterns — `FastAPI Depends()` for auth, Pydantic v2 models, async throughout, service layer for business logic, agents only for AI work. No new patterns introduced without justification in `docs/TDD.md`.
   - **Missing pieces:** Any logging gaps, unhandled edge cases, or security holes the other reviewers missed.

3. After all reviewers complete their fixes, run the full test suite:
   ```powershell
   .\backend\.venv\Scripts\python -m pytest backend/tests/ -v --tb=short
   ```
   If any tests fail after fixes, diagnose and fix before reporting done.

4. Report to the user: each reviewer's findings, fixes applied, and final test result.

## Review standard
- A finding must be a real bug, security issue, or correctness problem — not a style preference
- Every finding must be fixed in-place, not just flagged
- "Looks good" is only acceptable when the reviewer has checked every item on their checklist
