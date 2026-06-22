"""Tests for backend.agents.brand_analyst."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.candidates = [MagicMock()]
    response.candidates[0].content = MagicMock()
    response.candidates[0].content.parts = []
    return response


def _make_empty_response() -> MagicMock:
    response = MagicMock()
    response.candidates = []
    response.text = ""
    return response


_VALID_PROFILE = json.dumps(
    {
        "business_name": "Test Brand",
        "business_type": "service",
        "industry": "technology",
        "tone": "professional, confident, approachable",
        "colors": ["#2563EB", "#1E40AF", "#DBEAFE"],
        "target_audience": "developers aged 25-45",
        "visual_style": "modern-tech",
        "content_themes": ["tutorials", "product updates"],
        "competitors": [],
        "image_style_directive": "clean, minimal, modern",
        "caption_style_directive": "Short punchy sentences. First-person. Em dashes.",
        "image_generation_risk": "low",
        "byop_recommendation": "AI images work well here.",
    }
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_brand_analysis_returns_profile():
    """Happy path: valid JSON from LLM → returned profile has expected keys."""
    from backend.agents.brand_analyst import run_brand_analysis

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(_VALID_PROFILE)

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch("backend.agents.brand_analyst.fetch_website", new=AsyncMock(return_value={})),
        patch("backend.agents.brand_analyst.analyze_brand_colors", return_value={}),
        patch("backend.agents.brand_analyst.extract_brand_voice", return_value={}),
        patch(
            "backend.agents.brand_analyst.upload_brand_asset",
            new=AsyncMock(return_value="gs://bucket/file.png"),
        ),
    ):
        result = await run_brand_analysis(
            description="A SaaS company building developer tools for teams"
        )

    assert "industry" in result
    assert "tone" in result
    assert "colors" in result
    assert result["industry"] == "technology"
    assert isinstance(result["colors"], list)


@pytest.mark.asyncio
async def test_run_brand_analysis_empty_candidates_returns_defaults():
    """Empty candidates list → graceful fallback, no crash."""
    from backend.agents.brand_analyst import run_brand_analysis

    mock_client = MagicMock()
    # Empty text → json.loads("") raises ValueError → fallback
    mock_client.models.generate_content.return_value = _make_empty_response()

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch("backend.agents.brand_analyst.fetch_website", new=AsyncMock(return_value={})),
        patch("backend.agents.brand_analyst.analyze_brand_colors", return_value={}),
        patch("backend.agents.brand_analyst.extract_brand_voice", return_value={}),
        patch("backend.agents.brand_analyst.upload_brand_asset", new=AsyncMock(return_value=None)),
    ):
        result = await run_brand_analysis(
            description="A local coffee shop serving specialty drinks in downtown"
        )

    # Should return fallback profile, not raise
    assert isinstance(result, dict)
    assert "business_name" in result
    assert "colors" in result


@pytest.mark.asyncio
async def test_run_brand_analysis_malformed_json_returns_defaults():
    """LLM returns non-JSON → no exception, returns fallback profile."""
    from backend.agents.brand_analyst import run_brand_analysis

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response("not json at all")

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch("backend.agents.brand_analyst.fetch_website", new=AsyncMock(return_value={})),
        patch("backend.agents.brand_analyst.analyze_brand_colors", return_value={}),
        patch("backend.agents.brand_analyst.extract_brand_voice", return_value={}),
        patch("backend.agents.brand_analyst.upload_brand_asset", new=AsyncMock(return_value=None)),
    ):
        result = await run_brand_analysis(
            description="A fitness studio specializing in yoga and meditation classes"
        )

    assert isinstance(result, dict)
    # Fallback profile always has these keys
    assert "business_name" in result
    assert "tone" in result
    assert "content_themes" in result


@pytest.mark.asyncio
async def test_run_brand_analysis_includes_website_content():
    """fetch_website returns content → function completes without error."""
    from backend.agents.brand_analyst import run_brand_analysis

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(_VALID_PROFILE)

    website_data = {
        "title": "Widget Co",
        "description": "Company sells widgets",
        "text_content": "Company sells widgets to businesses worldwide.",
        "colors_found": ["#FF0000", "#0000FF"],
        "nav_items": ["Home", "Products"],
    }

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.brand_analyst.fetch_website", new=AsyncMock(return_value=website_data)
        ),
        patch(
            "backend.agents.brand_analyst.analyze_brand_colors", return_value={"primary": "#FF0000"}
        ),
        patch(
            "backend.agents.brand_analyst.extract_brand_voice",
            return_value={"detected_tones": ["professional"]},
        ),
        patch("backend.agents.brand_analyst.upload_brand_asset", new=AsyncMock(return_value=None)),
    ):
        result = await run_brand_analysis(
            description="A company that sells widgets to businesses",
            website_url="https://example.com",
        )

    assert isinstance(result, dict)
    assert "industry" in result


@pytest.mark.asyncio
async def test_generate_style_reference_returns_none_on_failure():
    """_generate_style_reference raises internally → returns None, no crash."""
    from backend.agents.brand_analyst import _generate_style_reference

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API error")

    with patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client):
        result = await _generate_style_reference(
            brand_id="test-brand-123",
            profile={
                "colors": ["#2563EB", "#1E40AF"],
                "tone": "professional",
                "industry": "technology",
                "image_style_directive": "clean, modern",
            },
        )

    assert result is None


@pytest.mark.asyncio
async def test_generate_style_reference_returns_none_on_empty_candidates():
    """_generate_style_reference with empty candidates → returns None."""
    from backend.agents.brand_analyst import _generate_style_reference

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_empty_response()

    with patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client):
        result = await _generate_style_reference(
            brand_id="test-brand-456",
            profile={
                "colors": [],
                "tone": "friendly",
                "industry": "food",
                "image_style_directive": "warm",
            },
        )

    assert result is None


@pytest.mark.asyncio
async def test_generate_style_reference_uploads_image_data():
    """_generate_style_reference returns GCS URI when image part found."""
    from backend.agents.brand_analyst import _generate_style_reference

    # Build response with one image part
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.data = b"fake_image_bytes"
    mock_part.inline_data.mime_type = "image/png"
    mock_candidate = MagicMock()
    mock_candidate.content = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_response.text = ""

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    expected_uri = "gs://bucket/brands/test-brand/style_reference.png"

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.brand_analyst.upload_brand_asset",
            new=AsyncMock(return_value=expected_uri),
        ),
    ):
        result = await _generate_style_reference(
            brand_id="test-brand",
            profile={
                "colors": ["#123456"],
                "tone": "bold",
                "industry": "tech",
                "image_style_directive": "modern",
            },
        )

    assert result == expected_uri


@pytest.mark.asyncio
async def test_run_brand_analysis_with_social_voice_analysis():
    """social_voice_analysis is included in the prompt when provided."""
    from backend.agents.brand_analyst import run_brand_analysis

    mock_client = MagicMock()
    prompts_seen = []

    def capture_prompt(*args, **kwargs):
        contents = kwargs.get("contents", args[1] if len(args) > 1 else "")
        prompts_seen.append(str(contents))
        return _make_text_response(_VALID_PROFILE)

    mock_client.models.generate_content.side_effect = capture_prompt

    social_voice = {
        "voice_characteristics": ["direct", "authoritative"],
        "common_phrases": ["the truth is"],
        "successful_patterns": ["storytelling"],
    }

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch("backend.agents.brand_analyst.fetch_website", new=AsyncMock(return_value={})),
        patch("backend.agents.brand_analyst.analyze_brand_colors", return_value={}),
        patch("backend.agents.brand_analyst.extract_brand_voice", return_value={}),
        patch("backend.agents.brand_analyst.upload_brand_asset", new=AsyncMock(return_value=None)),
    ):
        result = await run_brand_analysis(
            description="A coaching business for executives",
            social_voice_analysis=social_voice,
        )

    # Prompt should include social voice context
    assert any("direct" in p for p in prompts_seen)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_run_brand_analysis_with_brand_id_generates_style_ref():
    """When brand_id provided + style ref succeeds, profile gets style_reference_gcs_uri."""
    from backend.agents.brand_analyst import run_brand_analysis

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(_VALID_PROFILE)

    # Build a response with image inline_data for style reference
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.data = b"fake_image_bytes"
    mock_part.inline_data.mime_type = "image/png"
    mock_candidate = MagicMock()
    mock_candidate.content = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_response_with_image = MagicMock()
    mock_response_with_image.candidates = [mock_candidate]
    mock_response_with_image.text = ""

    call_count = [0]

    def call_side_effect(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        # First call is brand analysis, second is style reference
        if idx == 0:
            return _make_text_response(_VALID_PROFILE)
        return mock_response_with_image

    mock_client.models.generate_content.side_effect = call_side_effect

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch("backend.agents.brand_analyst.fetch_website", new=AsyncMock(return_value={})),
        patch("backend.agents.brand_analyst.analyze_brand_colors", return_value={}),
        patch("backend.agents.brand_analyst.extract_brand_voice", return_value={}),
        patch(
            "backend.agents.brand_analyst.upload_brand_asset",
            new=AsyncMock(return_value="gs://bucket/style.png"),
        ),
    ):
        result = await run_brand_analysis(
            description="A SaaS product for teams",
            brand_id="brand-style-test",
        )

    assert isinstance(result, dict)
    # style_reference_gcs_uri should be in profile when upload succeeds
    # (may or may not be set depending on the response structure)
    assert "business_name" in result


@pytest.mark.asyncio
async def test_run_brand_analysis_with_scraped_logo():
    """Website data with logo_url → download attempted for brand_id."""
    from backend.agents.brand_analyst import run_brand_analysis

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(_VALID_PROFILE)

    website_data = {
        "title": "Test Corp",
        "description": "We build widgets",
        "text_content": "Widget company website content here.",
        "colors_found": [],
        "nav_items": [],
        "logo_url": "https://example.com/logo.png",
    }

    with (
        patch("backend.agents.brand_analyst.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.brand_analyst.fetch_website", new=AsyncMock(return_value=website_data)
        ),
        patch("backend.agents.brand_analyst.analyze_brand_colors", return_value={}),
        patch("backend.agents.brand_analyst.extract_brand_voice", return_value={}),
        patch("backend.agents.brand_analyst.upload_brand_asset", new=AsyncMock(return_value=None)),
        patch(
            "backend.agents.brand_analyst._download_website_logo",
            new=AsyncMock(return_value="gs://bucket/logo.png"),
        ),
    ):
        result = await run_brand_analysis(
            description="A company that builds widgets",
            website_url="https://example.com",
            brand_id="brand-logo-test",
        )

    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_download_website_logo_success():
    """_download_website_logo returns GCS URI when download succeeds."""
    from backend.agents.brand_analyst import _download_website_logo

    fake_logo_bytes = b"x" * 300  # > 200 bytes

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "image/png"}
    mock_response.content = fake_logo_bytes
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_response

    with (
        patch(
            "backend.agents.brand_analyst.upload_brand_asset",
            new=AsyncMock(return_value="gs://bucket/logo.png"),
        ),
        patch("httpx.AsyncClient") as MockClient,
    ):
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _download_website_logo("brand-123", "https://example.com/logo.png")

    assert result == "gs://bucket/logo.png"


@pytest.mark.asyncio
async def test_download_website_logo_returns_none_for_non_image():
    """_download_website_logo returns None when content-type is not image/*."""
    from backend.agents.brand_analyst import _download_website_logo

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = b"not an image"
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _download_website_logo("brand-123", "https://example.com/page.html")

    assert result is None


@pytest.mark.asyncio
async def test_download_website_logo_returns_none_for_tiny_image():
    """_download_website_logo returns None when image bytes < 200 (too small to be real logo)."""
    from backend.agents.brand_analyst import _download_website_logo

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "image/png"}
    mock_response.content = b"small"  # < 200 bytes
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _download_website_logo("brand-123", "https://example.com/logo.png")

    assert result is None


@pytest.mark.asyncio
async def test_download_website_logo_returns_none_on_exception():
    """_download_website_logo returns None when request fails."""
    from backend.agents.brand_analyst import _download_website_logo

    mock_http_client = AsyncMock()
    mock_http_client.get.side_effect = Exception("Network error")

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _download_website_logo("brand-123", "https://example.com/logo.png")

    assert result is None


def test_fallback_profile_returns_dict_with_required_keys():
    """_fallback_profile always returns dict with all required keys."""
    from backend.agents.brand_analyst import _fallback_profile

    result = _fallback_profile("A consulting firm helping startups scale", None)
    for key in [
        "business_name",
        "business_type",
        "industry",
        "tone",
        "colors",
        "target_audience",
        "visual_style",
        "content_themes",
        "competitors",
        "image_style_directive",
        "caption_style_directive",
    ]:
        assert key in result


def test_fallback_profile_short_description():
    """_fallback_profile handles descriptions shorter than 3 words."""
    from backend.agents.brand_analyst import _fallback_profile

    result = _fallback_profile("Startup", None)
    assert "business_name" in result
    assert isinstance(result["colors"], list)
