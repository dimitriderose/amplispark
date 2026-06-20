---
name: code-feature
description: Implement a feature using role-specific engineering agents (BE, FE, Context, Network, Audio, DevOps, DBA). Use when the user wants to implement or build a feature from a spec.
---
Implement the feature using role-specific engineering agents.

## Steps

1. Read the feature spec from `docs/feature-specs/`. Ask the user which spec to implement if multiple exist.
   Also read the relevant existing code files identified in the spec.

2. Spawn role-specific agents based on what the spec requires. Only spawn agents for domains that have changes:

   ### Backend Engineer
   If the spec has backend changes:
   - Implement FastAPI routes in `backend/routers/`
   - Update Pydantic models in `backend/models/`
   - Implement service logic in `backend/services/`
   - Follow existing patterns: FastAPI `Depends()` for auth, Pydantic v2 models, async throughout, soft deletes for user data
   - Run: `.\backend\.venv\Scripts\python -m pytest backend/tests/ -v --tb=short` from project root to verify no regressions

   ### Frontend Engineer
   If the spec has frontend changes:
   - Implement React components in `frontend/src/`
   - Use React 19 patterns already in the codebase
   - API calls go through `/api/*` (proxied by Vite to backend:8080)
   - Type all props and state with TypeScript
   - Run `cd frontend && npm run build` to verify no TypeScript errors

   ### Context Engineer
   If the spec has prompt or AI agent changes:
   - Edit the relevant agent file in `backend/agents/`
   - Prompts are inline f-strings — keep them structured with clear sections
   - Temperature: 0.15 for analytical tasks, 0.2–0.7 for creative
   - Always include output format instructions and JSON fence markers
   - Verify fallback handling when LLM returns malformed JSON

   ### Network Engineer
   If the spec has changes to WebSocket/SSE handling, CORS, proxy config, or API routing:
   - Implement connection lifecycle (open, keepalive, close/cleanup on error)
   - Configure CORS in `backend/server.py` correctly for new endpoints
   - Ensure Vite proxy config in `frontend/vite.config.ts` matches any new API paths
   - Add reconnect logic on the frontend for WebSocket/SSE streams

   ### Audio Engineer
   If the spec has changes to voice/audio features:
   - Implement audio stream handling in `backend/routers/voice.py` and `backend/agents/voice_coach.py`
   - Handle Gemini Live session lifecycle: connect, stream, graceful disconnect, error recovery
   - On the frontend: manage AudioContext lifecycle (create on user gesture, suspend/close on unmount)
   - Validate sample rate and encoding match Gemini Live requirements

   ### GCP DevOps Engineer
   If the spec has infrastructure, deployment, or Cloud Run changes:
   - Update `cloudbuild.yaml`, `backend/Dockerfile`, or `scripts/deploy.sh` as needed
   - Validate Cloud Run resource limits (memory/CPU) are appropriate for new workloads
   - Ensure any new secrets are added to the deploy substitutions and `.env.example`, not hardcoded

   ### DBA
   If the spec has Firestore schema changes:
   - Update Pydantic models in `backend/models/` to reflect new fields
   - Update `backend/services/firestore_client.py` for any new collection operations
   - Document schema changes in `docs/TDD.md` under the Firestore section
   - Note optional fields with sensible defaults in the read path (Firestore is schemaless — existing docs won't have new fields)

3. Code quality rules (enforce for ALL agents):
   - No comments that describe WHAT the code does — only WHY when it is non-obvious
   - No multi-line docstrings or comment blocks
   - No dead code, unused imports, or leftover TODOs
   - No speculative abstractions — only abstract when the same logic appears 3+ times
   - No error handling for impossible cases
   - Type annotations on all function signatures (Python) and all props/state (TypeScript)

4. After all agents complete, run a final check from the project root:
   ```powershell
   .\backend\.venv\Scripts\python -m pytest backend/tests/ -v --tb=short
   ```
   Report results to the user. Fix any failures before reporting done.
