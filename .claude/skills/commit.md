Run all CI checks locally and commit only if everything passes.

## Steps

1. Show the user what will be committed:
   ```bash
   git status
   git diff --stat HEAD
   ```

2. Ask the user for a commit message if they haven't provided one with the skill invocation.

3. Run backend tests (mirrors Cloud Build Step 0):
   ```powershell
   .\backend\.venv\Scripts\python -m pytest backend/tests/ -v --tb=short
   ```
   If any test fails: STOP. Show failures. Do not commit. Tell the user to fix failures first.

4. Run frontend TypeScript build check (mirrors the Docker build):
   ```powershell
   cd frontend; npm run build
   ```
   If the build fails: STOP. Show errors. Do not commit.

5. Run frontend linter:
   ```powershell
   cd frontend; npm run lint
   ```
   If lint errors exist, attempt auto-fix:
   ```powershell
   cd frontend; npm run lint -- --fix
   ```
   Re-run lint. If errors remain: STOP and show them. Do not commit.

6. Check the latest GitHub Actions CI status on the current branch:
   ```bash
   gh run list --limit 3 --branch $(git rev-parse --abbrev-ref HEAD)
   ```
   If the most recent run shows `failure` or `cancelled`, warn the user before proceeding.
   If it shows `in_progress`, tell the user CI is still running — they can wait or proceed anyway.

7. Ensure git user is set correctly:
   ```bash
   git config user.name "dimitriderose"
   ```

8. Stage changed files:
   ```bash
   git add -A
   ```
   Verify no secrets were staged:
   ```bash
   git diff --cached --name-only
   ```
   If `.env`, `credentials.json`, `service-account*.json`, or any key file appears: unstage it with
   `git restore --staged <file>` and warn the user. Never commit secrets.

9. Commit:
   ```bash
   git commit -m "<commit message>

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
   ```

10. Report: all CI results, files committed, commit hash.
    Remind the user that pushing to `main` will trigger automatic deployment via GitHub Actions.
    If on a feature branch, remind them to open a PR.

## CI gate rules
- Backend tests must be 100% green — no failures, no skips
- Frontend build must succeed with zero TypeScript errors
- Linter must be clean
- No secrets staged
- All checks must pass before the commit is created
