---
name: db-backup
description: Export all Firestore data to GCS with a timestamped path. Use before risky migrations, on a regular schedule, or any time you want a point-in-time snapshot of the database.
---
Export the Amplispark Firestore database to Google Cloud Storage.

## Steps

1. Load environment variables:
   ```bash
   set -a && source .env && set +a
   ```

2. Confirm with the user before running (exports can take several minutes for large databases):
   "About to export Firestore to gs://$GCS_BUCKET_NAME/backups/firestore-{TIMESTAMP}. Proceed? (yes/no)"
   Wait for confirmation.

3. Trigger the Firestore export:
   ```bash
   TIMESTAMP=$(date +%Y%m%d-%H%M%S)
   gcloud firestore export \
     gs://$GCS_BUCKET_NAME/backups/firestore-$TIMESTAMP \
     --project=$GCP_PROJECT_ID \
     --async
   ```
   The `--async` flag returns immediately with an operation name.

4. Wait for the operation to complete by polling:
   ```bash
   gcloud firestore operations list --project=$GCP_PROJECT_ID
   ```
   Check every 30 seconds until the export operation shows `DONE`.

5. Confirm the backup exists in GCS:
   ```bash
   gcloud storage ls gs://$GCS_BUCKET_NAME/backups/firestore-$TIMESTAMP/
   ```

6. Report:
   - Backup path: `gs://$GCS_BUCKET_NAME/backups/firestore-$TIMESTAMP/`
   - Size of the exported data (from the GCS listing)
   - Time taken
   - Remind the user: to restore from this backup, use `gcloud firestore import gs://$GCS_BUCKET_NAME/backups/firestore-$TIMESTAMP/`
   - Note: backups share the same GCS bucket as media uploads — consider a GCS lifecycle rule if backups accumulate
