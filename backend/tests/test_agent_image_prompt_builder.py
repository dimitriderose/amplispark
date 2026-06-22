"""Tests for backend.agents.image_prompt_builder pure functions."""

_SAMPLE_BRAND_PROFILE = {
    "business_name": "Test Brand",
    "industry": "technology",
    "tone": "professional, bold",
    "colors": ["#2563EB", "#1E40AF", "#DBEAFE"],
    "visual_style": "modern-tech",
    "image_style_directive": "clean, minimal, modern tech with blue accents, sharp focus",
    "target_audience": "developers aged 25-45",
}


def test_get_image_style_returns_dict():
    """_get_image_style returns a dict with keyword and directives keys."""
    from backend.agents.image_prompt_builder import _get_image_style

    result = _get_image_style("editorial")
    assert isinstance(result, dict)
    assert "keyword" in result
    assert "directives" in result


def test_get_image_style_fallback_to_photorealistic():
    """Unknown style key falls back to 'photorealistic'."""
    from backend.agents.image_prompt_builder import _get_image_style

    result = _get_image_style("nonexistent_style_xyz")
    assert result["keyword"] == "professional photograph"


def test_get_image_style_none_fallback():
    """None style key falls back to 'photorealistic'."""
    from backend.agents.image_prompt_builder import _get_image_style

    result = _get_image_style(None)
    assert "keyword" in result
    assert result["keyword"] == "professional photograph"


def test_build_image_prompt_includes_platform():
    """Built prompt contains the platform name."""
    from backend.agents.image_prompt_builder import _build_image_prompt, _get_image_style

    style = _get_image_style("photorealistic")
    prompt = _build_image_prompt(
        platform="instagram",
        style=style,
        enhanced_image_prompt="Developer at a clean desk with laptop",
        image_style_directive="minimal, modern",
        color_hint="Brand colors: deep blue and indigo.",
        style_ref_block="",
        aspect="1:1",
        derivative_type="original",
    )

    assert "instagram" in prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_build_image_prompt_includes_subject():
    """The enhanced_image_prompt subject appears in the built prompt."""
    from backend.agents.image_prompt_builder import _build_image_prompt, _get_image_style

    style = _get_image_style("photorealistic")
    subject = "A barista preparing specialty coffee"
    prompt = _build_image_prompt(
        platform="instagram",
        style=style,
        enhanced_image_prompt=subject,
        image_style_directive="warm, organic",
        color_hint="",
        style_ref_block="",
        aspect="1:1",
    )

    assert subject in prompt


def test_build_image_prompt_includes_directives():
    """Style directive text appears in the built prompt."""
    from backend.agents.image_prompt_builder import _build_image_prompt, _get_image_style

    style = _get_image_style("photorealistic")
    directive = "unique style directive for testing"
    prompt = _build_image_prompt(
        platform="instagram",
        style=style,
        enhanced_image_prompt="Subject matter",
        image_style_directive=directive,
        color_hint="",
        style_ref_block="",
        aspect="4:5",
    )

    assert directive in prompt


def test_build_image_prompt_no_text_prohibition():
    """All prompts include the no-text prohibition block."""
    from backend.agents.image_prompt_builder import _build_image_prompt, _get_image_style

    style = _get_image_style("photorealistic")
    prompt = _build_image_prompt(
        platform="linkedin",
        style=style,
        enhanced_image_prompt="Professional context",
        image_style_directive="corporate",
        color_hint="",
        style_ref_block="",
        aspect="1.91:1",
    )

    assert "No AI-generated text" in prompt or "ABSOLUTE PROHIBITIONS" in prompt


def test_build_carousel_slide_prompt_includes_slide_number():
    """Carousel slide prompt mentions the slide number."""
    from backend.agents.image_prompt_builder import _build_carousel_slide_prompt, _get_image_style

    style = _get_image_style("photorealistic")
    prompt = _build_carousel_slide_prompt(
        platform="instagram",
        style=style,
        slide_num=3,
        slide_visual_hint="Close-up of hands on keyboard",
        color_hint="",
        style_ref_block="",
        slide_text="Learn this technique today",
    )

    assert "3" in prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_build_carousel_slide_prompt_includes_visual_hint():
    """Carousel slide prompt contains the visual hint."""
    from backend.agents.image_prompt_builder import _build_carousel_slide_prompt, _get_image_style

    style = _get_image_style("editorial")
    hint = "Wide shot of a modern co-working space"
    prompt = _build_carousel_slide_prompt(
        platform="instagram",
        style=style,
        slide_num=2,
        slide_visual_hint=hint,
        color_hint="",
        style_ref_block="",
    )

    assert hint in prompt


def test_infer_slide_mood_returns_string():
    """_infer_slide_mood returns a non-empty string for any text."""
    from backend.agents.image_prompt_builder import _infer_slide_mood

    result = _infer_slide_mood("Learn how to master this skill and achieve success")
    assert isinstance(result, str)
    assert len(result) > 0


def test_infer_slide_mood_default_for_no_keywords():
    """Text with no recognized keywords returns the default mood."""
    from backend.agents.image_prompt_builder import _infer_slide_mood

    result = _infer_slide_mood("xyz qrs abc def")
    assert result == "professional and approachable"
