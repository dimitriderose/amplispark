"""Tests for backend.agents.strategy_agent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

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
    "business_type": "service",
    "tone": "professional, bold",
    "target_audience": "developers aged 25-45",
    "content_themes": ["tutorials", "product updates", "industry news"],
    "visual_style": "modern-tech",
    "colors": ["#2563EB", "#1E40AF"],
}

_VALID_STRATEGY_JSON = json.dumps(
    [
        {
            "day_index": 0,
            "platform": "instagram",
            "pillar": "education",
            "pillar_id": "series_0",
            "content_theme": "3 ways to boost developer productivity",
            "caption_hook": "Most developers waste 2 hours a day on this one thing.",
            "key_message": "Small workflow changes compound into massive time savings.",
            "image_prompt": "Overhead shot of a clean minimal developer desk with a laptop showing code",
            "hashtags": ["devproductivity", "coding", "softwaredev"],
            "derivative_type": "carousel",
            "event_anchor": None,
            "cta_type": "engagement",
            "suggested_time": "6:00 PM",
        },
        {
            "day_index": 1,
            "platform": "linkedin",
            "pillar": "promotion",
            "pillar_id": "series_1",
            "content_theme": "How Test Brand accelerates development cycles",
            "caption_hook": "Ship features 40% faster — here is exactly how.",
            "key_message": "Automation tools eliminate the repetitive tasks slowing your team.",
            "image_prompt": "Clean product dashboard on a dark background with blue gradients",
            "hashtags": ["saas", "devtools", "productivity"],
            "derivative_type": "original",
            "event_anchor": None,
            "cta_type": "conversion",
            "suggested_time": "9:00 AM",
        },
    ]
)

_MOCK_FIRESTORE = MagicMock()
_MOCK_FIRESTORE.get_platform_recommendations = AsyncMock(return_value=None)
_MOCK_FIRESTORE.save_platform_recommendations = AsyncMock(return_value=None)
_MOCK_FIRESTORE.get_posting_frequency = AsyncMock(return_value=None)
_MOCK_FIRESTORE.save_posting_frequency = AsyncMock(return_value=None)
_MOCK_FIRESTORE.get_platform_trends = AsyncMock(return_value=None)
_MOCK_FIRESTORE.save_platform_trends = AsyncMock(return_value=None)


def _make_mock_client_for_strategy():
    """Return a mock genai client that responds to all strategy agent calls."""
    platform_recs = json.dumps(
        [
            {"platform": "instagram", "reason": "High engagement for tech", "priority": 1},
            {"platform": "linkedin", "reason": "B2B audience", "priority": 2},
        ]
    )
    freq_data = json.dumps(
        {
            "instagram": {"posts_per_week": 5, "best_times": ["6:00 PM", "12:00 PM"]},
            "linkedin": {"posts_per_week": 3, "best_times": ["9:00 AM", "12:00 PM"]},
        }
    )
    trends_data = json.dumps(
        {
            "trending_formats": ["Reels", "Carousel"],
            "trending_hooks": ["How I did X", "Stop making this mistake"],
            "algorithm_notes": "Reels get 2x reach",
            "best_posting_times": ["6:00 PM"],
        }
    )
    visual_data = json.dumps(
        {
            "trending_styles": ["editorial", "lo-fi"],
            "format_performance": "Carousel outperforms single image",
            "composition_tips": ["Rule of thirds", "Negative space"],
            "color_trends": "Muted earth tones",
            "scene_suggestions": ["Developer at desk with plants"],
        }
    )
    video_data = json.dumps(
        {
            "trending_formats": ["talking head", "b-roll"],
            "optimal_lengths": "30-60 seconds",
            "hook_patterns": ["Bold statement", "Question"],
            "audio_notes": "Trending sounds boost reach",
        }
    )
    hook_research = "Best hooks for tech: specific numbers, contrarian takes, 'I wish I knew this'"

    call_count = [0]

    def side_effect(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        responses = [
            platform_recs,  # 0: platform recommendations
            trends_data,  # 1: instagram trends
            trends_data,  # 2: linkedin trends (second platform)
            hook_research,  # 3: industry hooks (text, not JSON)
            freq_data,  # 4: posting frequency
            visual_data,  # 5: visual trends
            video_data,  # 6: video trends
            _VALID_STRATEGY_JSON,  # 7: main strategy plan
        ]
        text = responses[idx] if idx < len(responses) else _VALID_STRATEGY_JSON
        return _make_text_response(text)

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = side_effect
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_strategy_returns_days_list():
    """Happy path: valid LLM JSON → returns list of day dicts with required fields."""
    from backend.agents.strategy_agent import run_strategy

    mock_client = _make_mock_client_for_strategy()

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", _MOCK_FIRESTORE),
    ):
        days, trend_summary = await run_strategy(
            brand_id="test-brand-123",
            brand_profile=_BRAND_PROFILE,
            num_days=2,
            platforms=["instagram", "linkedin"],
        )

    assert isinstance(days, list)
    assert len(days) > 0
    for day in days:
        assert "day_index" in day
        assert "platform" in day
        assert "pillar" in day
        assert "content_theme" in day
        assert "caption_hook" in day
        assert "derivative_type" in day


@pytest.mark.asyncio
async def test_run_strategy_returns_trend_summary():
    """run_strategy also returns a trend_summary dict (may be {} on fallback)."""
    from backend.agents.strategy_agent import run_strategy

    mock_client = _make_mock_client_for_strategy()

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", _MOCK_FIRESTORE),
    ):
        days, trend_summary = await run_strategy(
            brand_id="test-brand-trend",
            brand_profile=_BRAND_PROFILE,
            num_days=2,
            platforms=["instagram", "linkedin"],
        )

    # trend_summary is always a dict (may be empty {} on error path)
    assert isinstance(trend_summary, dict)


@pytest.mark.asyncio
async def test_run_strategy_handles_malformed_json():
    """LLM returns non-JSON for strategy step → fallback plan returned, no crash."""
    from backend.agents.strategy_agent import run_strategy

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response("not valid json")

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", _MOCK_FIRESTORE),
    ):
        days, trend_summary = await run_strategy(
            brand_id="test-brand-fallback",
            brand_profile=_BRAND_PROFILE,
            num_days=3,
            platforms=["instagram"],
        )

    # Fallback plan returns num_days briefs
    assert isinstance(days, list)
    assert len(days) == 3
    for day in days:
        assert "day_index" in day
        assert "platform" in day


@pytest.mark.asyncio
async def test_run_strategy_uses_firestore_cache_for_platform_recs():
    """When firestore returns cached platform recommendations, LLM is not called for that step."""
    from backend.agents.strategy_agent import run_strategy

    cached_recs = [
        {"platform": "instagram", "reason": "Cached recommendation", "priority": 1},
    ]
    mock_fs = MagicMock()
    mock_fs.get_platform_recommendations = AsyncMock(return_value=cached_recs)
    mock_fs.save_platform_recommendations = AsyncMock(return_value=None)
    mock_fs.get_posting_frequency = AsyncMock(return_value=None)
    mock_fs.save_posting_frequency = AsyncMock(return_value=None)
    mock_fs.get_platform_trends = AsyncMock(return_value=None)
    mock_fs.save_platform_trends = AsyncMock(return_value=None)

    # Track which calls were made to detect if platform_recs prompt was skipped
    call_payloads = []

    def capture_call(*args, **kwargs):
        call_payloads.append(kwargs.get("contents", args[1] if len(args) > 1 else ""))
        return _make_text_response(_VALID_STRATEGY_JSON)

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = capture_call

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        days, _ = await run_strategy(
            brand_id="test-cached",
            brand_profile=_BRAND_PROFILE,
            num_days=2,
            # No explicit platforms → should use cached recs
        )

    assert isinstance(days, list)
    # Cache was used → no "rank the TOP 5 platforms" call
    for call in call_payloads:
        assert "rank the TOP 5 platforms" not in str(call)


@pytest.mark.asyncio
async def test_research_best_platforms_returns_ranked_list():
    """_research_best_platforms returns a list with platform + reason dicts."""
    from backend.agents.strategy_agent import _research_best_platforms

    platform_recs = json.dumps(
        [
            {"platform": "instagram", "reason": "High engagement for tech", "priority": 1},
            {"platform": "linkedin", "reason": "B2B professional audience", "priority": 2},
            {"platform": "x", "reason": "Real-time tech discussions", "priority": 3},
        ]
    )

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(platform_recs)

    mock_fs = MagicMock()
    mock_fs.get_platform_recommendations = AsyncMock(return_value=None)
    mock_fs.save_platform_recommendations = AsyncMock(return_value=None)

    from backend.platforms import keys as platform_keys

    available = platform_keys()

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_best_platforms(_BRAND_PROFILE, available)

    assert isinstance(result, list)
    assert len(result) > 0
    for item in result:
        assert "platform" in item
        assert "reason" in item


@pytest.mark.asyncio
async def test_research_best_platforms_returns_empty_on_error():
    """_research_best_platforms returns [] when LLM fails."""
    from backend.agents.strategy_agent import _research_best_platforms

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API error")

    mock_fs = MagicMock()
    mock_fs.get_platform_recommendations = AsyncMock(return_value=None)
    mock_fs.save_platform_recommendations = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_best_platforms(_BRAND_PROFILE, ["instagram", "linkedin"])

    assert result == []


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


def test_normalize_day_fills_required_fields():
    """_normalize_day ensures all required fields are present."""
    from backend.agents.strategy_agent import _normalize_day

    partial_day = {
        "day_index": 0,
        "platform": "instagram",
        "pillar": "education",
        "content_theme": "Tips for developers",
    }

    result = _normalize_day(partial_day, 0, _BRAND_PROFILE, ["instagram", "linkedin"])

    for field in [
        "day_index",
        "platform",
        "pillar",
        "pillar_id",
        "content_theme",
        "caption_hook",
        "key_message",
        "image_prompt",
        "hashtags",
        "derivative_type",
        "cta_type",
    ]:
        assert field in result


def test_normalize_day_mastodon_cta_forced_none():
    """Mastodon platform always gets cta_type='none'."""
    from backend.agents.strategy_agent import _normalize_day

    day = {
        "day_index": 0,
        "platform": "mastodon",
        "pillar": "education",
        "content_theme": "Tech tips",
        "cta_type": "conversion",  # should be overridden
    }

    result = _normalize_day(day, 0, _BRAND_PROFILE, ["mastodon"])
    assert result["cta_type"] == "none"


def test_normalize_day_threads_conversion_becomes_engagement():
    """Threads 'conversion' CTA is normalized to 'engagement'."""
    from backend.agents.strategy_agent import _normalize_day

    day = {
        "day_index": 0,
        "platform": "threads",
        "pillar": "education",
        "content_theme": "Tech tips",
        "cta_type": "conversion",
    }

    result = _normalize_day(day, 0, _BRAND_PROFILE, ["threads"])
    assert result["cta_type"] == "engagement"


def test_normalize_day_invalid_derivative_defaults_to_original():
    """Invalid derivative_type is normalized to 'original'."""
    from backend.agents.strategy_agent import _normalize_day

    day = {
        "day_index": 0,
        "platform": "instagram",
        "pillar": "education",
        "content_theme": "Tech tips",
        "derivative_type": "not_a_real_type",
    }

    result = _normalize_day(day, 0, _BRAND_PROFILE, ["instagram"])
    assert result["derivative_type"] == "original"


def test_enforce_group_size_caps_groups():
    """Groups larger than max_group_size get reassigned unique IDs."""
    from backend.agents.strategy_agent import _enforce_group_size

    # 5 days all with same pillar_id — exceeds default max of 3
    days = [
        {
            "day_index": i,
            "pillar_id": "series_0",
            "platform": "instagram",
            "derivative_type": "original",
        }
        for i in range(5)
    ]

    result = _enforce_group_size(days, max_group_size=3)

    # Count days still with original group ID
    group_0_count = sum(1 for d in result if d["pillar_id"] == "series_0")
    assert group_0_count == 3  # Only 3 allowed; rest get new IDs


def test_fallback_plan_returns_correct_length():
    """_fallback_plan returns exactly num_days briefs."""
    from backend.agents.strategy_agent import _fallback_plan

    days = _fallback_plan(5, _BRAND_PROFILE, ["instagram", "linkedin"])
    assert len(days) == 5
    for i, day in enumerate(days):
        assert day["day_index"] == i


def test_fallback_plan_uses_default_platforms_when_none():
    """_fallback_plan defaults to instagram/linkedin/x/facebook when no platforms given."""
    from backend.agents.strategy_agent import _fallback_plan

    days = _fallback_plan(4, _BRAND_PROFILE, None)
    assert len(days) == 4
    platforms_used = {d["platform"] for d in days}
    assert platforms_used.issubset({"instagram", "linkedin", "x", "facebook"})


def test_fallback_day_has_required_fields():
    """_fallback_day returns a day with all required fields populated."""
    from backend.agents.strategy_agent import _fallback_day

    day = _fallback_day(0, _BRAND_PROFILE, ["instagram"])
    for field in [
        "day_index",
        "platform",
        "pillar",
        "pillar_id",
        "content_theme",
        "caption_hook",
        "key_message",
        "image_prompt",
        "hashtags",
        "derivative_type",
        "cta_type",
    ]:
        assert field in day


def test_enforce_group_size_no_change_when_under_limit():
    """Groups within the size limit are left unchanged."""
    from backend.agents.strategy_agent import _enforce_group_size

    days = [
        {
            "day_index": i,
            "pillar_id": f"series_{i % 2}",
            "platform": "instagram",
            "derivative_type": "original",
        }
        for i in range(4)  # 2 groups of 2, max is 3 — no overflow
    ]
    result = _enforce_group_size(days, max_group_size=3)
    group_0 = [d for d in result if d["pillar_id"] == "series_0"]
    group_1 = [d for d in result if d["pillar_id"] == "series_1"]
    assert len(group_0) == 2
    assert len(group_1) == 2


def test_enforce_platform_concentration_below_max_unchanged():
    """Fewer unique platforms than max → list returned unchanged."""
    from backend.agents.strategy_agent import _enforce_platform_concentration

    days = [
        {"day_index": 0, "platform": "instagram"},
        {"day_index": 1, "platform": "linkedin"},
        {"day_index": 2, "platform": "instagram"},
    ]
    result = _enforce_platform_concentration(days, ["instagram", "linkedin"], max_unique=4)
    assert result == days


def test_enforce_platform_concentration_consolidates_extras():
    """More unique platforms than max → least-used reassigned to top platform."""
    from backend.agents.strategy_agent import _enforce_platform_concentration

    days = [
        {"day_index": 0, "platform": "instagram"},
        {"day_index": 1, "platform": "instagram"},
        {"day_index": 2, "platform": "instagram"},
        {"day_index": 3, "platform": "linkedin"},
        {"day_index": 4, "platform": "linkedin"},
        {"day_index": 5, "platform": "x"},
        {"day_index": 6, "platform": "tiktok"},
        {"day_index": 7, "platform": "pinterest"},
        {"day_index": 8, "platform": "threads"},
    ]
    result = _enforce_platform_concentration(
        days, ["instagram", "linkedin", "x", "tiktok", "pinterest", "threads"], max_unique=3
    )
    unique_platforms = {d["platform"] for d in result}
    assert len(unique_platforms) <= 3


def test_normalize_day_strips_hashtag_prefix():
    """Hashtags with # prefix are stripped."""
    from backend.agents.strategy_agent import _normalize_day

    day = {
        "day_index": 0,
        "platform": "instagram",
        "pillar": "education",
        "hashtags": ["#growth", "#saas", "#startup"],
    }
    result = _normalize_day(day, 0, _BRAND_PROFILE, ["instagram"])
    for tag in result["hashtags"]:
        assert not tag.startswith("#")


def test_normalize_day_invalid_platform_uses_fallback():
    """Invalid platform falls back to platforms[index % len(platforms)]."""
    from backend.agents.strategy_agent import _normalize_day

    day = {
        "day_index": 0,
        "platform": "myspace",  # not a real platform
        "pillar": "education",
        "content_theme": "Tips",
    }
    platforms = ["instagram", "linkedin"]
    result = _normalize_day(day, 0, _BRAND_PROFILE, platforms)
    assert result["platform"] in platforms


def test_normalize_day_invalid_pillar_uses_fallback():
    """Invalid pillar falls back to PILLARS[index % len(PILLARS)]."""
    from backend.agents.strategy_agent import _normalize_day

    day = {
        "day_index": 0,
        "platform": "instagram",
        "pillar": "not_a_real_pillar",
        "content_theme": "Tips",
    }
    result = _normalize_day(day, 0, _BRAND_PROFILE, ["instagram"])
    from backend.constants import PILLARS

    assert result["pillar"] in PILLARS


def test_normalize_day_attaches_trend_data():
    """platform_trends_map data is attached to result when platform matches."""
    from backend.agents.strategy_agent import _normalize_day

    day = {"day_index": 0, "platform": "instagram", "pillar": "education"}
    trends_map = {"instagram": {"trending_formats": ["Reels", "Carousel"]}}

    result = _normalize_day(day, 0, _BRAND_PROFILE, ["instagram"], platform_trends_map=trends_map)
    assert "platform_trends" in result
    assert result["platform_trends"]["trending_formats"] == ["Reels", "Carousel"]


def test_normalize_day_attaches_hook_research():
    """hook_research string is attached when provided."""
    from backend.agents.strategy_agent import _normalize_day

    day = {"day_index": 0, "platform": "instagram", "pillar": "education"}
    result = _normalize_day(
        day, 0, _BRAND_PROFILE, ["instagram"], hook_research="Best hooks for tech"
    )
    assert result.get("hook_research") == "Best hooks for tech"


# ---------------------------------------------------------------------------
# _research_posting_frequency — async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_posting_frequency_happy_path():
    """Returns validated frequency dict for provided platforms."""
    from backend.agents.strategy_agent import _research_posting_frequency

    freq_json = json.dumps(
        {
            "instagram": {"posts_per_week": 7, "best_times": ["6:00 PM", "12:00 PM"]},
            "linkedin": {"posts_per_week": 3, "best_times": ["9:00 AM"]},
        }
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(freq_json)

    mock_fs = MagicMock()
    mock_fs.get_posting_frequency = AsyncMock(return_value=None)
    mock_fs.save_posting_frequency = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_posting_frequency(_BRAND_PROFILE, ["instagram", "linkedin"])

    assert "instagram" in result
    assert "linkedin" in result
    assert 1 <= result["instagram"]["posts_per_week"] <= 7


@pytest.mark.asyncio
async def test_research_posting_frequency_uses_cache():
    """Returns cached result when available."""
    from backend.agents.strategy_agent import _research_posting_frequency

    cached = {
        "instagram": {"posts_per_week": 5, "best_times": ["6:00 PM"]},
    }
    mock_client = MagicMock()
    mock_fs = MagicMock()
    mock_fs.get_posting_frequency = AsyncMock(return_value=cached)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_posting_frequency(_BRAND_PROFILE, ["instagram"])

    mock_client.models.generate_content.assert_not_called()
    assert result == cached


@pytest.mark.asyncio
async def test_research_posting_frequency_fallback_on_error():
    """Returns fallback (7 posts/week) when LLM fails."""
    from backend.agents.strategy_agent import _research_posting_frequency

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API error")
    mock_fs = MagicMock()
    mock_fs.get_posting_frequency = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_posting_frequency(_BRAND_PROFILE, ["instagram", "linkedin"])

    # Fallback: 7 posts per week for each platform
    assert result["instagram"]["posts_per_week"] == 7
    assert result["linkedin"]["posts_per_week"] == 7


# ---------------------------------------------------------------------------
# _research_platform_trends — async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_platform_trends_happy_path():
    """Returns parsed trend dict on success."""
    from backend.agents.strategy_agent import _research_platform_trends

    trends = json.dumps(
        {
            "trending_formats": ["Reels", "Carousel"],
            "trending_hooks": ["How I did X"],
            "algorithm_notes": "Reels boosted",
            "best_posting_times": ["6:00 PM"],
            "best_content_format": "Reels",
            "caption_sweet_spot": "150-200 chars",
        }
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(trends)
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=None)
    mock_fs.save_platform_trends = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_platform_trends("instagram", "technology")

    assert result is not None
    assert "trending_formats" in result


@pytest.mark.asyncio
async def test_research_platform_trends_returns_none_on_error():
    """Returns None when LLM fails."""
    from backend.agents.strategy_agent import _research_platform_trends

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API error")
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_platform_trends("instagram", "technology")

    assert result is None


@pytest.mark.asyncio
async def test_research_industry_hooks_empty_industry():
    """Returns empty string when industry is empty."""
    from backend.agents.strategy_agent import _research_industry_hooks

    result = await _research_industry_hooks("", ["instagram"])
    assert result == ""


@pytest.mark.asyncio
async def test_research_industry_hooks_returns_text():
    """Returns hook research text on success."""
    from backend.agents.strategy_agent import _research_industry_hooks

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(
        "Best hooks for tech: specific numbers, contrarian takes"
    )

    with patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client):
        result = await _research_industry_hooks("technology", ["instagram", "linkedin"])

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_research_industry_hooks_returns_empty_on_error():
    """Returns empty string on LLM failure."""
    from backend.agents.strategy_agent import _research_industry_hooks

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API error")

    with patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client):
        result = await _research_industry_hooks("technology", ["instagram"])

    assert result == ""


# ---------------------------------------------------------------------------
# refresh_research — async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_posting_frequency_handles_integer_entry():
    """When platform entry is an integer (not dict), it's treated as posts_per_week."""
    from backend.agents.strategy_agent import _research_posting_frequency

    # LLM returns an integer directly for a platform (edge case)
    freq_json = json.dumps({"instagram": 5, "linkedin": 3})
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(freq_json)
    mock_fs = MagicMock()
    mock_fs.get_posting_frequency = AsyncMock(return_value=None)
    mock_fs.save_posting_frequency = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_posting_frequency(_BRAND_PROFILE, ["instagram", "linkedin"])

    assert result["instagram"]["posts_per_week"] == 5
    assert result["instagram"]["best_times"] == []


@pytest.mark.asyncio
async def test_research_posting_frequency_json_decode_error():
    """JSON decode error returns fallback dict with 7 posts/week."""
    from backend.agents.strategy_agent import _research_posting_frequency

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response("not valid json {{")
    mock_fs = MagicMock()
    mock_fs.get_posting_frequency = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_posting_frequency(_BRAND_PROFILE, ["instagram"])

    assert result["instagram"]["posts_per_week"] == 7


@pytest.mark.asyncio
async def test_research_best_platforms_json_decode_error():
    """JSON decode error in _research_best_platforms returns []."""
    from backend.agents.strategy_agent import _research_best_platforms

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response("not valid json {{")
    mock_fs = MagicMock()
    mock_fs.get_platform_recommendations = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_best_platforms(_BRAND_PROFILE, ["instagram", "linkedin"])

    assert result == []


@pytest.mark.asyncio
async def test_research_platform_trends_json_decode_error():
    """JSON decode error in _research_platform_trends returns None."""
    from backend.agents.strategy_agent import _research_platform_trends

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response("not json {{")
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_platform_trends("instagram", "technology")

    assert result is None


@pytest.mark.asyncio
async def test_research_visual_trends_happy_path():
    """_research_visual_trends returns parsed dict on success."""
    from backend.agents.strategy_agent import _research_visual_trends

    visual_json = json.dumps(
        {
            "trending_styles": ["editorial", "lo-fi"],
            "format_performance": "Carousel wins",
            "composition_tips": ["Rule of thirds"],
            "color_trends": "Earth tones",
            "scene_suggestions": ["Developer at desk"],
        }
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(visual_json)
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=None)
    mock_fs.save_platform_trends = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_visual_trends("instagram", "technology")

    assert result is not None
    assert "trending_styles" in result


@pytest.mark.asyncio
async def test_research_visual_trends_returns_none_on_error():
    """_research_visual_trends returns None when LLM fails."""
    from backend.agents.strategy_agent import _research_visual_trends

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API error")
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_visual_trends("instagram", "technology")

    assert result is None


@pytest.mark.asyncio
async def test_research_video_trends_happy_path():
    """_research_video_trends returns parsed dict on success."""
    from backend.agents.strategy_agent import _research_video_trends

    video_json = json.dumps(
        {
            "trending_formats": ["talking head", "b-roll"],
            "optimal_lengths": "30-60 seconds",
            "hook_patterns": ["Bold statement"],
            "audio_notes": "Trending sounds boost reach",
        }
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(video_json)
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=None)
    mock_fs.save_platform_trends = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_video_trends("instagram", "technology")

    assert result is not None
    assert "trending_formats" in result


@pytest.mark.asyncio
async def test_research_video_trends_uses_cache():
    """_research_video_trends returns cached result when available."""
    from backend.agents.strategy_agent import _research_video_trends

    cached = {"trending_formats": ["cached format"], "optimal_lengths": "30s"}
    mock_client = MagicMock()
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=cached)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_video_trends("instagram", "technology")

    mock_client.models.generate_content.assert_not_called()
    assert result == cached


@pytest.mark.asyncio
async def test_research_platform_trends_uses_cache():
    """_research_platform_trends returns cached result when available."""
    from backend.agents.strategy_agent import _research_platform_trends

    cached = {"trending_formats": ["Reels"], "algorithm_notes": "cached"}
    mock_client = MagicMock()
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=cached)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await _research_platform_trends("instagram", "technology")

    mock_client.models.generate_content.assert_not_called()
    assert result == cached


@pytest.mark.asyncio
async def test_refresh_research_returns_trend_summary():
    """refresh_research returns a dict with researched_at, platform_trends, etc."""
    from backend.agents.strategy_agent import refresh_research

    trends = json.dumps(
        {
            "trending_formats": ["Reels"],
            "trending_hooks": [],
            "algorithm_notes": "",
            "best_posting_times": [],
        }
    )
    visual = json.dumps(
        {
            "trending_styles": ["editorial"],
            "format_performance": "Carousel wins",
            "composition_tips": [],
            "color_trends": "",
            "scene_suggestions": [],
        }
    )
    video = json.dumps(
        {
            "trending_formats": ["talking head"],
            "optimal_lengths": "30-60s",
            "hook_patterns": [],
            "audio_notes": "",
        }
    )

    call_count = [0]

    def llm_side_effect(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        responses = [trends, visual, video]
        return _make_text_response(responses[min(idx, len(responses) - 1)])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = llm_side_effect
    mock_fs = MagicMock()
    mock_fs.get_platform_trends = AsyncMock(return_value=None)
    mock_fs.save_platform_trends = AsyncMock(return_value=None)

    with (
        patch("backend.agents.strategy_agent.get_genai_client", return_value=mock_client),
        patch("backend.agents.strategy_agent.firestore_client", mock_fs),
    ):
        result = await refresh_research(
            platforms=["instagram"],
            industry="technology",
            primary_platform="instagram",
        )

    assert isinstance(result, dict)
    assert "researched_at" in result
    assert "platform_trends" in result
