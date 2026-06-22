"""Unit tests for backend/agents/voice_coach.py — pure builder functions."""

from backend.agents.voice_coach import (
    _build_calendar_block,
    _build_cta_block,
    _build_pillar_block,
    _build_platform_block,
    _build_tier_block,
    build_coaching_prompt,
)

# ---------------------------------------------------------------------------
# _build_tier_block tests
# ---------------------------------------------------------------------------


def test_build_tier_block_data_rich():
    """data_rich tier references years and clients in the block."""
    result = _build_tier_block("data_rich", years=10, clients=500)
    assert "10" in result
    assert "500" in result
    assert "Proven" in result or "data_rich" in result.lower() or "SOCIAL PROOF TIER" in result


def test_build_tier_block_partial_data_with_years():
    """partial_data tier with years shows 'years in business'."""
    result = _build_tier_block("partial_data", years=5, clients=None)
    assert "5" in result
    assert "PROCESS AUTHORITY" in result or "partial" in result.lower() or "Established" in result


def test_build_tier_block_partial_data_with_clients():
    """partial_data tier with only clients shows client count."""
    result = _build_tier_block("partial_data", years=None, clients=200)
    assert "200" in result


def test_build_tier_block_thin_profile():
    """thin_profile tier emphasizes depth of knowledge."""
    result = _build_tier_block("thin_profile", years=None, clients=None)
    assert "DEPTH OF KNOWLEDGE" in result or "Building Phase" in result


# ---------------------------------------------------------------------------
# _build_pillar_block tests
# ---------------------------------------------------------------------------


def test_build_pillar_block_contains_pillar_names():
    """Pillar block contains key content pillar names."""
    result = _build_pillar_block("data_rich")
    assert "Education" in result or "education" in result.lower()
    assert "Promotion" in result or "promotion" in result.lower()


def test_build_pillar_block_thin_profile_caps_promotion():
    """thin_profile tier caps promotion posts at 1."""
    result = _build_pillar_block("thin_profile")
    assert "1" in result  # "capped at 1"
    assert "Education" in result or "education" in result.lower()


# ---------------------------------------------------------------------------
# _build_cta_block tests
# ---------------------------------------------------------------------------


def test_build_cta_block_thin_profile_limits_conversion():
    """thin_profile CTA block prefers engagement CTAs over conversion."""
    result = _build_cta_block("thin_profile")
    assert "engagement" in result.lower() or "engagement CTAs" in result


def test_build_cta_block_data_rich_allows_rotation():
    """data_rich CTA block allows rotating between engagement and conversion."""
    result = _build_cta_block("data_rich")
    assert "engagement" in result.lower()
    assert "conversion" in result.lower()


# ---------------------------------------------------------------------------
# _build_platform_block tests
# ---------------------------------------------------------------------------


def test_build_platform_block_with_connected_platforms():
    """Returns block containing connected platform names."""
    result = _build_platform_block(["instagram", "linkedin"])
    assert "instagram" in result.lower() or "Instagram" in result
    assert "linkedin" in result.lower() or "LinkedIn" in result


def test_build_platform_block_empty_falls_back_to_defaults():
    """Empty list falls back to default platforms."""
    result = _build_platform_block([])
    # Should contain at least one default platform
    assert any(p in result.lower() for p in ["instagram", "linkedin", "facebook", "x"])


# ---------------------------------------------------------------------------
# _build_calendar_block tests
# ---------------------------------------------------------------------------


def test_build_calendar_block_no_plan():
    """No plan returns message about no calendar."""
    result = _build_calendar_block(None, None)
    assert "No content calendar" in result or "CONTENT CALENDAR" in result


def test_build_calendar_block_empty_days():
    """Plan with no days returns appropriate message."""
    result = _build_calendar_block({"days": []}, None)
    assert "no scheduled days" in result or "CONTENT CALENDAR" in result


def test_build_calendar_block_with_days():
    """Plan with days returns summary containing platform and day info."""
    plan = {
        "days": [
            {
                "day_index": 0,
                "platform": "instagram",
                "pillar": "education",
                "content_theme": "Marketing tips",
                "caption_hook": "Test hook",
                "cta_type": "engagement",
                "derivative_type": "original",
            }
        ]
    }
    result = _build_calendar_block(plan, [])
    assert "instagram" in result.lower() or "Instagram" in result
    assert "Marketing tips" in result


def test_build_calendar_block_caps_length():
    """Very long calendar blocks are truncated to prevent prompt bloat."""
    many_days = [
        {
            "day_index": i,
            "platform": "instagram",
            "pillar": "education",
            "content_theme": f"Theme {i} — " + "x" * 200,
            "caption_hook": "Hook",
            "cta_type": "engagement",
            "derivative_type": "original",
        }
        for i in range(50)
    ]
    result = _build_calendar_block({"days": many_days}, [])
    assert len(result) <= 3100  # ~3000 chars + slight buffer for the truncation suffix


# ---------------------------------------------------------------------------
# build_coaching_prompt integration test
# ---------------------------------------------------------------------------


def test_build_coaching_prompt_contains_brand_name():
    """Full coaching prompt includes the brand name."""
    brand = {
        "business_name": "Acme Consulting",
        "tone": "professional",
        "industry": "consulting",
    }
    result = build_coaching_prompt(brand)
    assert "Acme Consulting" in result


def test_build_coaching_prompt_contains_role_section():
    """Full coaching prompt includes the YOUR ROLE section."""
    brand = {"business_name": "Test Brand", "tone": "friendly"}
    result = build_coaching_prompt(brand)
    assert "YOUR ROLE" in result


def test_build_coaching_prompt_contains_end_session_marker():
    """Full coaching prompt instructs the model to output [END_SESSION]."""
    brand = {"business_name": "Test Brand"}
    result = build_coaching_prompt(brand)
    assert "[END_SESSION]" in result


def test_build_coaching_prompt_with_plan_and_posts():
    """build_coaching_prompt accepts plan and posts without crashing."""
    brand = {"business_name": "Brand With Plan", "tone": "casual"}
    plan = {
        "days": [
            {
                "day_index": 0,
                "platform": "linkedin",
                "pillar": "education",
                "content_theme": "Growth hacking",
                "caption_hook": "Hook",
                "cta_type": "engagement",
                "derivative_type": "original",
            }
        ]
    }
    posts = [
        {
            "day_index": 0,
            "platform": "linkedin",
            "status": "complete",
            "review": {"score": 8, "approved": True, "improvements": ["Sharpen the hook"]},
        }
    ]
    result = build_coaching_prompt(brand, plan=plan, posts=posts)
    assert "Brand With Plan" in result
    assert "linkedin" in result.lower() or "LinkedIn" in result
