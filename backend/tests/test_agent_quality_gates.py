"""Tests for backend.agents.quality_gates."""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


_BRAND_PROFILE = {
    "business_name": "Test Brand",
    "industry": "technology",
    "tone": "professional",
    "target_audience": "developers",
    "caption_style_directive": "Short punchy sentences.",
}

_DAY_BRIEF = {
    "pillar": "education",
    "content_theme": "Developer productivity tips",
    "cta_type": "engagement",
}


# ---------------------------------------------------------------------------
# _check_quality_violations — pure function
# ---------------------------------------------------------------------------


def test_check_quality_violations_no_violations():
    """Clean caption → empty violations list."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "Three habits that doubled my code review speed.\n\nMost reviews take 45 minutes. Mine take 12."
    violations = _check_quality_violations(caption, "instagram", "original")
    assert violations == []


def test_check_quality_violations_banned_hook():
    """Caption starting with 'Are you' → BANNED_HOOK violation."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "Are you struggling with slow code reviews? Here is the fix."
    violations = _check_quality_violations(caption, "instagram", "original")
    assert any("BANNED_HOOK" in v for v in violations)


def test_check_quality_violations_exclamation_spam():
    """More than one exclamation mark → EXCLAMATION_SPAM."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "Amazing results! Try this now! You will love it!"
    violations = _check_quality_violations(caption, "instagram", "original")
    assert any("EXCLAMATION_SPAM" in v for v in violations)


def test_check_quality_violations_vague_social_proof():
    """'many businesses' → VAGUE_SOCIAL_PROOF."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "Many businesses have seen incredible results using this approach."
    violations = _check_quality_violations(caption, "instagram", "original")
    assert any("VAGUE_SOCIAL_PROOF" in v for v in violations)


def test_check_quality_violations_pinterest_skips_hook_check():
    """Pinterest skips the banned hook check (hook check is platform-excluded)."""
    from backend.agents.quality_gates import _check_quality_violations

    # Even a banned hook opener should not trigger for pinterest
    caption = "Are you looking for home decor ideas? Here are 5 styles."
    violations = _check_quality_violations(caption, "pinterest", "pin")
    # No BANNED_HOOK for pinterest
    assert not any("BANNED_HOOK" in v for v in violations)


# ---------------------------------------------------------------------------
# _quality_retry — async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_retry_returns_original_when_no_violations():
    """No violations → returns original caption, LLM not called."""
    from backend.agents.quality_gates import _quality_retry

    caption = "Three habits that doubled my code review speed."
    mock_client = MagicMock()

    with patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client):
        result = await _quality_retry(caption, "instagram", "original")

    mock_client.models.generate_content.assert_not_called()
    assert result == caption


@pytest.mark.asyncio
async def test_quality_retry_calls_llm_on_violations():
    """Violations detected → LLM is called for retry."""
    from backend.agents.quality_gates import _quality_retry

    # This caption has a banned hook
    bad_caption = "Are you struggling to grow your business? Here is the answer."
    improved = "Three tactics that actually move the needle on growth."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(improved)

    with patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client):
        result = await _quality_retry(bad_caption, "instagram", "original")

    mock_client.models.generate_content.assert_called_once()
    # Either improved caption or original (if retry didn't help)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_quality_retry_keeps_original_when_retry_doesnt_improve():
    """If retry produces same/worse violations, original is kept."""
    from backend.agents.quality_gates import _quality_retry

    # Has exclamation spam
    original = "Amazing! Try this now! You will love it!"
    # Retry also has spam
    still_bad = "Incredible! Do this today! It works!"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(still_bad)

    with patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client):
        result = await _quality_retry(original, "instagram", "original")

    # Should keep original when retry doesn't improve
    assert result == original


# ---------------------------------------------------------------------------
# _review_gate — async, mocks review_post
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_gate_passes_on_high_score():
    """Score >= 7 → caption passes through unchanged."""
    from backend.agents.quality_gates import _review_gate

    caption = "Three habits that doubled my code review speed."
    hashtags = ["coding", "devproductivity"]

    good_review = {
        "score": 8,
        "brand_alignment": "strong",
        "strengths": ["Specific hook", "Clear value"],
        "improvements": [],
        "approved": True,
        "revision_notes": None,
        "revised_hashtags": None,
        "structural_issues": [],
        "engagement_scores": {
            "hook_strength": 8,
            "relevance": 8,
            "cta_effectiveness": 7,
            "platform_fit": 8,
            "teaching_depth": 7,
        },
        "engagement_prediction": "high",
    }

    with patch("backend.agents.quality_gates.review_post", return_value=good_review):
        out_caption, out_hashtags, review = await _review_gate(
            caption, hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    assert out_caption == caption
    assert out_hashtags == hashtags
    assert review is not None


@pytest.mark.asyncio
async def test_review_gate_returns_original_on_exception():
    """If review_post raises, original caption is returned gracefully."""
    from backend.agents.quality_gates import _review_gate

    caption = "Some caption here."
    hashtags = ["test"]

    with patch("backend.agents.quality_gates.review_post", side_effect=RuntimeError("fail")):
        out_caption, out_hashtags, review = await _review_gate(
            caption, hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    assert out_caption == caption
    assert out_hashtags == hashtags
    assert review is None


# ---------------------------------------------------------------------------
# _review_gate low-score paths — triggers rewrite logic (lines 160-420)
# ---------------------------------------------------------------------------


def _low_review(score: int = 5, revision_notes=None, revised_hashtags=None) -> dict:
    """Build a low-scoring review dict for _review_gate tests."""
    return {
        "score": score,
        "brand_alignment": "weak",
        "strengths": [],
        "improvements": ["Improve the hook"],
        "approved": False,
        "revision_notes": revision_notes or "Make the hook more specific and actionable.",
        "revised_hashtags": revised_hashtags,
        "structural_issues": [],
        "engagement_scores": {
            "hook_strength": 4,
            "relevance": 5,
            "cta_effectiveness": 4,
            "platform_fit": 5,
            "teaching_depth": 3,
        },
        "engagement_prediction": "low",
    }


def _good_review(score: int = 8, revised_hashtags=None) -> dict:
    return {
        "score": score,
        "brand_alignment": "strong",
        "strengths": ["Improved hook"],
        "improvements": [],
        "approved": True,
        "revision_notes": None,
        "revised_hashtags": revised_hashtags,
        "structural_issues": [],
        "engagement_scores": {
            "hook_strength": 8,
            "relevance": 8,
            "cta_effectiveness": 7,
            "platform_fit": 8,
            "teaching_depth": 7,
        },
        "engagement_prediction": "high",
    }


@pytest.mark.asyncio
async def test_review_gate_rewrites_on_low_score_and_passes():
    """Score < 7 with revision_notes → LLM rewrite → re-review passes → returns rewritten."""
    from backend.agents.quality_gates import _review_gate

    original = "Are you struggling to grow? Let me help you out here."
    rewritten = "Three specific tactics that cut our sales cycle by 40%."
    hashtags = ["growth", "sales"]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(rewritten)

    # First call: low score; second call (re-review): passes
    review_side_effects = [_low_review(score=5), _good_review(score=8)]

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.quality_gates.review_post",
            side_effect=review_side_effects,
        ),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            original, hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    # Rewritten caption was accepted after re-review
    assert out_caption == rewritten
    assert review is not None
    assert review["score"] == 8


@pytest.mark.asyncio
async def test_review_gate_returns_original_when_no_revision_notes():
    """Score < 7 but revision_notes is None/empty → keep original without LLM call."""
    from backend.agents.quality_gates import _review_gate

    caption = "Some weak caption."
    hashtags = ["test"]

    low_review_no_notes = _low_review(score=4, revision_notes=None)
    # Override revision_notes to be falsy
    low_review_no_notes["revision_notes"] = None

    mock_client = MagicMock()

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch("backend.agents.quality_gates.review_post", return_value=low_review_no_notes),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            caption, hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    # No rewrite should be attempted
    mock_client.models.generate_content.assert_not_called()
    assert out_caption == caption


@pytest.mark.asyncio
async def test_review_gate_attempt2_when_rewrite_still_fails():
    """Rewrite attempt 1 still scores < 7 → attempt 2 triggers stronger rewrite."""
    from backend.agents.quality_gates import _review_gate

    original = "Are you ready to change your business? Let's dive in."
    attempt1 = "Most founders miss this one financial mistake every quarter."
    attempt2 = "This cash flow mistake costs founders $12k a year on average."
    hashtags = ["finance", "startup"]

    call_count = [0]

    def llm_side_effect(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        texts = [attempt1, attempt2]
        return _make_text_response(texts[min(idx, len(texts) - 1)])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = llm_side_effect

    # First review: low; re-review after attempt1: still low; re-review after attempt2: passes
    review_side_effects = [
        _low_review(score=5),
        _low_review(score=6),  # attempt 1 re-review still fails
        _good_review(score=8),  # attempt 2 re-review passes
    ]

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch("backend.agents.quality_gates.review_post", side_effect=review_side_effects),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            original, hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    # Second attempt should have been triggered — LLM called twice
    assert mock_client.models.generate_content.call_count == 2
    assert out_caption == attempt2


@pytest.mark.asyncio
async def test_review_gate_exhausted_returns_best():
    """Both attempts fail → returns whichever attempt had the higher score."""
    from backend.agents.quality_gates import _review_gate

    original = "Weak caption that needs work."
    attempt1 = "Slightly better caption still below threshold."
    attempt2 = "Another attempt that also fails review."
    hashtags = ["test"]

    call_count = [0]

    def llm_side_effect(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return _make_text_response([attempt1, attempt2][min(idx, 1)])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = llm_side_effect

    # All three reviews fail: original, attempt1, attempt2
    review_side_effects = [
        _low_review(score=5),
        _low_review(score=6),  # attempt1 re-review
        _low_review(score=4),  # attempt2 re-review — worse than attempt1
    ]

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch("backend.agents.quality_gates.review_post", side_effect=review_side_effects),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            original, hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    # Attempt1 scored higher (6 vs 4), so it should be returned
    assert out_caption == attempt1


@pytest.mark.asyncio
async def test_review_gate_carousel_rejects_rewrite_losing_slides():
    """Carousel rewrite that loses slide structure is rejected; original returned."""
    from backend.agents.quality_gates import _review_gate

    original = (
        "Slide 1: Hook — Three steps that doubled our pipeline\n"
        "Slide 2: Step one — Identify high-intent leads\n"
        "Slide 3: Step two — Personalize the outreach"
    )
    # Rewrite that loses slide structure
    bad_rewrite = "Just a plain paragraph without any slide labels at all."
    hashtags = ["sales"]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(bad_rewrite)

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch("backend.agents.quality_gates.review_post", return_value=_low_review(score=5)),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            original, hashtags, "instagram", "carousel", _BRAND_PROFILE, _DAY_BRIEF
        )

    # Structural safety net should keep original
    assert out_caption == original


@pytest.mark.asyncio
async def test_review_gate_updates_hashtags_from_revised_hashtags():
    """When review provides revised_hashtags, they are adopted after a successful rewrite."""
    from backend.agents.quality_gates import _review_gate

    original = "Weak hook opener."
    rewritten = "Two specific actions that increased our close rate by 30%."
    original_hashtags = ["sales"]
    revised_tags = ["closingdeals", "salesstrategy", "b2b"]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(rewritten)

    review_side_effects = [
        _low_review(score=5, revised_hashtags=revised_tags),
        _good_review(score=8),
    ]

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch("backend.agents.quality_gates.review_post", side_effect=review_side_effects),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            original, original_hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    # revised_hashtags should be applied
    assert set(out_hashtags).issubset(set(revised_tags) | set(original_hashtags))


@pytest.mark.asyncio
async def test_review_gate_list_revision_notes_joined():
    """revision_notes as a list (not string) is joined into prompt correctly."""
    from backend.agents.quality_gates import _review_gate

    caption = "Are you a founder struggling to scale?"
    rewritten = "Founders who scaled past $1M all shared this one habit."
    hashtags = ["startup"]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(rewritten)

    # revision_notes as a list
    low_review = _low_review(
        score=4,
        revision_notes=["Remove the banned hook", "Be more specific", "Add a data point"],
    )

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.quality_gates.review_post",
            side_effect=[low_review, _good_review(score=8)],
        ),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            caption, hashtags, "instagram", "original", _BRAND_PROFILE, _DAY_BRIEF
        )

    # LLM was called (list revision_notes didn't break anything)
    mock_client.models.generate_content.assert_called_once()
    assert isinstance(out_caption, str)


@pytest.mark.asyncio
async def test_review_gate_with_storytelling_profile():
    """social_proof_tier from brand profile is applied to rewrite constraints."""
    from backend.agents.quality_gates import _review_gate

    brand_with_story = {
        **_BRAND_PROFILE,
        "storytelling_strategy": {
            "social_proof_tier": "strong_profile",
        },
    }
    day_brief_with_cta = {
        **_DAY_BRIEF,
        "cta_type": "conversion",
    }

    caption = "Why most businesses fail at content marketing."
    rewritten = "The content strategy that took us from 0 to 10k followers in 90 days."
    hashtags = ["contentmarketing"]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(rewritten)

    with (
        patch("backend.agents.quality_gates.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.quality_gates.review_post",
            side_effect=[_low_review(score=5), _good_review(score=9)],
        ),
    ):
        out_caption, out_hashtags, review = await _review_gate(
            caption, hashtags, "instagram", "original", brand_with_story, day_brief_with_cta
        )

    assert isinstance(out_caption, str)


# ---------------------------------------------------------------------------
# _check_quality_violations — additional edge cases
# ---------------------------------------------------------------------------


def test_check_quality_violations_discourse_marker_prefix():
    """'But what if' → discourse marker stripped → 'What if' → BANNED_HOOK."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "But what if you could double revenue without more clients?"
    violations = _check_quality_violations(caption, "instagram", "original")
    assert any("BANNED_HOOK" in v for v in violations)


def test_check_quality_violations_carousel_uses_slide1_first_line():
    """Carousel: banned hook inside Slide 1 is detected."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "Slide 1: Are you struggling to grow your business?\nSlide 2: Here is the fix."
    violations = _check_quality_violations(caption, "instagram", "carousel")
    assert any("BANNED_HOOK" in v for v in violations)


def test_check_quality_violations_single_exclamation_ok():
    """A single exclamation mark does NOT trigger EXCLAMATION_SPAM."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "Three tactics that grew our pipeline by 60%! Start today."
    violations = _check_quality_violations(caption, "instagram", "original")
    assert not any("EXCLAMATION_SPAM" in v for v in violations)


def test_check_quality_violations_numerous_clients():
    """'numerous clients' matches VAGUE_SOCIAL_PROOF."""
    from backend.agents.quality_gates import _check_quality_violations

    caption = "Numerous clients have used this approach to scale."
    violations = _check_quality_violations(caption, "linkedin", "original")
    assert any("VAGUE_SOCIAL_PROOF" in v for v in violations)
