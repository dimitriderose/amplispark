---
name: sdlc
description: Run the full Amplispark software development lifecycle in sequence: plan-feature → code-feature → review-code → qa-plan → qa-test → run-local (if not running) → commit → deploy. Use when the user wants to build a feature end-to-end or go through the full SDLC workflow.
---
Guide the user through the full Amplispark software development lifecycle, one phase at a time.

Run each skill in sequence, pausing for user confirmation between phases.

## Phases

### Phase 1 — Plan
Invoke `/plan-feature`: facilitate a PM + Software Architect planning session and produce a feature spec in `docs/feature-specs/`.

Tell the user: "Phase 1 complete — feature spec written. Ready to start coding? (yes/no)"
Wait for confirmation before continuing.

### Phase 2 — Code
Invoke `/code-feature`: spawn role-specific agents (BE, FE, Context, Network, Audio, DevOps, DBA) to implement the spec.

Tell the user: "Phase 2 complete — implementation done. Ready for code review? (yes/no)"
Wait for confirmation before continuing.

### Phase 3 — Review
Invoke `/review-code`: run brutal multi-agent code review across all domains, fix every bug in-place.

Tell the user: "Phase 3 complete — all bugs fixed. Ready to create the QA test plan? (yes/no)"
Wait for confirmation before continuing.

### Phase 4 — QA Plan
Invoke `/qa-plan`: QA Lead reads the spec and writes a structured test plan to `docs/feature-specs/{feature-name}-test-plan.md`.

Tell the user: "Phase 4 complete — test plan written. Ready to implement the tests? (yes/no)"
Wait for confirmation before continuing.

### Phase 5 — QA Tests
Invoke `/qa-test`: QA Testers implement the test plan as pytest tests, run the suite, fix failures.

Tell the user: "Phase 5 complete — tests passing. Ready to verify the feature locally? (yes/no)"
Wait for confirmation before continuing.

### Phase 6 — Run Local (if not already running)
Check whether the servers are already up:
```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
```
If either port is not listening, invoke `/run-local` to start both servers.

Tell the user:
- Backend: http://localhost:8080
- Frontend: http://localhost:5173
- "Please verify the feature works as expected in the browser, then confirm to continue."

Wait for the user to confirm the feature looks good before continuing.

### Phase 7 — Commit
Invoke `/commit`: run all 8 CI checks locally (ruff, mypy, pytest, tsc, eslint, vitest, build), then commit if all pass.

Tell the user: "Phase 7 complete — committed. Ready to deploy to production? (yes/no)"
Wait for confirmation before continuing.

### Phase 8 — Deploy
Invoke `/deploy`: confirm with the user, then deploy to Google Cloud Run via `scripts/deploy.sh`.

Tell the user: "Phase 8 complete — deployed to production. Full SDLC cycle done."

## Rules
- Never skip a phase without explicit user confirmation
- If any phase fails (tests fail, build fails, review finds unfixed bugs), stop and tell the user what needs to be resolved before continuing
- The user can stop at any phase by saying "stop" or "done for now"
- If the user wants to re-run a single phase, they can invoke it directly (e.g. `/review-code`)
