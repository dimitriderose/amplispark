---
name: deploy
description: Deploy Amplispark to production on Google Cloud Run. Use when the user wants to deploy, ship, or push to production.
---
Deploy Amplispark to production on Google Cloud Run.

WARNING: This updates the live production app and cannot be automatically undone.

## Steps

1. Ask the user to confirm:
   "This will deploy Amplispark to PRODUCTION (Google Cloud Run). The live app will be updated. Type 'yes' to continue."
   If the user says anything other than "yes" or "y", abort: "Deploy cancelled."

2. Check gcloud is authenticated:
   ```bash
   gcloud auth list --filter=status:ACTIVE --format="value(account)"
   ```
   If output is empty, tell the user: "gcloud is not authenticated. Run `gcloud auth login` in a terminal first." and stop.

3. Check .env exists at the project root:
   ```powershell
   Test-Path "C:\Users\dimit\Documents\GitHub\amplispark\.env"
   ```
   If False, tell the user: ".env file missing at project root. Copy .env.example and fill in values." and stop.

4. Run the deploy script and stream output:
   ```bash
   bash C:/Users/dimit/Documents/GitHub/amplispark/scripts/deploy.sh
   ```

5. On success (exit code 0): report the live Cloud Run URL printed by the script.
   On failure: show the error output and direct the user to https://console.cloud.google.com/cloud-build/builds
