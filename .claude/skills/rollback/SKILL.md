---
name: rollback
description: Roll back Cloud Run to a previous revision when something breaks in prod. Use when a bad deploy causes errors and you need to restore a known-good revision immediately.
---
Roll back the Amplispark Cloud Run service to a previous revision.

## Steps

1. Load environment variables to get region and project:
   ```bash
   set -a && source .env && set +a
   ```

2. List the 10 most recent revisions with traffic and deploy time:
   ```bash
   gcloud run revisions list \
     --service=amplifi \
     --region=$GCP_REGION \
     --project=$GCP_PROJECT_ID \
     --limit=10 \
     --format="table(name,status.observedGeneration,metadata.creationTimestamp,status.traffic.percent)"
   ```

3. Ask the user: "Which revision do you want to roll back to? (paste the revision name, e.g. amplifi-00012-abc)"
   Wait for their answer.

4. Shift 100% of traffic to the selected revision:
   ```bash
   gcloud run services update-traffic amplifi \
     --region=$GCP_REGION \
     --project=$GCP_PROJECT_ID \
     --to-revisions={REVISION}=100
   ```

5. Confirm the traffic split now shows 100% on the selected revision:
   ```bash
   gcloud run services describe amplifi \
     --region=$GCP_REGION \
     --project=$GCP_PROJECT_ID \
     --format="value(status.traffic)"
   ```

6. Tell the user:
   - Rollback complete — traffic is now 100% on `{REVISION}`
   - Run `/tail-logs` with ERROR severity to confirm the error rate has dropped
   - The bad revision is still deployed but receiving 0% traffic — it can be deleted later
   - When the root cause is fixed, push a new commit to main to deploy a clean revision
