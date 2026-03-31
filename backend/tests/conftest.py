"""Shared test fixtures for Amplispark backend tests."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
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
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
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
        "created_at": datetime.now(timezone.utc).isoformat(),
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
