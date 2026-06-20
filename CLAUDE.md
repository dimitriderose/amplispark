# Amplispark — Claude Code Context

## Project Layout

Monorepo with two servers and shared GCP infrastructure:

```
frontend/        React 19 + TypeScript + Vite 7     → http://localhost:5173
backend/         FastAPI (Python 3.12) + uvicorn     → http://localhost:8080
backend/agents/  14 AI agents (Gemini API)           — prompts are inline f-strings
backend/tests/   pytest test suite (629 lines, 7 files)
docs/            PRD.md, TDD.md, feature-specs/
scripts/         deploy.sh — one-command Cloud Run deploy
terraform/       GCP infrastructure (Cloud Run, Firestore, GCS, Artifact Registry)
.github/
  workflows/
    ci.yml       CI — runs on all branches except main (tests + build + lint)
    deploy.yml   CI/CD — runs on push to main (tests + build + deploy to Cloud Run)
```

## Local Development (Windows)

**Backend** — run from project root, NOT from inside `backend/`:
```powershell
.\backend\.venv\Scripts\uvicorn backend.server:app --host 0.0.0.0 --port 8080 --reload
```
Module path is `backend.server:app`. Running from inside `backend/` with `server:app` fails because the server imports `from backend.config import ...`.

**Frontend:**
```powershell
cd frontend
npm run dev    # http://localhost:5173 — /api/* proxied to :8080
```

**Shortcuts:** `/run-local`, `/run-backend`, `/run-frontend`

## Key URLs (local)
- Frontend: http://localhost:5173
- Backend API: http://localhost:8080
- Swagger docs: http://localhost:8080/docs

## Architecture Conventions

- **Auth:** Firebase Google Sign-In (client) + `firebase-admin` token verification (server). Every protected route uses `Depends(verify_token)`. Brand ownership is enforced via `Depends(verify_brand_ownership)`.
- **Async throughout:** All FastAPI handlers and Firestore calls are async. No blocking I/O in async functions.
- **Pydantic v2 models** in `backend/models/` for all request/response schemas and Firestore data.
- **Service layer** in `backend/services/` for business logic. Agents in `backend/agents/` for AI-only work.
- **Soft deletes:** Posts are never hard-deleted. Use `status: "deleted"` + `deleted_at` timestamp. `list_posts` filters these out.
- **Firestore schema** documented in `docs/TDD.md`. Collections: `brands/`, `brands/{id}/content_plans/`, `brands/{id}/posts/`.
- **Prompts** are inline f-strings in agent files — no separate template files. Structured with clear sections and JSON fence markers for output.

## Test Command
```powershell
.\backend\.venv\Scripts\python -m pytest backend/tests/ -v --tb=short
```
Run from project root. `asyncio_mode = auto` in `pytest.ini`. Mock Firebase and Firestore via fixtures in `conftest.py`.

## Production Deploy

Every push to `main` auto-deploys via GitHub Actions (`.github/workflows/deploy.yml`):
tests → frontend build → `scripts/deploy.sh` → Cloud Build → Cloud Run.

Manual deploy: `/deploy` (requires gcloud authenticated + `.env` at project root).

Live URL: https://amplifi-seimyaykpa-uc.a.run.app

## Available Skills

| Skill | Purpose |
|---|---|
| `/run-local` | Start both servers in new terminal windows |
| `/run-backend` | Start backend only |
| `/run-frontend` | Start frontend only |
| `/plan-feature` | PM + Architect planning session → feature spec in `docs/feature-specs/` |
| `/code-feature` | Role-specific agents implement the spec (BE, FE, Context, Network, Audio, DevOps, DBA) |
| `/review-code` | Brutal multi-agent review (8 reviewers) — finds and fixes all bugs |
| `/qa-plan` | QA Lead creates test plan → `docs/feature-specs/{name}-test-plan.md` |
| `/qa-test` | QA Testers implement test plan as pytest tests |
| `/commit` | Local CI gate (tests + build + lint) then commit |
| `/deploy` | Manual deploy to production with confirmation gate |

## Git
- Username: `dimitriderose`
- Feature branches push to non-main → CI runs automatically
- Merge to main → auto-deploy runs automatically
- Never commit `.env` or any credentials file
