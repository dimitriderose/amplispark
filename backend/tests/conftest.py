"""Shared test fixtures for Amplispark backend tests."""

from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Mock Firebase Admin before any backend module imports it
# ---------------------------------------------------------------------------
_mock_firebase_app = MagicMock()

# Patch firebase_admin at module level so middleware.py doesn't crash on import
patch_firebase_admin = patch.dict(
    "sys.modules",
    {
        "firebase_admin": MagicMock(_apps={"[DEFAULT]": _mock_firebase_app}),
        "firebase_admin.auth": MagicMock(),
    },
)
patch_firebase_admin.start()

# Now safe to import backend modules
from backend.server import app  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_UID = "test-user-uid-123"
TEST_BRAND_ID = "test-brand-id-456"


@pytest.fixture
def test_uid():
    return TEST_UID


@pytest.fixture
def test_brand_id():
    return TEST_BRAND_ID


@pytest.fixture
def sample_brand():
    return {
        "brand_id": TEST_BRAND_ID,
        "owner_uid": TEST_UID,
        "business_name": "Test Brand",
        "description": "A test brand",
        "analysis_status": "complete",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


@pytest.fixture
def sample_post():
    return {
        "post_id": "test-post-id-789",
        "brand_id": TEST_BRAND_ID,
        "plan_id": "test-plan-id",
        "platform": "instagram",
        "status": "complete",
        "caption": "Test caption for this post",
        "hashtags": ["#test", "#amplispark"],
        "image_url": "https://example.com/image.png",
        "created_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def mock_verify_token():
    """Mock Firebase token verification to return test UID."""
    with patch("backend.middleware.firebase_auth") as mock_auth:
        mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
        mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
        mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})
        yield mock_auth


@pytest.fixture
def mock_firestore(sample_brand):
    """Mock all firestore_client operations."""
    with patch("backend.services.firestore_client") as mock_fc:
        mock_fc.get_brand = AsyncMock(return_value=sample_brand)
        mock_fc.create_brand = AsyncMock(return_value=TEST_BRAND_ID)
        mock_fc.update_brand = AsyncMock()
        mock_fc.list_brands_by_owner = AsyncMock(return_value=[sample_brand])
        mock_fc.get_plan = AsyncMock(return_value=None)
        mock_fc.list_posts = AsyncMock(return_value=[])
        mock_fc.save_post = AsyncMock(return_value="new-post-id")
        mock_fc.update_post = AsyncMock()
        mock_fc.delete_post = AsyncMock()
        yield mock_fc


@pytest.fixture
def client(mock_verify_token, mock_firestore):
    """FastAPI TestClient with mocked auth and Firestore."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Headers with a valid Bearer token."""
    return {"Authorization": "Bearer fake-valid-token"}


@pytest.fixture
def uid_headers():
    """Headers with X-User-UID fallback."""
    return {"X-User-UID": TEST_UID}


@pytest.fixture
def sample_plan():
    return {
        "plan_id": "test-plan-id",
        "brand_id": TEST_BRAND_ID,
        "num_days": 7,
        "status": "complete",
        "days": [
            {
                "day_index": i,
                "platform": "instagram",
                "theme": f"Theme {i}",
                "brief": f"Brief {i}",
                "content_type": "photo",
                "posting_time": "9:00 AM",
            }
            for i in range(7)
        ],
        "trend_summary": {"highlights": ["trend1"]},
        "created_at": datetime.now(UTC),
    }


@pytest.fixture
def mock_gcs_bucket():
    with patch("backend.services.storage_client.get_bucket") as mock_get_bucket:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/image.png"
        mock_blob.content_type = "image/png"
        mock_blob.size = 1024
        mock_bucket.blob.return_value = mock_blob
        mock_get_bucket.return_value = mock_bucket
        yield mock_bucket, mock_blob


@pytest.fixture
def mock_httpx():
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        yield mock_client


@pytest.fixture
def mock_pil_image():
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_fernet():
    with patch("backend.routers.integrations._fernet") as mock_f:
        mock_f.encrypt.return_value = b"encrypted-token"
        mock_f.decrypt.return_value = b"real-token"
        yield mock_f


@pytest.fixture
def extended_mock_firestore(mock_firestore, sample_plan):
    mock_firestore.get_plan = AsyncMock(return_value=sample_plan)
    mock_firestore.list_plans = AsyncMock(return_value=[sample_plan])
    mock_firestore.create_plan = AsyncMock(return_value="new-plan-id")
    mock_firestore.update_plan = AsyncMock()
    mock_firestore.update_plan_day = AsyncMock()
    mock_firestore.get_post = AsyncMock(return_value=None)
    mock_firestore.create_video_job = AsyncMock(return_value="job-id-1")
    mock_firestore.get_video_job = AsyncMock(
        return_value={"job_id": "job-id-1", "status": "queued"}
    )
    mock_firestore.update_video_job = AsyncMock()
    mock_firestore.create_repurpose_job = AsyncMock(return_value="repurpose-job-id")
    mock_firestore.get_repurpose_job = AsyncMock(
        return_value={"job_id": "repurpose-job-id", "status": "queued"}
    )
    mock_firestore.save_review = AsyncMock()
    mock_firestore.get_review = AsyncMock(return_value=None)
    return mock_firestore
