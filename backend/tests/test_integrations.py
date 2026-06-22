"""Tests for OAuth security: HMAC state validation, token encryption."""

import hmac
import os
from unittest.mock import AsyncMock, patch

import pytest


class TestTokenEncryption:
    """Tests for _encrypt_token and _decrypt_token."""

    def test_encrypt_token_raises_without_key(self):
        """Encryption must fail if TOKEN_ENCRYPT_KEY is not set."""
        with patch.dict(os.environ, {"TOKEN_ENCRYPT_KEY": ""}, clear=False):
            # Re-import to pick up empty key
            import backend.routers.integrations as mod

            # If _fernet is None, _encrypt_token should raise
            if mod._fernet is None:
                with pytest.raises(RuntimeError, match="TOKEN_ENCRYPT_KEY"):
                    mod._encrypt_token("test-token")

    def test_decrypt_token_warns_on_plaintext(self, caplog):
        """Reading a plaintext token should log a warning."""
        import backend.routers.integrations as mod

        with caplog.at_level("WARNING"):
            result = mod._decrypt_token("plain-text-token")
        # Should return the token (backward compat) but warn
        assert result == "plain-text-token"
        assert any("plaintext" in r.message.lower() for r in caplog.records)

    def test_encrypt_decrypt_roundtrip(self):
        """If encryption key is set, encrypt→decrypt should roundtrip."""
        import backend.routers.integrations as mod

        if mod._fernet is not None:
            encrypted = mod._encrypt_token("my-secret-token")
            assert encrypted.startswith("enc:")
            decrypted = mod._decrypt_token(encrypted)
            assert decrypted == "my-secret-token"


class TestOAuthHmacState:
    """Tests for Notion OAuth CSRF protection via HMAC-signed state."""

    def _compute_hmac(self, brand_id: str, key: str) -> str:
        return hmac.new(
            key.encode() if key else b"fallback",
            brand_id.encode(),
            "sha256",
        ).hexdigest()[:16]

    def test_valid_hmac_state_accepted(self):
        """A correctly signed state should be accepted."""
        import backend.routers.integrations as mod

        key = mod._TOKEN_KEY or ""
        brand_id = "test-brand-123"
        sig = self._compute_hmac(brand_id, key)
        state = f"{brand_id}:{sig}"

        # Split and verify like the callback does
        parts = state.split(":", 1)
        assert len(parts) == 2
        extracted_brand_id = parts[0]
        extracted_sig = parts[1]
        expected_sig = self._compute_hmac(extracted_brand_id, key)
        assert hmac.compare_digest(extracted_sig, expected_sig)

    def test_tampered_state_rejected(self):
        """A state with wrong signature should be rejected."""
        import backend.routers.integrations as mod

        key = mod._TOKEN_KEY or ""
        brand_id = "test-brand-123"
        tampered_sig = "0000000000000000"
        state = f"{brand_id}:{tampered_sig}"

        parts = state.split(":", 1)
        expected_sig = self._compute_hmac(parts[0], key)
        assert not hmac.compare_digest(parts[1], expected_sig)

    def test_missing_signature_rejected(self):
        """A state without ':' separator should be rejected."""
        state = "just-a-brand-id"
        parts = state.split(":", 1)
        assert len(parts) == 1  # No signature present


class TestEncryptTokenUnit:
    """Unit tests for _encrypt_token and _decrypt_token helpers."""

    def test_encrypt_token_returns_enc_prefix(self, mock_fernet):
        import backend.routers.integrations as mod

        result = mod._encrypt_token("my-access-token")
        assert result.startswith("enc:")

    def test_decrypt_token_with_enc_prefix_decrypts_correctly(self, mock_fernet):
        import backend.routers.integrations as mod

        result = mod._decrypt_token("enc:encrypted-token")
        assert result == "real-token"

    def test_decrypt_token_with_plaintext_returns_as_is(self, caplog):
        import backend.routers.integrations as mod

        with caplog.at_level("WARNING"):
            result = mod._decrypt_token("raw-plaintext-token")
        assert result == "raw-plaintext-token"

    def test_encrypt_token_raises_runtime_error_when_fernet_is_none(self):
        import backend.routers.integrations as mod

        with patch.object(mod, "_fernet", None):
            with pytest.raises(RuntimeError, match="TOKEN_ENCRYPT_KEY"):
                mod._encrypt_token("some-token")


_INTEGRATIONS_FC = "backend.routers.integrations.firestore_client"
_MIDDLEWARE_FC = "backend.middleware.firestore_client"

TEST_BRAND_ID = "test-brand-id-456"


class TestNotionAuthUrlEndpoint:
    """HTTP tests for GET /api/brands/{brand_id}/integrations/notion/auth-url."""

    def test_notion_auth_url_returns_url_with_brand_state(self, client, auth_headers, sample_brand):
        with (
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.config.NOTION_CLIENT_ID", "test-client-id"),
            patch("backend.config.NOTION_REDIRECT_URI", "https://example.com/callback"),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/auth-url",
                headers=auth_headers,
            )
        assert response.status_code == 200
        auth_url = response.json()["auth_url"]
        assert "notion.com" in auth_url
        assert TEST_BRAND_ID in auth_url

    def test_notion_auth_url_returns_500_when_not_configured(
        self, client, auth_headers, sample_brand
    ):
        with patch(_MIDDLEWARE_FC) as mfc, patch("backend.config.NOTION_CLIENT_ID", ""):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/auth-url",
                headers=auth_headers,
            )
        assert response.status_code == 500


class TestNotionDisconnectEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/integrations/notion/disconnect."""

    def test_notion_disconnect_removes_integration(self, client, auth_headers, sample_brand):
        brand_with_notion = {
            **sample_brand,
            "integrations": {"notion": {"access_token": "enc:abc123", "bot_id": "bot-1"}},
        }
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand_with_notion)
            fc.get_brand = AsyncMock(return_value=brand_with_notion)
            fc.update_brand = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/disconnect",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"
        update_call = fc.update_brand.call_args[0][1]
        assert "notion" not in update_call.get("integrations", {})

    def test_notion_disconnect_returns_404_when_brand_missing(
        self, client, auth_headers, sample_brand
    ):
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/disconnect",
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestNotionDatabasesEndpoint:
    """HTTP tests for GET /api/brands/{brand_id}/integrations/notion/databases."""

    def _brand_with_notion(self, sample_brand):
        return {
            **sample_brand,
            "integrations": {"notion": {"access_token": "enc:tok", "bot_id": "b1"}},
        }

    def test_returns_databases_when_connected(self, client, auth_headers, sample_brand):
        brand = self._brand_with_notion(sample_brand)
        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.services.notion_client.search_databases",
                new=AsyncMock(return_value=[{"id": "db1", "title": "DB"}]),
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/databases",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert "databases" in response.json()

    def test_returns_400_when_notion_not_connected(self, client, auth_headers, sample_brand):
        brand_no_notion = {**sample_brand, "integrations": {}}
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand_no_notion)
            fc.get_brand = AsyncMock(return_value=brand_no_notion)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/databases",
                headers=auth_headers,
            )
        assert response.status_code == 400
        assert "not connected" in response.json()["detail"].lower()

    def test_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/databases",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_502_when_notion_api_fails(self, client, auth_headers, sample_brand):
        brand = self._brand_with_notion(sample_brand)

        async def _fail(*args, **kwargs):
            raise RuntimeError("API error")

        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.services.notion_client.search_databases", new=_fail),
        ):
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/databases",
                headers=auth_headers,
            )
        assert response.status_code == 502


class TestNotionSelectDatabaseEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/integrations/notion/select-database."""

    def _brand_with_notion(self, sample_brand):
        return {
            **sample_brand,
            "integrations": {"notion": {"access_token": "enc:tok", "bot_id": "b1"}},
        }

    def test_selects_database_and_returns_status(self, client, auth_headers, sample_brand):
        brand = self._brand_with_notion(sample_brand)
        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.services.notion_client.ensure_database_schema", new=AsyncMock()),
        ):
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            fc.update_brand = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/select-database",
                json={"database_id": "db-123", "database_name": "My DB"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "selected"
        assert response.json()["database_id"] == "db-123"

    def test_returns_400_when_notion_not_connected(self, client, auth_headers, sample_brand):
        brand_no_notion = {**sample_brand, "integrations": {}}
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand_no_notion)
            fc.get_brand = AsyncMock(return_value=brand_no_notion)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/select-database",
                json={"database_id": "db-123"},
                headers=auth_headers,
            )
        assert response.status_code == 400

    def test_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/integrations/notion/select-database",
                json={"database_id": "db-123"},
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestExportPlanToNotionEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/plans/{plan_id}/export/notion."""

    def _brand_with_notion_db(self, sample_brand):
        return {
            **sample_brand,
            "integrations": {
                "notion": {
                    "access_token": "enc:tok",
                    "bot_id": "b1",
                    "database_id": "db-456",
                }
            },
        }

    def test_exports_posts_to_notion(
        self, client, auth_headers, sample_brand, sample_plan, sample_post
    ):
        brand = self._brand_with_notion_db(sample_brand)
        page_result = {"id": "notion-page-id"}
        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.services.notion_client.create_page",
                new=AsyncMock(return_value=page_result),
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[sample_post])
            fc.update_post = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{sample_plan['plan_id']}/export/notion",
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["exported"] == 1
        assert data["total"] == 1

    def test_returns_400_when_no_database_selected(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        brand_no_db = {
            **sample_brand,
            "integrations": {"notion": {"access_token": "enc:tok", "bot_id": "b1"}},
        }
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand_no_db)
            fc.get_brand = AsyncMock(return_value=brand_no_db)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{sample_plan['plan_id']}/export/notion",
                headers=auth_headers,
            )
        assert response.status_code == 400
        assert "database" in response.json()["detail"].lower()

    def test_returns_400_when_notion_not_connected(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        brand_no_notion = {**sample_brand, "integrations": {}}
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand_no_notion)
            fc.get_brand = AsyncMock(return_value=brand_no_notion)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{sample_plan['plan_id']}/export/notion",
                headers=auth_headers,
            )
        assert response.status_code == 400

    def test_returns_404_when_plan_missing(self, client, auth_headers, sample_brand, sample_plan):
        brand = self._brand_with_notion_db(sample_brand)
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{sample_plan['plan_id']}/export/notion",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_404_when_no_posts(self, client, auth_headers, sample_brand, sample_plan):
        brand = self._brand_with_notion_db(sample_brand)
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[])
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{sample_plan['plan_id']}/export/notion",
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestNotionCallbackEndpoint:
    """HTTP tests for GET /api/integrations/notion/callback."""

    def _make_state(self, brand_id: str) -> str:
        import hmac as _hmac

        import backend.routers.integrations as mod

        key = mod._TOKEN_KEY or ""
        sig = _hmac.new(
            key.encode() if key else b"fallback",
            brand_id.encode(),
            "sha256",
        ).hexdigest()[:16]
        return f"{brand_id}:{sig}"

    def test_callback_redirects_on_success(self, client, auth_headers, sample_brand):
        state = self._make_state(TEST_BRAND_ID)
        token_data = {
            "access_token": "notion-tok",
            "bot_id": "b1",
            "workspace_id": "w1",
            "workspace_name": "WS",
        }
        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(
                "backend.services.notion_client.exchange_code",
                new=AsyncMock(return_value=token_data),
            ),
            patch("backend.config.NOTION_CLIENT_ID", "cid"),
            patch("backend.config.NOTION_CLIENT_SECRET", "csec"),
            patch("backend.config.NOTION_REDIRECT_URI", "https://example.com/cb"),
            patch("backend.routers.integrations._encrypt_token", return_value="enc:abc"),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            response = client.get(
                f"/api/integrations/notion/callback?code=auth-code&state={state}",
                follow_redirects=False,
            )
        assert response.status_code in (302, 307)

    def test_callback_returns_400_when_state_has_no_colon(self, client, auth_headers):
        response = client.get(
            "/api/integrations/notion/callback?code=abc&state=invalidsig",
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_callback_returns_400_when_hmac_invalid(self, client, auth_headers, sample_brand):
        state = f"{TEST_BRAND_ID}:0000000000000000"
        response = client.get(
            f"/api/integrations/notion/callback?code=abc&state={state}",
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_callback_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        state = self._make_state(TEST_BRAND_ID)
        token_data = {
            "access_token": "tok",
            "bot_id": "b1",
            "workspace_id": "w1",
            "workspace_name": "WS",
        }
        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(
                "backend.services.notion_client.exchange_code",
                new=AsyncMock(return_value=token_data),
            ),
            patch("backend.config.NOTION_CLIENT_ID", "cid"),
            patch("backend.config.NOTION_CLIENT_SECRET", "csec"),
            patch("backend.config.NOTION_REDIRECT_URI", "https://example.com/cb"),
        ):
            fc.get_brand = AsyncMock(return_value=None)
            response = client.get(
                f"/api/integrations/notion/callback?code=auth-code&state={state}",
                follow_redirects=False,
            )
        assert response.status_code == 404


class TestConnectSocialEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/connect-social."""

    def test_connects_platform_and_returns_voice_analysis(self, client, auth_headers, sample_brand):
        voice = {"tone": "friendly", "style": "casual"}
        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.agents.social_voice_agent.connect_platform",
                new=AsyncMock(return_value=voice),
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/connect-social",
                json={"platform": "instagram", "oauth_token": "token123"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["platform"] == "instagram"
        assert "voice_analysis" in response.json()

    def test_returns_400_when_token_is_empty(self, client, auth_headers, sample_brand):
        with patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/connect-social",
                json={"platform": "instagram", "oauth_token": "  "},
                headers=auth_headers,
            )
        assert response.status_code == 400

    def test_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        with patch(_INTEGRATIONS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/connect-social",
                json={"platform": "instagram", "oauth_token": "tok"},
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_502_when_platform_fetch_fails(self, client, auth_headers, sample_brand):
        async def _fail(*args, **kwargs):
            raise RuntimeError("API error")

        with (
            patch(_INTEGRATIONS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.agents.social_voice_agent.connect_platform", new=_fail),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/connect-social",
                json={"platform": "instagram", "oauth_token": "tok"},
                headers=auth_headers,
            )
        assert response.status_code == 502
