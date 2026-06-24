---
name: commit
description: Run all CI checks locally (ruff, mypy, pytest, tsc, eslint, vitest, build) and commit only if everything passes. Use when the user wants to commit changes, save work, or run CI before committing.
---
Run all CI checks locally and commit only if everything passes.

## Steps

1. Show the user what will be committed:
   ```bash
   git status
   git diff --name-only
   ```

2. Ask the user for a commit message if they haven't provided one with the skill invocation.

3. Run backend CI checks (fail-fast order):
   ```bash
   ruff check backend/
   ruff format --check backend/
   mypy backend/ --ignore-missing-imports
   ```
   Then run tests:
   ```bash
   backend/.venv/Scripts/python -m pytest backend/tests/ -v --tb=short
   ```
   If any check fails: STOP. Show the failure. Do not commit. Fix it first.

4. Run frontend CI checks (fail-fast order):
   ```bash
   cd frontend && npm run typecheck
   cd frontend && npm run lint
   cd frontend && npm run test -- --coverage
   cd frontend && npm run build
   ```
   If any check fails: STOP. Show the error. Do not commit.

5. Check the latest GitHub Actions CI status:
   ```bash
   gh run list --limit 3 --branch $(git rev-parse --abbrev-ref HEAD)
   ```
   If the most recent run shows `failure`, warn the user before proceeding.

6. Ensure git user is set correctly:
   ```bash
   git config user.name "dimitriderose"
   ```

7. Stage ALL changed files:
   ```bash
   git diff --name-only
   git diff --name-only --cached
   ```
   Review the full list. If `.env`, `credentials.json`, `service-account*.json`, or any key file appears: do NOT stage it and warn the user.
   Stage everything else:
   ```bash
   git add <files>
   ```

8. Commit:
   ```bash
   git commit -m "<commit message>

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
   ```

9. Report: all CI results, files committed, commit hash.
   Remind the user that pushing to `main` triggers automatic deployment.
   If on a feature branch, remind them to open a PR.

## CI gate rules
- All 8 checks must be green before committing
- No secrets staged — ever
- Stage ALL changed files, not just the ones you were focused on
