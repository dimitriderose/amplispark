"""Tests for backend.agents.review_agent."""

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


def _make_empty_response() -> MagicMock:
    response = MagicMock()
    response.candidates = []
    response.text = ""
    return response


_VALID_REVIEW_JSON = json.dumps(
    {
        "structural_issues": [],
        "brand_alignment": "strong",
        "strengths": ["Specific hook", "Clear value proposition"],
        "improvements": ["Add more specifics"],
        "revision_notes": None,
        "revised_hashtags": ["coding", "devproductivity", "saas"],
        "engagement_scores": {
            "hook_strength": 8,
            "relevance": 9,
            "cta_effectiveness": 7,
            "platform_fit": 8,
            "teaching_depth": 8,
        },
        "engagement_prediction": "high",
    }
)

_BRAND_PROFILE = {
    "business_name": "Test Brand",
    "industry": "technology",
    "tone": "professional, bold",
    "target_audience": "developers aged 25-45",
    "caption_style_directive": "Short punchy sentences.",
}

_SAMPLE_POST = {
    "caption": "Three habits that doubled my code review speed.\n\nMost reviews take 45 minutes. Mine take 12.",
    "hashtags": ["coding", "devproductivity"],
    "platform": "instagram",
    "derivative_type": "original",
    "pillar": "education",
    "content_theme": "Developer productivity",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_post_returns_score_and_feedback():
    """Happy path: valid LLM JSON → result has score, brand_alignment, etc."""
    from backend.agents.review_agent import review_post

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(_VALID_REVIEW_JSON)

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_client):
        result = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    assert "score" in result
    assert "brand_alignment" in result
    assert "strengths" in result
    assert "improvements" in result
    assert "approved" in result
    assert "engagement_scores" in result
    assert isinstance(result["score"], int)
    assert 1 <= result["score"] <= 10


@pytest.mark.asyncio
async def test_review_post_score_computed_from_engagement():
    """Score is computed deterministically from engagement_scores."""
    from backend.agents.review_agent import review_post

    # High engagement scores → high final score
    high_scores_json = json.dumps(
        {
            "structural_issues": [],
            "brand_alignment": "strong",
            "strengths": ["Strong hook"],
            "improvements": [],
            "revision_notes": None,
            "revised_hashtags": [],
            "engagement_scores": {
                "hook_strength": 9,
                "relevance": 9,
                "cta_effectiveness": 9,
                "platform_fit": 9,
                "teaching_depth": 9,
            },
            "engagement_prediction": "viral",
        }
    )

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(high_scores_json)

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_client):
        result = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    assert result["score"] >= 7
    assert result["approved"] is True


@pytest.mark.asyncio
async def test_review_post_handles_malformed_json():
    """Non-JSON response → no crash, returns fallback dict."""
    from backend.agents.review_agent import review_post

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response("not valid json")

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_client):
        result = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    assert isinstance(result, dict)
    assert "score" in result
    # Fallback score is 7
    assert result["score"] == 7


@pytest.mark.asyncio
async def test_review_post_empty_candidates_returns_defaults():
    """LLM returns empty text → graceful fallback, no crash."""
    from backend.agents.review_agent import review_post

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_empty_response()

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_client):
        result = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    assert isinstance(result, dict)
    assert "score" in result
    assert "approved" in result


@pytest.mark.asyncio
async def test_review_post_structural_issues_lower_score():
    """Structural issues penalize the computed score."""
    from backend.agents.review_agent import review_post

    # Moderate engagement but multiple structural issues → score should be lower
    with_issues_json = json.dumps(
        {
            "structural_issues": [
                "Caption uses banned hook pattern",
                "Exclamation spam detected",
                "Vague social proof used",
            ],
            "brand_alignment": "moderate",
            "strengths": ["On-brand tone"],
            "improvements": ["Fix banned hook", "Remove social proof"],
            "revision_notes": "Fix the opener and remove vague claims",
            "revised_hashtags": [],
            "engagement_scores": {
                "hook_strength": 6,
                "relevance": 7,
                "cta_effectiveness": 6,
                "platform_fit": 7,
                "teaching_depth": 6,
            },
            "engagement_prediction": "low",
        }
    )

    no_issues_json = json.dumps(
        {
            "structural_issues": [],
            "brand_alignment": "strong",
            "strengths": ["Clear hook"],
            "improvements": [],
            "revision_notes": None,
            "revised_hashtags": [],
            "engagement_scores": {
                "hook_strength": 6,
                "relevance": 7,
                "cta_effectiveness": 6,
                "platform_fit": 7,
                "teaching_depth": 6,
            },
            "engagement_prediction": "medium",
        }
    )

    mock_with_issues = MagicMock()
    mock_with_issues.models.generate_content.return_value = _make_text_response(with_issues_json)

    mock_no_issues = MagicMock()
    mock_no_issues.models.generate_content.return_value = _make_text_response(no_issues_json)

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_with_issues):
        result_with = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_no_issues):
        result_without = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    # Same engagement scores but issues should lower the score
    assert result_with["score"] <= result_without["score"]


@pytest.mark.asyncio
async def test_review_post_revision_notes_null_when_no_issues():
    """revision_notes is None when structural_issues is empty."""
    from backend.agents.review_agent import review_post

    clean_json = json.dumps(
        {
            "structural_issues": [],
            "brand_alignment": "strong",
            "strengths": ["Strong hook"],
            "improvements": [],
            "revision_notes": "This should be null because no issues",
            "revised_hashtags": [],
            "engagement_scores": {
                "hook_strength": 8,
                "relevance": 8,
                "cta_effectiveness": 8,
                "platform_fit": 8,
                "teaching_depth": 8,
            },
            "engagement_prediction": "high",
        }
    )

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(clean_json)

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_client):
        result = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    # The invariant: revision_notes=None when no structural issues
    assert result["revision_notes"] is None


@pytest.mark.asyncio
async def test_review_post_strips_markdown_fences():
    """LLM response wrapped in ```json``` fences is handled correctly."""
    from backend.agents.review_agent import review_post

    fenced_json = f"```json\n{_VALID_REVIEW_JSON}\n```"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(fenced_json)

    with patch("backend.agents.review_agent.get_genai_client", return_value=mock_client):
        result = await review_post(_SAMPLE_POST, _BRAND_PROFILE)

    assert isinstance(result, dict)
    assert "score" in result
