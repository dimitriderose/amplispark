---
name: tail-logs
description: Pull recent production logs filtered by severity or a search term. Use when you want to see what's happening in prod right now or investigate a specific error.
---
Pull recent Amplispark production logs with optional severity and text filters.

## Steps

1. Load environment variables:
   ```bash
   set -a && source .env && set +a
   ```

2. Ask the user:
   - "Severity filter? (ERROR / WARNING / INFO / DEBUG — default: ERROR)"
   - "Text filter? (e.g. a route like /api/posts, a brand_id, user_uid, or error keyword — leave blank for none)"
   
   Wait for their answers.

3. Build the log filter:
   - Base: `resource.type=cloud_run_revision AND resource.labels.service_name=amplifi AND severity>={SEVERITY}`
   - If text filter provided, append: `AND jsonPayload.message=~"{TEXT}"`

4. Pull the last 100 matching log entries from the past 2 hours:
   ```bash
   gcloud logging read \
     "{FILTER}" \
     --project=$GCP_PROJECT_ID \
     --limit=100 \
     --freshness=2h \
     --format="table(timestamp,severity,jsonPayload.message,jsonPayload.path,jsonPayload.status_code,jsonPayload.user_uid,jsonPayload.duration_ms)"
   ```

5. Format and present the results:
   - Group by severity (CRITICAL/ERROR first, then WARNING, then INFO)
   - For each entry show: `[timestamp] [SEVERITY] path=... status=... uid=... duration=...ms — message`
   - Highlight any CRITICAL entries prominently

6. Summarise:
   - Total entries returned, severity breakdown
   - Most frequent error messages (if >1 occurrence)
   - Tell the user to re-run `/tail-logs` for a fresh pull (Cloud Logging CLI doesn't stream in real-time)
   - If errors are found, suggest `/incident` for a guided response
