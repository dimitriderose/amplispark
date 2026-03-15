"""Image prompt construction for single images and carousel slides."""

import logging
import re

from backend.platforms import get as get_platform

logger = logging.getLogger(__name__)


# ── Adaptive Image Style System (35 styles, 6 categories) ────────────────────

_IMAGE_STYLE_MAP: dict[str, dict[str, str]] = {
    # ── Photography Styles ──
    "photorealistic":   {"keyword": "professional photograph",     "directives": "Shot on 50mm f/1.8 lens, sharp focus, natural lighting at 5500K, realistic textures, authentic composition. Professional but not stock-photo sterile"},
    "editorial":        {"keyword": "editorial photograph",         "directives": "Magazine-quality framing, soft diffused light, muted earthy tones, shallow DOF at f/2.8, aspirational but understated. Focus: fashion, beauty, lifestyle"},
    "documentary":      {"keyword": "documentary photograph",      "directives": "35mm lens, available light only, candid moments, honest and raw, photojournalism feel, slight grain ISO 800+"},
    "cinematic":        {"keyword": "cinematic still photograph",  "directives": "Dramatic chiaroscuro lighting, anamorphic lens feel (wide 2.39:1 crop energy), film grain, teal-orange color grading, deep shadows, narrative tension. Focus: storytelling, drama, atmosphere"},
    "food-photo":       {"keyword": "food photograph",             "directives": "Shot at 45° or overhead, 85mm macro lens, natural window light at 4000K warm, styled props, appetizing colors, restaurant-quality plating, shallow DOF f/2.8"},
    "product":          {"keyword": "product photograph",          "directives": "100mm macro lens, clean seamless background, 3-point studio lighting (key + fill + rim), sharp detail at f/8, hero-shot composition, material textures visible"},
    "lifestyle":        {"keyword": "lifestyle photograph",        "directives": "35mm f/1.4 lens, people in natural settings, warm golden-hour light at 3200K, candid feel, authentic moments, bokeh background, relatable context"},
    "lo-fi":            {"keyword": "lo-fi aesthetic photograph",   "directives": "Intentional grain, slightly desaturated, analog camera feel, imperfect framing, retro-tech warmth. Trending 2025-2026"},

    # ── Illustration & Art Styles ──
    "illustration":     {"keyword": "digital illustration",        "directives": "Clean vector-like art, bold colors, clear shapes, modern graphic feel"},
    "hand-drawn":       {"keyword": "hand-drawn illustration",     "directives": "Visible brush/pen strokes, imperfect organic lines, warmth, personality, scrapbook-like accents. Anti-AI aesthetic trending 2026"},
    "anime":            {"keyword": "anime-style illustration",    "directives": "Japanese animation aesthetic, vibrant colors, expressive characters, cel-shaded look, clean linework, dynamic poses"},
    "cartoon":          {"keyword": "cartoon illustration",        "directives": "Exaggerated proportions, bold outlines, flat bright colors, playful expressions, comic-book energy, fun and accessible"},
    "watercolor":       {"keyword": "watercolor painting",         "directives": "Soft color bleeds, organic edges, translucent layers, dreamy and artistic, gentle and warm palette"},
    "pixel-art":        {"keyword": "pixel art",                   "directives": "Grid-based retro game aesthetic, limited color palette, nostalgic 8-bit/16-bit feel, clean pixel placement. Revival trend 2026"},
    "risograph":        {"keyword": "risograph-style print",       "directives": "Limited vivid color palette (2-3 colors), halftone dots, charming imperfections, dust/grain, overprint color mixing. Trending 2026"},

    # ── 3D & Futuristic ──
    "3d-render":        {"keyword": "3D render",                   "directives": "Clean geometry, soft global illumination, glass/metal materials, subtle reflections, modern product-visualization feel"},
    "futuristic":       {"keyword": "sci-fi concept art",          "directives": "Neon accents, holographic elements, dark backgrounds with glowing highlights, cyberpunk/utopian atmosphere, sleek surfaces"},
    "retro-futurism":   {"keyword": "retro-futuristic design",    "directives": "Chrome finishes, neon palette, 1980s sci-fi aesthetic, synthwave colors, speculative optimism. Trending 2026"},

    # ── Graphic Design Styles ──
    "bold-minimal":     {"keyword": "bold minimalist graphic",     "directives": "Strong single focal point, oversized typography, confident color choice, maximum whitespace, high impact. Trending 2026"},
    "maximalist":       {"keyword": "maximalist collage",          "directives": "Layered typography, bold colors, dense imagery, mixed textures, eclectic energy, visual abundance. Anti-minimalism trend 2026"},
    "neo-brutalist":    {"keyword": "neo-brutalist graphic",       "directives": "Raw layout, oversized type, black borders, intentional roughness, high contrast, prioritize clarity over refinement. Trending 2026"},
    "mixed-media":      {"keyword": "mixed-media collage",         "directives": "Layered photography + illustration + typography + texture, dimensional richness, handmade cutout feel. Top trend 2026"},
    "flat-design":      {"keyword": "flat design graphic",          "directives": "Solid colors, no gradients or shadows, geometric shapes, clean sans-serif type, modern UI-inspired aesthetic, accessible and clean"},
    "glitch":           {"keyword": "glitch art",                  "directives": "Controlled digital distortion, RGB shift, scan lines, data corruption aesthetic, cyberpunk energy"},

    # ── Mood/Aesthetic Styles ──
    "cozy":             {"keyword": "cozy aesthetic photograph",   "directives": "Warm tones, soft textures (knit, wood, candles), comfort-focused, hygge mood, gentle natural light. Trending 2025-2026"},
    "nature":           {"keyword": "nature-inspired photograph",  "directives": "Organic shapes, earth tones, botanical elements, natural textures, atmospheric outdoor lighting, eco-conscious feel"},
    "luxury":           {"keyword": "luxury editorial",            "directives": "Empty premium spaces, premium materials close-up, minimal people, muted palette, aspirational restraint"},
    "energetic":        {"keyword": "dynamic action photograph",   "directives": "Motion blur accents, vibrant saturated colors, high energy, human movement, sports/fitness feel"},
    "nostalgic":        {"keyword": "vintage nostalgic photograph", "directives": "Retro color grading (70s/80s/90s), warm grain, analog textures, faded tones, throwback composition. Nostalgia remix trend"},
    "dreamy":           {"keyword": "dreamy soft-focus image",     "directives": "Blur effects, atmospheric haze, soft pastel colors, ethereal mood, gentle light leaks, romantic feel"},

    # ── Industry-Specific ──
    "corporate":        {"keyword": "corporate professional photograph", "directives": "Even studio lighting, clean backgrounds, neutral tones, sharp focus, trustworthy and polished"},
    "craftsmanship":    {"keyword": "detail close-up photograph",  "directives": "Hands at work, material textures in focus, warm side-lighting, shallow DOF, artisan pride"},
    "data-viz":         {"keyword": "data visualization graphic",  "directives": "Clean chart/diagram layout, high contrast, sans-serif typography, infographic aesthetic, clear hierarchy"},
    "ugc":              {"keyword": "authentic user-generated content style photograph", "directives": "Phone-camera feel, natural imperfections, real settings, no studio lighting, relatable and genuine. Micro-authenticity trend 2026"},
}


def _get_image_style(style_key: str | None) -> dict[str, str]:
    """Look up image style by key, fallback to photorealistic."""
    if style_key and style_key in _IMAGE_STYLE_MAP:
        return _IMAGE_STYLE_MAP[style_key]
    return _IMAGE_STYLE_MAP["photorealistic"]


_MOOD_KEYWORDS: dict[str, list[str]] = {
    "positive and empowering — people should look engaged, confident, and motivated": [
        "master", "success", "achieve", "grow", "win", "boost", "improve", "reclaim",
        "transform", "unlock", "elevate", "thrive", "excel", "empower",
    ],
    "urgent and cautionary — convey alertness and focus, not panic": [
        "avoid", "stop", "don't", "mistake", "pitfall", "risk", "danger", "warning", "fail",
    ],
    "curious and exploratory — convey wonder and openness": [
        "discover", "explore", "learn", "research", "investigate", "wonder", "uncover", "reveal",
    ],
    "action-oriented and determined — convey forward momentum": [
        "start", "launch", "build", "create", "execute", "implement", "ship", "deploy",
    ],
    "warm and communal — convey togetherness and support": [
        "community", "together", "support", "gratitude", "grateful", "team", "celebrate",
        "share", "connect", "belong", "welcome", "help",
    ],
    "fun and energetic — convey excitement and spontaneity": [
        "fun", "exciting", "amazing", "wow", "love", "hack", "trick", "trend",
        "viral", "challenge", "try", "watch",
    ],
    "authoritative and data-driven — convey expertise and strategic insight": [
        "strategy", "roi", "metrics", "pipeline", "framework", "methodology",
        "benchmark", "optimize", "scale", "revenue", "performance", "leverage",
    ],
}


def _infer_slide_mood(slide_text: str) -> str:
    """Infer mood from slide text using word-boundary keyword matching."""
    words = set(re.findall(r'\b\w+\b', slide_text.lower()))
    for mood, keywords in _MOOD_KEYWORDS.items():
        if words & set(keywords):
            return mood
    return "professional and approachable"


def _build_image_prompt(
    platform: str,
    style: dict[str, str],
    enhanced_image_prompt: str,
    image_style_directive: str,
    color_hint: str,
    style_ref_block: str,
    aspect: str,
    derivative_type: str | None = None,
) -> str:
    """Build a platform-aware image generation prompt."""
    _spec = get_platform(platform)

    _color_block = ""
    if color_hint:
        _color_block = (
            f"{color_hint} Incorporate these brand colors as accents — "
            "through environment elements, clothing, props, lighting tint, or background tones. "
            "Brand colors should be noticeable but not dominate the composition. "
            "The palette should feel natural, not artificially saturated.\n"
        )
    prompt = (
        f"Create a high-quality {aspect} {style['keyword']} for {platform}.\n"
        f"Subject: {enhanced_image_prompt}\n"
        f"Visual direction: {style['directives']}. {image_style_directive}\n"
        f"{_color_block}"
    )
    if _spec.composition:
        prompt += f"COMPOSITION: {_spec.composition}\n"
    if _spec.lighting:
        prompt += f"LIGHTING: {_spec.lighting}\n"
    if _spec.mood:
        prompt += f"MOOD: {_spec.mood}\n"
    prompt += (
        "TECHNICAL: Professional quality, proper white balance, no motion blur unless "
        "intentional, correct perspective geometry, clean edges.\n"
    )
    if _spec.people:
        prompt += f"PEOPLE: {_spec.people}\n"

    # Text overlay platforms get different instructions
    if _spec.text_overlay:
        prompt += (
            "TEXT ZONES: Leave clear areas for text overlay (top 20% and bottom 30%).\n"
            "Background should be slightly muted/gradient in text zones for readability.\n"
        )
    else:
        prompt += "Leave center/lower third slightly uncluttered (text may be added separately).\n"

    prompt += (
        "SCENE GUIDANCE:\n"
        "- Ground the subject in a specific, tangible environment — avoid generic or empty backdrops.\n"
        "- Vary the setting to match the subject matter (kitchen for food, workshop for craft, park for lifestyle, etc.).\n"
        "- Avoid GENERIC office/boardroom scenes. If the topic involves professional work, show a SPECIFIC workspace "
        "(a real desk with real tools, a workshop, a client site) — not a sterile conference table.\n"
        "- If the visual concept involves screens or monitors, show them — but their displays should contain abstract shapes, color gradients, or blurred content, never readable text.\n"
        "- Props and environmental details should reinforce the subject, not distract from it.\n"
    )
    prompt += (
        "ABSOLUTE PROHIBITIONS (text will be added in post-production — the image must be text-free):\n"
        "- No AI-generated text, letters, numbers, words, labels, or typography anywhere in the image\n"
        "- No readable text on any surface — screens, signs, books, clothing, whiteboards, packaging. Show abstract visuals, color fields, or blurred content instead\n"
        "- No watermarks, logos, brand marks, or signatures\n"
        "- No UI elements, buttons, frames, borders, or overlays\n"
        "- No fake screenshots, browser windows, or device mockups\n"
        "- No floating/disconnected elements or glowing holographic shapes\n"
        "- No distorted anatomy, extra limbs, or wrong finger counts\n"
        "- No stock-photo cliches: handshake, lightbulb, puzzle pieces, gears, miniature people on oversized objects, "
        "magnifying glass over documents, person reviewing paperwork, person pointing at or touching a screen/whiteboard, "
        "person at laptop in modern office, generic conference room or boardroom, person holding tablet or clipboard, "
        "blue holographic data visualizations, person with arms crossed posing at camera, "
        "group standing around a table, team high-fiving, sticky notes on glass wall, rocket ship\n"
        f"{style_ref_block}"
    )
    return prompt


def _build_carousel_slide_prompt(
    platform: str,
    style: dict[str, str],
    slide_num: int,
    slide_visual_hint: str,
    color_hint: str,
    style_ref_block: str,
    slide_text: str = "",
) -> str:
    """Build prompt for a carousel slide image — visual hint only, no text content."""
    _spec = get_platform(platform)
    carousel_notes = _spec.carousel_notes or ""
    mood = _infer_slide_mood(slide_text) if slide_text else (_spec.mood or "professional")

    _color_block = ""
    if color_hint:
        _color_block = (
            f"{color_hint} Incorporate these brand colors as accents — "
            "through environment elements, clothing, props, lighting tint, or background tones. "
            "Noticeable but not dominant.\n"
        )
    prompt = (
        f"Create carousel slide {slide_num} image as a {style['keyword']}.\n"
        f"Visual direction: {style['directives']}.\n"
        f"Scene: {slide_visual_hint}\n"
        f"MOOD: {mood}.\n"
        f"{_color_block}"
    )
    if _spec.composition:
        prompt += f"COMPOSITION: {_spec.composition}\n"
    if _spec.lighting:
        prompt += f"LIGHTING: {_spec.lighting}\n"
    if carousel_notes:
        prompt += f"CAROUSEL: {carousel_notes}\n"
    prompt += (
        "VISUAL CONSISTENCY (CRITICAL): This slide MUST look like it belongs in the same "
        "visual series as the cover image. Match ALL of the following exactly:\n"
        "- Same visual style (e.g., editorial photo, hand-drawn illustration, 3D render)\n"
        "- Same color temperature and grading (warm/cool, saturation level)\n"
        "- Same lighting direction and quality\n"
        "- Same depth of field or detail level\n"
        "- Same background complexity (don't mix clean studio with busy street)\n"
        "A viewer should feel these belong to the same visual series.\n"
    )
    # Per-slide composition variety
    _SLIDE_COMPOSITIONS = {
        2: "COMPOSITION: Medium close-up shot. Focus on hands, tools, or a detail. Shallow depth of field.\n",
        3: "COMPOSITION: Wide or environmental shot. Show the full scene or space. Subject occupies less than 40% of frame.\n",
        4: "COMPOSITION: Overhead/flat-lay or unusual angle. Bird's-eye view of workspace, ingredients, materials, or arrangement.\n",
        5: "COMPOSITION: Tight close-up on texture, material, or expression. Abstract or detail-oriented.\n",
        6: "COMPOSITION: Medium shot from a low or diagonal angle. Dynamic perspective with environmental context.\n",
    }
    prompt += _SLIDE_COMPOSITIONS.get(slide_num, "COMPOSITION: Vary the angle and framing from previous slides. Avoid repeating the same shot.\n")
    prompt += (
        "ABSOLUTE PROHIBITIONS (text will be added in post-production — the image must be text-free):\n"
        "- No AI-generated text, letters, numbers, words, labels, or typography anywhere\n"
        "- No readable text on any surface — screens, signs, books, whiteboards, packaging. Show abstract visuals or blurred content instead\n"
        "- No watermarks, logos, brand marks, or signatures\n"
        "- No UI elements, buttons, frames, borders, or overlays\n"
        "- No floating/disconnected elements or glowing holographic shapes\n"
        "- No distorted anatomy, extra limbs, or wrong finger counts\n"
        "- No stock-photo cliches: handshake, lightbulb, puzzle pieces, gears, miniature people on oversized objects, "
        "magnifying glass over documents, person reviewing paperwork, person pointing at or touching a screen/whiteboard, "
        "person at laptop in modern office, generic conference room or boardroom, person holding tablet or clipboard, "
        "blue holographic data visualizations, person with arms crossed posing at camera, "
        "group standing around a table, team high-fiving, sticky notes on glass wall, rocket ship\n"
        f"{style_ref_block}"
    )
    return prompt
