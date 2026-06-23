"""Tests for dependency upgrade changes (Issue #7).

Covers:
- firebase-admin 7.x: get_app()/ValueError init guard (EC-7)
- verify_id_token executor offload (EC-1)
- Exception log safety — no token leakage (ER-4, ER-10)
- Unclaimed-brand write guard edge cases (EC-2, EC-3, EC-4, EC-5)
- Empty Bearer token (EC-6)
- WebSocket auth: missing token, expired, invalid, generic error (ER-8, ER-9, ER-10)
- verify_ws_brand_owner: missing brand_id, brand not found, wrong owner, owner match
"""

import importlib
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, WebSocketException, status

from backend.middleware import (
    get_authenticated_uid,
    get_ws_authenticated_uid,
    verify_brand_owner,
    verify_ws_brand_owner,
)
from backend.tests.conftest import TEST_BRAND_ID, TEST_UID

UNCLAIMED_BRAND = {"brand_id": "unclaimed", "owner_uid": None}
CLAIMED_BRAND = {"brand_id": TEST_BRAND_ID, "owner_uid": TEST_UID}


# ---------------------------------------------------------------------------
# Firebase Admin SDK init guard (EC-7)
# ---------------------------------------------------------------------------


class TestFirebaseAdminInitGuard:
    def test_initialize_app_called_when_get_app_raises_value_error(self):
        mock_firebase = MagicMock()
        mock_firebase.get_app.side_effect = ValueError("no app")

        with patch.dict("sys.modules", {"firebase_admin": mock_firebase}):
            import backend.middleware as mw

            importlib.reload(mw)

        mock_firebase.initialize_app.assert_called_once()

    def test_initialize_app_not_called_when_app_already_exists(self):
        mock_firebase = MagicMock()
        mock_firebase.get_app.return_value = MagicMock()

        with patch.dict("sys.modules", {"firebase_admin": mock_firebase}):
            import backend.middleware as mw

            importlib.reload(mw)

        mock_firebase.initialize_app.assert_not_called()


# ---------------------------------------------------------------------------
# get_authenticated_uid — executor offload + edge cases
# ---------------------------------------------------------------------------


class TestGetAuthenticatedUidExtended:
    async def test_verify_id_token_called_via_run_in_executor(self, mock_verify_token):
        request = MagicMock()
        request.headers = {"Authorization": "Bearer valid-token"}
        request.url.path = "/api/brands"

        with patch("backend.middleware.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_asyncio.get_running_loop.return_value = mock_loop
            mock_loop.run_in_executor = AsyncMock(return_value={"uid": TEST_UID})

            uid = await get_authenticated_uid(request)

        assert uid == TEST_UID
        mock_loop.run_in_executor.assert_awaited_once()
        args = mock_loop.run_in_executor.call_args[0]
        assert args[0] is None  # executor=None means default thread pool

    async def test_empty_bearer_token_raises_401(self, mock_verify_token):
        mock_verify_token.verify_id_token.side_effect = mock_verify_token.InvalidIdTokenError()

        request = MagicMock()
        request.headers = {"Authorization": "Bearer "}
        request.url.path = "/api/brands"

        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_uid(request)
        assert exc_info.value.status_code == 401

    async def test_generic_exception_does_not_leak_token_in_log(self, mock_verify_token, caplog):
        secret_token = "supersecret.jwt.payload"
        mock_verify_token.verify_id_token.side_effect = RuntimeError(f"token={secret_token}")

        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {secret_token}"}
        request.url.path = "/api/brands"

        with caplog.at_level(logging.WARNING, logger="backend.middleware"):
            with pytest.raises(HTTPException):
                await get_authenticated_uid(request)

        for record in caplog.records:
            assert secret_token not in record.getMessage()
        assert any("RuntimeError" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# verify_brand_owner — unclaimed brand write guard edge cases
# ---------------------------------------------------------------------------


class TestVerifyBrandOwnerWriteGuard:
    @pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "POST"])
    async def test_unclaimed_brand_blocks_unauthenticated_write_methods(self, method):
        request = MagicMock()
        request.path_params = {"brand_id": "unclaimed"}
        request.method = method

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=UNCLAIMED_BRAND)
            with pytest.raises(HTTPException) as exc_info:
                await verify_brand_owner(request, user_uid=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    async def test_unclaimed_brand_allows_unauthenticated_safe_methods(self, method):
        request = MagicMock()
        request.path_params = {"brand_id": "unclaimed"}
        request.method = method

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=UNCLAIMED_BRAND)
            result = await verify_brand_owner(request, user_uid=None)
        assert result is None

    async def test_unclaimed_brand_allows_authenticated_write(self):
        request = MagicMock()
        request.path_params = {"brand_id": "unclaimed"}
        request.method = "POST"

        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=UNCLAIMED_BRAND)
            result = await verify_brand_owner(request, user_uid=TEST_UID)
        assert result == TEST_UID


# ---------------------------------------------------------------------------
# get_ws_authenticated_uid
# ---------------------------------------------------------------------------


class TestGetWsAuthenticatedUid:
    def _make_websocket(self, protocol_header: str) -> MagicMock:
        ws = MagicMock()
        ws.headers = {"sec-websocket-protocol": protocol_header}
        ws.url.path = "/ws/voice"
        return ws

    async def test_valid_auth_subprotocol_returns_uid(self, mock_verify_token):
        ws = self._make_websocket("auth.valid-token")
        uid = await get_ws_authenticated_uid(ws)
        assert uid == TEST_UID

    async def test_token_extracted_from_multiple_subprotocols(self, mock_verify_token):
        ws = self._make_websocket("v1.protocol, auth.valid-token, other")
        uid = await get_ws_authenticated_uid(ws)
        assert uid == TEST_UID

    async def test_missing_auth_subprotocol_raises_1008(self, mock_verify_token):
        ws = self._make_websocket("v1.protocol")
        with pytest.raises(WebSocketException) as exc_info:
            await get_ws_authenticated_uid(ws)
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_empty_protocol_header_raises_1008(self, mock_verify_token):
        ws = self._make_websocket("")
        with pytest.raises(WebSocketException) as exc_info:
            await get_ws_authenticated_uid(ws)
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_expired_token_raises_1008(self, mock_verify_token):
        mock_verify_token.verify_id_token.side_effect = mock_verify_token.ExpiredIdTokenError()
        ws = self._make_websocket("auth.expired-token")
        with pytest.raises(WebSocketException) as exc_info:
            await get_ws_authenticated_uid(ws)
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION
        assert "expired" in exc_info.value.reason.lower()

    async def test_invalid_token_raises_1008(self, mock_verify_token):
        mock_verify_token.verify_id_token.side_effect = mock_verify_token.InvalidIdTokenError()
        ws = self._make_websocket("auth.bad-token")
        with pytest.raises(WebSocketException) as exc_info:
            await get_ws_authenticated_uid(ws)
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_generic_exception_raises_1008(self, mock_verify_token):
        mock_verify_token.verify_id_token.side_effect = RuntimeError("network error")
        ws = self._make_websocket("auth.some-token")
        with pytest.raises(WebSocketException) as exc_info:
            await get_ws_authenticated_uid(ws)
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_generic_exception_does_not_leak_token_in_log(self, mock_verify_token, caplog):
        secret_token = "supersecret.ws.jwt"
        mock_verify_token.verify_id_token.side_effect = RuntimeError(f"token={secret_token}")
        ws = self._make_websocket(f"auth.{secret_token}")

        with caplog.at_level(logging.WARNING, logger="backend.middleware"):
            with pytest.raises(WebSocketException):
                await get_ws_authenticated_uid(ws)

        for record in caplog.records:
            assert secret_token not in record.getMessage()
        assert any("RuntimeError" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# verify_ws_brand_owner
# ---------------------------------------------------------------------------


class TestVerifyWsBrandOwner:
    def _make_websocket(self, brand_id: str | None) -> MagicMock:
        ws = MagicMock()
        ws.path_params = {"brand_id": brand_id} if brand_id else {}
        ws.url.path = "/ws/voice"
        return ws

    async def test_owner_match_returns_brand_with_uid(self):
        ws = self._make_websocket(TEST_BRAND_ID)
        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=dict(CLAIMED_BRAND))
            result = await verify_ws_brand_owner(ws, user_uid=TEST_UID)
        assert result["_authenticated_uid"] == TEST_UID
        assert result["brand_id"] == TEST_BRAND_ID

    async def test_wrong_owner_raises_1008(self):
        ws = self._make_websocket(TEST_BRAND_ID)
        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=dict(CLAIMED_BRAND))
            with pytest.raises(WebSocketException) as exc_info:
                await verify_ws_brand_owner(ws, user_uid="wrong-uid")
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_brand_not_found_raises_1008(self):
        ws = self._make_websocket("nonexistent")
        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=None)
            with pytest.raises(WebSocketException) as exc_info:
                await verify_ws_brand_owner(ws, user_uid=TEST_UID)
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_missing_brand_id_raises_1008(self):
        ws = self._make_websocket(None)
        with pytest.raises(WebSocketException) as exc_info:
            await verify_ws_brand_owner(ws, user_uid=TEST_UID)
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_unclaimed_brand_allows_access_and_attaches_uid(self):
        ws = self._make_websocket("unclaimed")
        with patch("backend.middleware.firestore_client") as mock_fc:
            mock_fc.get_brand = AsyncMock(return_value=dict(UNCLAIMED_BRAND))
            result = await verify_ws_brand_owner(ws, user_uid=TEST_UID)
        assert result["_authenticated_uid"] == TEST_UID
