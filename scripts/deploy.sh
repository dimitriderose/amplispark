#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Amplispark — One-command deploy to Cloud Run
#
# Reads config from .env (gitignored), submits a Cloud Build job that builds
# the Docker image, pushes to Artifact Registry, and deploys to Cloud Run
# with all required environment variables.
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. Copy .env.example → .env and fill in your Firebase config
#   3. Run `terraform apply` first to provision GCP resources
#
# Usage:
#   ./scripts/deploy.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env from project root
ENV_FILE="$PROJECT_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env not found at $ENV_FILE"
  echo "Copy .env.example to .env and fill in your Firebase config."
  exit 1
fi

# Source .env (only VITE_FIREBASE_* vars)
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Validate required vars
REQUIRED_VARS=(
  VITE_FIREBASE_API_KEY
  VITE_FIREBASE_AUTH_DOMAIN
  VITE_FIREBASE_PROJECT_ID
  VITE_FIREBASE_STORAGE_BUCKET
  VITE_FIREBASE_MESSAGING_SENDER_ID
  VITE_FIREBASE_APP_ID
  GCP_PROJECT_ID
  GOOGLE_API_KEY
)

for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: $var is not set in .env"
    exit 1
  fi
done

REGION="${GCP_REGION:-us-central1}"

echo "Deploying Amplispark to Cloud Run..."
echo "  Project:  $GCP_PROJECT_ID"
echo "  Region:   $REGION"
echo ""

cd "$PROJECT_ROOT"

gcloud builds submit \
  --project="$GCP_PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions="\
_VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY,\
_VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN,\
_VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID,\
_VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET,\
_VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID,\
_VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID,\
_GOOGLE_API_KEY=$GOOGLE_API_KEY,\
_CORS_ORIGINS=${CORS_ORIGINS:-*},\
_RESEND_API_KEY=${RESEND_API_KEY:-},\
_NOTION_CLIENT_ID=${NOTION_CLIENT_ID:-},\
_NOTION_CLIENT_SECRET=${NOTION_CLIENT_SECRET:-},\
_NOTION_REDIRECT_URI=${NOTION_REDIRECT_URI:-},\
_TOKEN_ENCRYPT_KEY=${TOKEN_ENCRYPT_KEY:-},\
_REGION=$REGION"

# Get the live URL from the deployed service
LIVE_URL=$(gcloud run services describe amplifi --region="$REGION" --project="$GCP_PROJECT_ID" --format='value(status.url)' 2>/dev/null || echo "unknown")

echo ""
echo "Deploy complete! Your app is live at:"
echo "  $LIVE_URL"
