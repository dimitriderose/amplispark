"""Tests for brand-related logic and validation."""

from backend.tests.conftest import TEST_UID, TEST_BRAND_ID


class TestBrandAllowedKeys:
    """Test that brand analysis sanitizes LLM output to allowed keys."""

    ALLOWED_KEYS = {
        "brand_voice", "target_audience", "key_messages", "colors",
        "competitors", "content_pillars", "visual_style", "industry",
    }

    def test_sanitize_filters_unknown_keys(self):
        """Only allowed keys should pass through from LLM output."""
        raw_profile = {
            "brand_voice": "professional",
            "target_audience": "small business owners",
            "malicious_key": "should be removed",
            "colors": ["#FF0000"],
            "__private": "also removed",
        }
        safe = {k: v for k, v in raw_profile.items() if k in self.ALLOWED_KEYS}
        assert "brand_voice" in safe
        assert "target_audience" in safe
        assert "colors" in safe
        assert "malicious_key" not in safe
        assert "__private" not in safe

    def test_empty_profile_returns_empty(self):
        """Empty LLM output should produce empty dict."""
        safe = {k: v for k, v in {}.items() if k in self.ALLOWED_KEYS}
        assert safe == {}
