import logging as _logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
if not os.environ.get("GEMINI_MODEL"):
    _logging.getLogger(__name__).warning("GEMINI_MODEL not set, using default: %s", GEMINI_MODEL)
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "amplifi-hackathon")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", f"{GCP_PROJECT_ID}-amplifi-assets")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

# Server-side OAuth redirect flow (future). Currently the frontend collects user OAuth
# tokens directly and passes them to the /connect-social endpoint.
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")

# Notion OAuth (public integration)
NOTION_CLIENT_ID = os.environ.get("NOTION_CLIENT_ID", "")
NOTION_CLIENT_SECRET = os.environ.get("NOTION_CLIENT_SECRET", "")
NOTION_REDIRECT_URI = os.environ.get("NOTION_REDIRECT_URI", "")
if not NOTION_REDIRECT_URI:
    _logging.getLogger(__name__).warning(
        "NOTION_REDIRECT_URI is not set. Notion OAuth integration will not work until this is configured."
    )

BETA_MAX_BRANDS = 1
BETA_MAX_QUICK_POSTS_PER_MONTH = 8
BETA_MAX_CALENDARS_PER_MONTH = 4
BETA_DURATION_DAYS = 30

IMAGE_COST_PER_UNIT = 0.039  # ~$0.039 per generated image
VIDEO_COST_FAST = 1.20  # $1.20 per 8-sec Veo Fast clip
VIDEO_COST_STD = 3.20  # $3.20 per 8-sec Veo Standard clip
TOTAL_BUDGET = 100.0
IMAGE_BUDGET = 70.0
VIDEO_BUDGET = 30.0

_logger = _logging.getLogger(__name__)
if not GOOGLE_API_KEY:
    _logger.error("GOOGLE_API_KEY is not set — AI features will not work")
