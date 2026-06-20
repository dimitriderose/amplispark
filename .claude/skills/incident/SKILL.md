---
name: incident
description: Guided incident response runbook — characterise the problem, identify the cause via logs and recent deploys, remediate via rollback or hotfix, then verify resolution. Use when something is broken in production.
---
Run the Amplispark incident response runbook.

## Steps

### Step 1 — Characterise the incident
Ask the user:
- "What are users reporting? (e.g. 500 errors on a specific route, slow responses, feature not working)"
- "When did it start? (approximate time)"

Then run `/check-prod` to get the current health snapshot (active revision, instance count, recent errors).

Tell the user the health status and any ERROR logs found.

### Step 2 — Identify the cause via logs
Run `/tail-logs` with ERROR severity, mentioning the time window the user reported.

Ask the user: "Do the logs point to a clear cause?"
- **Yes** → Go to Step 4 (remediate)
- **No / unclear** → Go to Step 3

### Step 3 — Check recent deploys
List the last 5 Cloud Run revisions with deploy times:
```bash
set -a && source .env && set +a
gcloud run revisions list \
  --service=amplifi \
  --region=$GCP_REGION \
  --project=$GCP_PROJECT_ID \
  --limit=5 \
  --format="table(name,metadata.creationTimestamp,status.conditions[0].status)"
```

Ask the user: "Did any deploy happen around the time the incident started?"
- **Yes** → likely a bad deploy → offer rollback (Step 4a)
- **No** → the cause may be external (Gemini API, Firestore, GCS outage) — check GCP Status Dashboard at https://status.cloud.google.com and ask the user what they want to do

### Step 4 — Remediate

**Option 4a — Rollback (deploy-caused incident):**
Invoke `/rollback` to list revisions, confirm with user, shift traffic to the last known-good revision.

**Option 4b — Hotfix (known code bug):**
If the root cause is a clear, safe, small code fix:
- Implement the fix directly
- Run `ruff check` and `mypy` on changed files
- Run `pytest` to confirm no regressions
- Invoke `/commit` to run the full CI gate and commit
- Push to main: `git push origin main`
- Auto-deploy will trigger via GitHub Actions → Cloud Build
- Monitor the deploy: `gh run watch`

### Step 5 — Verify and close
Run `/check-prod` again after remediation.
Run `/tail-logs` with ERROR severity — confirm error count has dropped.

Ask the user: "Is the incident resolved? (yes/no)"

**If yes:**
Summarise the incident:
- What was reported
- Root cause identified
- Remediation taken (rollback revision / hotfix commit)
- Current status: GREEN

Suggest follow-up actions:
- If rollback: open a task to fix the root cause properly and redeploy
- If no alerting was in place: prioritise setting up uptime + error rate alerts
- If logs were hard to read: consider adding more structured context to the affected handler

**If no:**
Return to Step 2 and repeat with a different filter or deeper investigation.

## Rules
- Never skip the verify step — always confirm error rate dropped after remediation
- A rollback is always safer than a hotfix under pressure — default to rollback unless the fix is trivial and well-tested
- If the incident involves data loss or corruption, run `/db-backup` before any remediation
