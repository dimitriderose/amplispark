---
name: check-prod
description: Check the health of production right now — active revision, instance count, error rate, and recent logs. Use when you want a quick prod status snapshot or before/after a deploy.
---
Check the current health of the Amplispark production service.

## Steps

1. Load environment variables:
   ```bash
   set -a && source .env && set +a
   ```

2. Get active revision and traffic split:
   ```bash
   gcloud run services describe amplifi \
     --region=$GCP_REGION \
     --project=$GCP_PROJECT_ID \
     --format="table(status.traffic.revisionName,status.traffic.percent,status.traffic.latestRevision)"
   ```

3. Get instance count and resource limits for the active revision:
   ```bash
   gcloud run revisions describe $(gcloud run services describe amplifi \
     --region=$GCP_REGION --project=$GCP_PROJECT_ID \
     --format="value(status.latestReadyRevisionName)") \
     --region=$GCP_REGION \
     --project=$GCP_PROJECT_ID \
     --format="table(name,spec.containerConcurrency,spec.containers[0].resources.limits)"
   ```

4. Pull the last 30 ERROR and CRITICAL log entries from the past hour:
   ```bash
   gcloud logging read \
     "resource.type=cloud_run_revision AND resource.labels.service_name=amplifi AND severity>=ERROR" \
     --project=$GCP_PROJECT_ID \
     --limit=30 \
     --freshness=1h \
     --format="table(timestamp,severity,jsonPayload.message,jsonPayload.path,jsonPayload.user_uid)"
   ```

5. Get last deploy time (creation time of the latest revision):
   ```bash
   gcloud run revisions list \
     --service=amplifi \
     --region=$GCP_REGION \
     --project=$GCP_PROJECT_ID \
     --limit=1 \
     --format="table(name,metadata.creationTimestamp)"
   ```

6. Report a health summary:
   - **Revision:** name of the active revision
   - **Last deploy:** timestamp
   - **Errors (last 1h):** count of ERROR/CRITICAL entries found
   - **Status:** GREEN (0 errors), YELLOW (1-5 errors), RED (>5 errors or CRITICAL entries)
   - List any ERROR log messages found so the user can see them at a glance
   - Suggest `/tail-logs` for a live view or `/incident` if the status is RED
