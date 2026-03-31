"""Tests for Firebase auth middleware and brand ownership verification."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from backend.tests.conftest import TEST_UID, TEST_BRAND_ID


# ---------------------------------------------------------------------------
# get_authenticated_uid tests
# ---------------------------------------------------------------------------


class TestGetAuthenticatedUid:
    """Tests for get_authenticated_uid()."""

    @pytest.mark.asyncio
    async def test_valid_bearer_token_returns_uid(self, mock_verify_token):
        from backend.middleware import get_authenticated_uid

        request = MagicMock()
        request.headers = {"Authorization": "Bearer valid-token"}
        request.url.path = "/api/brands"

        uid = await get_authenticated_uid(request)
        assert uid == TEST_UID
        mock_verify_token.verify_id_token.assert_called_once_with("valid-token")

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self, mock_verify_token):
        from backend.middleware import get_authenticated_uid

        mock_verify_token.verify_id_token.side_effect = mock_verify_token.ExpiredIdTokenError()

        request = MagicMock()
        request.headers = {"Authorization": "Bearer expired-token"}
        request.url.path = "/api/brands"

        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_uid(request)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, mock_verify_token):
        from backend.middleware import get_authenticated_uid

        mock_verify_token.verify_id_token.side_effect = mock_verify_token.InvalidIdTokenError()

        request = MagicMock()
        request.headers = {"Authorization": "Bearer bad-token"}
        request.url.path = "/api/brands"

        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_uid(request)
        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_none(self, mock_verify_token):
        from backend.middleware import get_authenticated_uid

        request = MagicMock()
        request.headers = {}
        request.url.path = "/api/brands"

        uid = await get_authenticated_uid(request)
        assert uid is None

    @pytest.mark.asyncio
    async def test_x_user_uid_fallback(self, mock_verify_token):
        from backend.middleware import get_authenticated_uid

        request = MagicMock()
        request.headers = {"X-User-UID": "fallback-uid"}
        request.url.path = "/api/brands"

        uid = await get_authenticated_uid(request)
        assert uid == "fallback-uid"

    @pytest.mark.asyncio
    async def test_generic_exception_raises_401(self, mock_verify_token):
        from backend.middleware import get_authenticated_uid

        mock_verify_token.verify_id_token.side_effect = RuntimeError("network error")

        request = MagicMock()
        request.headers = {"Authorization": "Bearer token"}
        request.url.path = "/api/brands"

        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_uid(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# verify_brand_owner tests
# ---------------------------------------------------------------------------


class TestVerifyBrandOwner:
    """Tests for verify_brand_owner()."""

    @pytest.mark.asyncio
    async def test_owner_matches_returns_uid(self, sample_brand):
        from backend.middleware import verify_brand_owner

        request = MagicMock()
        request.path_params = {"brand_id": TEST_BRAND_ID}

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=sample_brand)
            result = await verify_brand_owner(request, user_uid=TEST_UID)
        assert result == TEST_UID

    @pytest.mark.asyncio
    async def test_wrong_owner_raises_403(self, sample_brand):
        from backend.middleware import verify_brand_owner

        request = MagicMock()
        request.path_params = {"brand_id": TEST_BRAND_ID}

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=sample_brand)
            with pytest.raises(HTTPException) as exc_info:
                await verify_brand_owner(request, user_uid="wrong-uid")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_brand_not_found_raises_404(self):
        from backend.middleware import verify_brand_owner

        request = MagicMock()
        request.path_params = {"brand_id": "nonexistent"}

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=None)
            with pytest.raises(HTTPException) as exc_info:
                await verify_brand_owner(request, user_uid=TEST_UID)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_unclaimed_brand_allows_access(self):
        from backend.middleware import verify_brand_owner

        request = MagicMock()
        request.path_params = {"brand_id": "unclaimed"}

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value={"brand_id": "unclaimed", "owner_uid": None})
            result = await verify_brand_owner(request, user_uid=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_brand_id_in_path_skips_check(self):
        from backend.middleware import verify_brand_owner

        request = MagicMock()
        request.path_params = {}

        result = await verify_brand_owner(request, user_uid=TEST_UID)
        assert result == TEST_UID

    @pytest.mark.asyncio
    async def test_unauthenticated_on_claimed_brand_raises_401(self, sample_brand):
        from backend.middleware import verify_brand_owner

        request = MagicMock()
        request.path_params = {"brand_id": TEST_BRAND_ID}

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=sample_brand)
            with pytest.raises(HTTPException) as exc_info:
                await verify_brand_owner(request, user_uid=None)
        assert exc_info.value.status_code == 401
