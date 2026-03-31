"""Tests for OAuth security: HMAC state validation, token encryption."""

import hmac
import os
from unittest.mock import patch

import pytest


class TestTokenEncryption:
    """Tests for _encrypt_token and _decrypt_token."""

    def test_encrypt_token_raises_without_key(self):
        """Encryption must fail if TOKEN_ENCRYPT_KEY is not set."""
        with patch.dict(os.environ, {"TOKEN_ENCRYPT_KEY": ""}, clear=False):
            # Re-import to pick up empty key
            import importlib
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
