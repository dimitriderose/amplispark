import asyncio
import base64
import logging
import re
from typing import AsyncIterator

from google import genai
from google.genai import types

from backend.config import GOOGLE_API_KEY, GEMINI_MODEL
from backend.clients import get_genai_client
from backend.constants import get_proof_tier
from backend.platforms import get as get_platform

# Interleaved text+image generation requires an image-capable model
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
from backend.services import budget_tracker as bt
from backend.services.storage_client import upload_image_to_gcs
from backend.services.brand_assets import get_brand_reference_images
from backend.services.image_postprocess import (
    resize_to_aspect, create_carousel_cover, create_carousel_slide,
    create_pinterest_pin, create_tiktok_cover,
)
from backend.agents.review_agent import review_post

# ── Extracted modules ──
from backend.agents.caption_pipeline import (
    _smart_condense, _enforce_char_limit, _fix_mojibake, _strip_markdown,
)
from backend.agents.carousel_builder import (
    _parse_slide_descriptions, _extract_slide_headline, _SLIDE_RE,
)
from backend.agents.hashtag_engine import _sanitize_hashtags
from backend.agents.quality_gates import (
    _review_gate, _check_quality_violations, _quality_retry,
)
from backend.agents.image_prompt_builder import (
    _build_image_prompt, _build_carousel_slide_prompt,
    _get_image_style, _IMAGE_STYLE_MAP,
)

logger = logging.getLogger(__name__)

def _validate_format(caption: str, derivative_type: str) -> bool:
    """Check if the caption follows the expected derivative format. Log warnings on mismatch."""
    if derivative_type == "carousel":
        ok = "Slide 1" in caption and "Slide 2" in caption
        if not ok:
            logger.warning("Carousel caption missing Slide 1/2 structure")
        return ok
    if derivative_type == "thread_hook":
        ok = "1/" in caption or "1)" in caption
        if not ok:
            logger.warning("Thread caption missing numbered format (1/, 2/...)")
        return ok
    if derivative_type == "pin":
        ok = "PIN TITLE" in caption.upper() or "PIN DESCRIPTION" in caption.upper()
        if not ok:
            logger.warning("Pin caption missing PIN TITLE / PIN DESCRIPTION labels")
        return ok
    return True


def _build_dedup_block(prior_hooks: list[str] | None) -> str:
    """Build a prompt block listing hooks already used this week for deduplication."""
    if not prior_hooks:
        return ""
    return (
        "CRITICAL — DO NOT repeat these hooks already used this week:\n"
        + "\n".join(f"  - {h}" for h in prior_hooks)
        + "\nYour hook must be COMPLETELY DIFFERENT in angle, structure, and wording.\n\n"
    )


_STRUCTURAL_PATTERNS_RE = re.compile(
    r"(?i)(?:"
    r"start with (?:a |an )?(?:\w+[\s,]+)*(?:question|statement|hook|bold)|"
    r"follow with|"
    r"include (?:a )?call to action|"
    r"end with (?:a )?(?:CTA|call to action|question)|"
    r"(?:us(?:e|ing) |include )bullet points|"
    r"share (?:a |an )?(?:story|insight|example)|"
    r"highlight (?:the |how )(?:brand|company)|"
    r"explain how \w+ provides|"
    r"(?:book a consultation|learn more|visit (?:our|the) website|DM us)|"
    r"address (?:a )?(?:common |their )?pain point"
    r")"
)


def _wrap_caption_style_directive(raw: str) -> str:
    """Strip structural instructions from caption_style_directive, keep only rhythm/tone.

    The raw directive stored in Firestore may contain content-structure instructions
    (e.g. 'start with a question', 'include a call to action') that conflict with
    QUALITY RULES and HOOK RULES. Instead of disclaiming them, actively remove them.
    """
    if not raw or not raw.strip():
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', raw.strip())
    clean = [s for s in sentences if not _STRUCTURAL_PATTERNS_RE.search(s)]
    if not clean:
        return ""
    return (
        "BRAND WRITING RHYTHM (tone and cadence ONLY):\n"
        f"{' '.join(clean)}\n"
    )


async def _generate_carousel_images(
    slide_descriptions: list[str],
    business_name: str,
    visual_style: str,
    color_hint: str,
    image_style_directive: str,
    style_ref_block: str,
    platform: str,
    post_id: str,
    cover_image_bytes: bytes | None,
    image_style: dict[str, str] | None = None,
) -> list[tuple[bytes, str]]:
    """Generate images for carousel slides 2+ in parallel.

    Returns list of (image_bytes, mime_type) tuples.
    Skips slide 0 if cover_image_bytes is already provided (from the interleaved call).
    """
    start = 1 if cover_image_bytes else 0
    slides_to_generate = slide_descriptions[start:]  # generate all remaining slides
    if not slides_to_generate:
        return []

    style = image_style or _get_image_style(None)

    # Limit concurrent image API calls to avoid rate limiting
    _sem = asyncio.Semaphore(3)

    async def _gen_one(slide_text: str, slide_num: int) -> tuple[bytes, str] | None:
        async with _sem:
            prompt = _build_carousel_slide_prompt(
                platform=platform,
                style=style,
                slide_num=slide_num,
                slide_visual_hint=slide_text[:200],
                color_hint=color_hint,
                style_ref_block=style_ref_block,
                slide_text=slide_text,
            )
            # Pass cover image as visual reference for style consistency
            contents: list = [prompt]
            if cover_image_bytes:
                contents.append(
                    "The following image is the carousel COVER — match its visual style, "
                    "color grading, lighting, and photographic approach exactly."
                )
                contents.append(types.Part.from_bytes(
                    data=cover_image_bytes, mime_type="image/png"
                ))
            try:
                resp = await asyncio.to_thread(
                    get_genai_client().models.generate_content,
                    model=GEMINI_IMAGE_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        temperature=0.7,
                    ),
                )
                for part in resp.candidates[0].content.parts:
                    if part.inline_data:
                        return (part.inline_data.data, part.inline_data.mime_type or "image/png")
            except Exception as e:
                logger.error("Carousel slide %d generation failed: %s", slide_num, e)
            return None

    results = await asyncio.gather(
        *[_gen_one(text, i + start + 1) for i, text in enumerate(slides_to_generate)]
    )
    return [r for r in results if r is not None]


async def _generate_image_with_retry(
    img_contents: list,
    max_retries: int = 2,
) -> tuple[bytes | None, str]:
    """Generate image with retry on failure. Returns (image_bytes, mime_type)."""
    for attempt in range(max_retries + 1):
        try:
            resp = await asyncio.to_thread(
                get_genai_client().models.generate_content,
                model=GEMINI_IMAGE_MODEL,
                contents=img_contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.7,
                ),
            )
            for part in resp.candidates[0].content.parts:
                if part.inline_data:
                    data = part.inline_data.data
                    mime = part.inline_data.mime_type or "image/png"
                    if len(data) > 5000:  # Minimum viable image (~5KB)
                        return data, mime
                    logger.warning("Image too small (%dB), retry %d/%d", len(data), attempt + 1, max_retries)
        except Exception as e:
            logger.warning("Image generation failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
        if attempt < max_retries:
            await asyncio.sleep(1)
    return None, "image/png"


async def _generate_alt_text(
    image_bytes: bytes,
    content_theme: str,
    platform: str,
) -> str | None:
    """Generate descriptive alt-text for accessibility using vision model.

    Only generated for platforms where alt-text is community-expected (Mastodon, Bluesky).
    """
    _spec = get_platform(platform)
    if not _spec.alt_text_required:
        return None

    try:
        result = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                (
                    f"Write alt-text for this image (for screen readers). Context: {content_theme[:150]}.\n"
                    "Be factual and descriptive: what's in the image, colors, composition.\n"
                    "Do NOT say 'AI-generated' or 'stock photo'. Max 300 characters."
                ),
            ],
        )
        alt = result.text.strip()[:500]
        return alt
    except Exception as e:
        logger.warning("Alt-text generation failed (non-fatal): %s", e)
        return None


async def generate_post(
    plan_id: str,
    day_brief: dict,
    brand_profile: dict,
    post_id: str,
    custom_photo_bytes: bytes | None = None,
    custom_photo_mime: str = "image/jpeg",
    instructions: str | None = None,
    prior_hooks: list[str] | None = None,
    image_style_key: str | None = None,
) -> AsyncIterator[dict]:
    """
    Generate a social media post using Gemini 2.5 Flash.

    If custom_photo_bytes is provided (BYOP mode): Gemini vision analyzes the
    photo and writes a caption; the photo is used as the hero image (no image
    generation budget consumed).

    Otherwise: interleaved TEXT+IMAGE generation (normal mode).

    Yields SSE-compatible event dicts: {"event": str, "data": dict}

    Events emitted (in order):
      {"event": "status",  "data": {"message": "..."}}
      {"event": "caption", "data": {"text": "...", "chunk": True}}   # streamed chunks
      {"event": "caption", "data": {"text": "...", "chunk": False, "hashtags": [...]}}  # final
      {"event": "image",   "data": {"url": "...", "mime_type": "image/png"}}
      {"event": "complete","data": {"post_id": "...", "caption": "...", "hashtags": [...], "image_url": "..."}}
      {"event": "error",   "data": {"message": "..."}}  # on failure
    """

    platform = day_brief.get("platform", "instagram")
    pillar = day_brief.get("pillar", "education")
    content_theme = day_brief.get("content_theme", "")
    caption_hook = day_brief.get("caption_hook", "")
    key_message = day_brief.get("key_message", "")
    image_prompt = day_brief.get("image_prompt", "")
    hashtags_hint = _sanitize_hashtags(day_brief.get("hashtags", []), platform)
    derivative_type = day_brief.get("derivative_type", "original")

    business_name = brand_profile.get("business_name", "Brand")
    industry = brand_profile.get("industry", "")
    target_audience = brand_profile.get("target_audience", "general audience")
    tone = brand_profile.get("tone", "professional")
    visual_style = brand_profile.get("visual_style", "")
    image_style_directive = brand_profile.get("image_style_directive", "")
    caption_style_directive = _wrap_caption_style_directive(
        brand_profile.get("caption_style_directive", "")
    )
    colors = brand_profile.get("colors", [])
    style_reference_gcs_uri = brand_profile.get("style_reference_gcs_uri")

    # Social voice block — injected when the user has connected a social account
    _sva = brand_profile.get("social_voice_analysis") or {}
    _sva_chars = _sva.get("voice_characteristics", [])
    _sva_phrases = _sva.get("common_phrases", [])
    _sva_tone = _sva.get("tone_adjectives", [])
    if _sva_chars or _sva_phrases:
        _sva_lines = ["EXISTING SOCIAL VOICE (match this style closely):"]
        if _sva_chars:
            _sva_lines.append(f"- Voice characteristics: {', '.join(_sva_chars)}")
        if _sva_phrases:
            _sva_lines.append(f"- Common phrases: {', '.join(_sva_phrases)}")
        if _sva_tone:
            _sva_lines.append(f"- Tone adjectives: {', '.join(_sva_tone)}")
        _sva_lines.append(
            "IMPORTANT: Generated captions should sound like this person's existing voice, not replace it."
        )
        social_voice_block = "\n".join(_sva_lines) + "\n"
    else:
        social_voice_block = ""

    # Quality guardrails injected into every generation prompt
    _QUALITY_BLOCK = (
        "QUALITY RULES:\n"
        "FORMATTING: Write plain text only. No **bold**, *italic*, __underline__, or [links](url). "
        "Use CAPS or emoji for emphasis sparingly.\n\n"
        "BANNED PATTERNS (instant fail if any appear):\n"
        "- \"Are you ready to...?\" / \"Did you know...?\" / \"What if...?\" / \"In today's [adjective] world...\"\n"
        "- \"As a [profession]...\" / \"When it comes to...\" / \"Let's dive in\"\n"
        "- \"Still [verb]-ing...?\" (e.g., \"Still handling your own marketing?\")\n"
        "- \"[Role] won't tell you this about...\" (clickbait hook family)\n"
        "- \"You might be [missing/leaving/losing]...\" (fear-based hook)\n"
        "- \"Imagine [positive outcome]...\" (wish-casting hook)\n"
        "- \"Game-changer\" / \"unlock your potential\" / \"take it to the next level\"\n"
        "- \"Drop a comment below!\" / \"Follow for more!\" / \"Like and share\"\n"
        "- \"Here's the thing:\" / \"The truth is:\" / \"Let me tell you something:\"\n"
        "- \"Sound familiar?\" / \"Let's break it down\" / \"Here's why it matters\" / "
        "\"Let's talk about it\" / \"Let me explain\" (momentum-killing filler after hooks)\n"
        "- Starting 3+ sentences with \"It's\" or \"This is\"\n"
        "- Emoji bullet lists (fire Point one, pin Point two, lightbulb Point three)\n"
        "- More than 2 emojis in any single post\n"
        "- Generic advice that could apply to any business in any industry\n"
        "- Ending with an exclamation mark on more than 1 sentence\n"
        "- Fabricated statistics, percentages, or specific numbers not from the brand profile\n"
        "- \"We've seen countless...\" / \"Many businesses...\" / \"So many [people/clients/owners]...\" "
        "(vague social proof — use the brand's real data or skip social proof entirely)\n\n"
        "REQUIRED:\n"
        "- VALUE FIRST: The caption must TEACH — a specific tip, fact, insight, "
        "or perspective the reader didn't know. The brand is the NARRATOR, not the subject.\n"
        "  BAD: 'At [Brand], we partner with [audience] to provide [service].' (brand-as-subject paragraph)\n"
        "  GOOD: '[Specific insight]. We noticed this pattern last quarter.' (brand woven into the story)\n"
        "- NO BRAND PARAGRAPHS: Never dedicate a full paragraph to describing the brand's services, "
        "history, or value proposition. The brand name should appear at most ONCE, "
        "embedded naturally in a sentence that's primarily about the reader's problem or the insight.\n"
        "- At least one SPECIFIC detail (number, name, timeframe, scenario) from the brand profile\n"
        "- A human perspective — first person (\"we\", \"I\", \"our clients\") not third person\n"
        "- Content that could ONLY come from this brand, not a generic template\n"
        "- CTA DISCIPLINE: End with ONE type of CTA — either an engagement question "
        "(\"What's your approach?\") OR a conversion action (\"Book a call\" / \"DM us\"), NEVER both. "
        "Engagement questions get more reach; conversion CTAs get more leads. Pick one per post.\n"
        "  BY DERIVATIVE TYPE:\n"
        "  - video_first: CTA is optional — a cliffhanger or curiosity hook works better than a forced CTA.\n"
        "  - story: CTA required (swipe up / reply / DM — the CTA IS the point of a story).\n"
        "  - pin: CTA is implicit in the action-oriented title ('How to...', 'Try this...'). "
        "Do NOT add an explicit question or conversion CTA.\n"
        "  - carousel/original/blog_snippet: CTA required.\n"
        "  BY PLATFORM (overrides above when stricter):\n"
        "  - Threads: ONLY engagement questions, NEVER conversion CTAs. A hot take that naturally "
        "invites replies is better than an explicit question.\n"
        "  - Mastodon: Do NOT include any CTA. No engagement questions, no conversion actions. "
        "The community boosts genuinely useful content. Asking for engagement is considered spam.\n"
        "  - Bluesky: Engagement questions must be SPECIFIC to the content topic. "
        "Generic questions ('What do you think?', 'Thoughts?') are treated as spam.\n"
        "  - Facebook: Engagement questions should be the default. Conversion CTAs get zero organic reach.\n"
        "  - YouTube Shorts: 'Subscribe' is a valid CTA — not a generic CTA."
    )

    # Hook quality enforcement
    _HOOK_BLOCK = (
        "HOOK RULES (your opening line determines if anyone reads the rest):\n"
        "1. SPECIFICITY: Include a number, timeframe, or concrete detail from the brand's real experience.\n"
        "   BAD: \"Growing your business is hard\"\n"
        "   GOOD: \"After 20 years in this industry, here's the one mistake we still see every quarter\"\n"
        "2. PATTERN INTERRUPT — use one of these structures (rotate, NEVER repeat same pattern in a week):\n"
        "   - Contrarian flip: \"[Common belief] is actually costing you [specific consequence].\"\n"
        "   - Data-driven: \"[X]% of [audience] make this mistake. Here's the pattern.\"\n"
        "   - Story opener: \"A client came to us last [season] because...\"\n"
        "   - Number: \"[X] mistakes we see every [timeframe] in [industry]\"\n"
        "   - Question: \"What would change if you [specific outcome]?\"\n"
        "   - Confession: \"We almost made this mistake ourselves.\"\n"
        "   - Observation: \"I've reviewed [X] [items] this year. Here's the pattern.\"\n"
        "   - Comparison: \"[Thing A] vs [Thing B] — and why most people pick wrong.\"\n"
        "   BANNED HOOK FORMATS (overused — except TikTok/Reels where imperatives are native):\n"
        "   - \"Stop [verb]-ing...\" (the 'Stop doing X' formula)\n"
        "   - \"Most people don't realize...\"\n"
        "   - \"Here's the truth about...\"\n"
        "   - \"Nobody is talking about...\"\n"
        "3. NEVER start with: \"Are you...?\", \"Did you know...?\", \"What if...?\", \"In today's...\", \"As a...\", \"When it comes to...\"\n"
        "4. The hook from the brief is a STARTING POINT — rewrite it to be specific and surprising.\n"
        "5. PLATFORM FOLD: Your hook MUST land BEFORE the fold (Instagram: 125 chars, "
        "LinkedIn: 140 chars, Facebook: ~140 chars). Everything after the fold requires "
        "a tap to reveal — if the hook isn't above the fold, nobody reads the rest.\n"
        "6. HOOK TEST: Read just the first line. Would a stranger in your target audience "
        "stop scrolling? If not, rewrite it."
    )

    # Pinterest: SEO-driven titles, not social hook patterns
    if platform == "pinterest":
        _HOOK_BLOCK = (
            "PIN TITLE RULES:\n"
            "- Keyword-rich, action-oriented title under 100 characters\n"
            "- Start with a verb or number ('5 Ways...', 'How to...', 'Try this...')\n"
            "- Optimize for Pinterest search, not social engagement\n"
            "- No question hooks, no contrarian takes — just clear, searchable value"
        )

    # ── Self-Review Checklist (appended to every prompt) ──
    _SELF_REVIEW_CHECKLIST = (
        "\n--- SELF-REVIEW (run EVERY check before outputting. If ANY check fails, "
        "rewrite BEFORE outputting. Output ONLY the final corrected caption — no drafts, "
        "no explanations.) ---\n\n"

        "☐ HOOK: Does my first line match a banned opener? "
        "(Are you...?, Did you know...?, What if...?, In today's..., As a..., "
        "When it comes to..., Still [verb]-ing...?, [Role] won't tell you..., "
        "You might be [missing/leaving]..., Imagine [outcome]..., "
        "[Number] ways/reasons/tips..., The secret to...)\n"
        "  → REWRITE as a concrete, mid-story statement or a bold claim rooted in "
        "the brand's specific domain. No rhetorical or clickbait questions. No direct address. "
        "The hook must be a complete, compelling thought within the pre-fold window.\n"
        "  PLATFORM EXCEPTIONS — X: a short provocative question or hot take (<60 chars) is native; "
        "allow if not from the banned list. TikTok: 'Stop [verb]-ing' and lowercase imperatives are native. "
        "Threads/Bluesky: a genuine, specific question is acceptable if not from the banned list. "
        "Pinterest: rewrite as a keyword-rich descriptive phrase a user would search for — "
        "no first person, no social hooks. YouTube Shorts: keep it short and curiosity-driven, "
        "subordinate to the video.\n"
        "  TONE — X: tight and opinionated, sentence fragments OK. "
        "TikTok: lowercase and casual, if it reads like a press release rewrite as a text message. "
        "Facebook: warm and relational, first-person stories over informational statements.\n\n"

        "☐ BRAND PARAGRAPH & VOICE: Did I write a sentence where the brand is the subject "
        "and the verb describes what the brand does, offers, or believes? "
        "(e.g., '[Brand] specializes in...', '[Brand] has been helping...', 'At [Brand], we...') "
        "Did I shift person (I/we/you/they/the brand) inconsistently within the caption? "
        "Did I restate the brand's category as if it were a value proposition?\n"
        "  → DELETE brand-as-subject sentences. The brand appears once, as the resolution to "
        "the reader's problem, never as the topic. Pick one voice (first-person singular for "
        "thought leadership, second-person for educational, first-person plural for brand voice) "
        "and hold it for the entire caption. Pinterest: no first person in titles or descriptions.\n\n"

        "☐ FORMATTING & HASHTAGS: Did I use emoji bullet lists, emoji as section markers, "
        "more than 2 emoji total, markdown syntax (**bold**, ### headers, [links]()), "
        "or numbered lists (LinkedIn permits short numbered lists ≤5 items)? "
        "Did I use hashtags on Pinterest (deprecated — remove them), "
        "lowercase hashtags on Mastodon (use #CamelCase for screen reader accessibility), "
        "or #Shorts on YouTube Shorts (unnecessary — remove it)?\n"
        "  → REMOVE all markdown. REMOVE emoji bullets and section markers. "
        "Reduce to 0–2 emoji max. Keep paragraphs to 1–2 sentences for mobile readability. "
        "TikTok carousel: up to 4 emoji permitted as inline visual rhythm. "
        "Mastodon: fix all hashtags to #CamelCase. Pinterest: remove all hashtags.\n"
        "  HASHTAG COUNTS — X: 0–2 inline only, never stacked at end. "
        "TikTok: 3–5 niche-specific at caption end (never #fyp #viral). "
        "Facebook: 0–1 max. Instagram: ≤5, in a separate block after the caption body, "
        "no inline hashtags mid-sentence.\n\n"

        "☐ FILLER & PACING: Did I include a stalling phrase? "
        "(Here's the thing, Let's break it down, Here's why this matters, Here's the truth, "
        "The reality is, Think about it, Let me explain, It's no secret that, It's simple, "
        "The good news is, Sound familiar?)\n"
        "  → DELETE the phrase. Start the sentence with the actual content that follows it.\n\n"

        "☐ SPECIFICITY: Did I use a generic claim or advice not tied to this brand's actual data, "
        "niche, or offering? (post consistently, engage with your audience, stay ahead of the curve, "
        "take your business to the next level, in today's competitive landscape, unlock your potential, "
        "it's a game-changer) Did I restate the brand's industry category as a value proposition?\n"
        "  → REPLACE with a concrete detail from the brand brief or DELETE entirely. "
        "If I cannot make it specific, it does not belong.\n\n"

        "☐ SOCIAL PROOF: Did I use a vague quantifier? "
        "(countless, many businesses, many clients, so many, numerous, a growing number of, "
        "tons of, hundreds of)\n"
        "  → REPLACE with a specific number from the brand profile. "
        "If no number exists, REMOVE the claim — do not fabricate.\n\n"

        "☐ FABRICATION: Did I invent a statistic, percentage, dollar amount, timeframe, "
        "or regulatory/legal claim not provided in the brand brief?\n"
        "  → DELETE and restate qualitatively (e.g., 'improved cash flow' not "
        "'boosted revenue by 30%'). Never invent numbers.\n\n"

        "☐ CTA: Do I have more than one call to action (engagement question + conversion CTA, "
        "or two of either)? Does my CTA violate platform norms?\n"
        "  PLATFORM RULES — Mastodon: ZERO CTAs, no engagement bait; prepend CW: [topic] for "
        "food/diet, politics, mental health, or corporate content. "
        "Threads: conversational only, no 'link in bio', no conversion language. "
        "TikTok: embedded in narrative, not appended. "
        "X: no appended links or 'check out' directives — embed as a reply prompt. "
        "Facebook: conversational engagement questions only — no 'tag a friend', no link-pushing; "
        "a light conversational question improves distribution, so keep one if natural. "
        "Pinterest: action-verb CTAs only ('Try', 'Save', 'Make') — no 'Follow us' or 'Visit our site'. "
        "YouTube Shorts: 'Subscribe' / 'Follow for more' are valid; no other conversion CTAs. "
        "Bluesky: no generic engagement bait ('Thoughts?' = spam) — ask a specific question or omit. "
        "LinkedIn: no raw URLs in caption body (suppresses reach).\n"
        "  → KEEP only one. Match platform tone. When in doubt, cut the CTA entirely.\n\n"

        "☐ LENGTH & FOLD: Does my caption fit the platform character limit? "
        "Does my strongest hook land BEFORE the fold?\n"
        "  LIMITS — X: 280 chars hard limit, no fold. "
        "TikTok video: 200 chars max. TikTok carousel: up to 800 chars, keyword-rich. "
        "Instagram: 125 chars before fold, best at <300 or 800–1200 total. "
        "LinkedIn: 140 chars before fold, best at 1000–1800 total. "
        "Facebook: 140 chars before fold. "
        "Bluesky: 300 chars hard limit (not 280). "
        "Threads: 500 chars limit, 200–300 sweet spot. "
        "Pinterest: title ≤100 chars, front-load keywords in first 50 chars of description. "
        "YouTube Shorts: ~100 chars visible before truncation. "
        "Mastodon: 500 chars total, no fold.\n"
        "  → CUT from the middle, never the hook or close. Front-load the hook into the "
        "pre-fold window. Avoid the 400–700 char dead zone on Instagram. "
        "For carousel slides: each slide carries one complete idea in ≤15 words; "
        "do not split a sentence across slides.\n\n"

        "--- END SELF-REVIEW ---\n"
    )

    # Industry hook research context (from strategy agent web search)
    _hook_research = day_brief.get("hook_research", "")
    _hook_context = (
        f"\nINDUSTRY HOOK RESEARCH (use these patterns as inspiration):\n{_hook_research}\n"
    ) if _hook_research else ""

    # ── Storytelling + Social Proof Strategy ──
    _story_details = []
    _has_years = bool(brand_profile.get("years_in_business"))
    _has_clients = bool(brand_profile.get("client_count"))
    _has_location = bool(brand_profile.get("location"))
    _has_usp = bool(brand_profile.get("unique_selling_points"))

    if brand_profile.get("business_name"):
        _story_details.append(f"Business: {brand_profile['business_name']}")
    if _has_years:
        _story_details.append(f"In business for {brand_profile['years_in_business']} years")
    if _has_location:
        _story_details.append(f"Based in {brand_profile['location']}")
    if _has_clients:
        _story_details.append(f"Served {brand_profile['client_count']}+ clients")
    if _has_usp:
        _story_details.append(f"Known for: {brand_profile['unique_selling_points']}")

    # Determine social proof tier based on available data
    _proof_tier = get_proof_tier(
        brand_profile.get("years_in_business"),
        brand_profile.get("client_count"),
    )

    _PROOF_STRATEGIES = {
        "data_rich": (
            "SOCIAL PROOF STRATEGY (your brand has strong data — USE IT):\n"
            "- Lead with hard numbers: 'After {years} years and {clients}+ clients...'\n"
            "- Reference real experience patterns: 'In {years} years, the #1 mistake we see is...'\n"
            "- NEVER use vague framing ('many clients', 'countless businesses') — "
            "you have real numbers, use them.\n"
        ),
        "partial_data": (
            "SOCIAL PROOF STRATEGY (use what you have, don't inflate):\n"
            "- Use available data specifically: 'After {years} years...' or "
            "'Working with {clients}+ clients...'\n"
            "- For missing data, use PROCESS AUTHORITY instead: 'The first thing we check is...' / "
            "'In our experience, the pattern looks like...'\n"
            "- NEVER inflate: no 'countless', 'many', or 'so many' — either cite the real number "
            "or describe your process.\n"
        ),
        "thin_profile": (
            "SOCIAL PROOF STRATEGY (NO volume claims — ZERO tolerance):\n"
            "- You have NO data about years in business or client count. Do NOT reference either.\n"
            "- ABSOLUTELY FORBIDDEN phrases: 'We've seen...', 'Our clients...', 'Over the years...', "
            "'Many businesses...', 'Countless...', 'Time and again...', 'We've helped...', "
            "'Clients tell us...', 'We see clients...', 'Clients typically...'\n"
            "- Lead with EDUCATIONAL AUTHORITY: teach a specific, actionable insight. "
            "The teaching IS the proof.\n"
            "- Use PROCESS AUTHORITY: 'The first thing to check is...' / "
            "'Here's what most people miss about...'\n"
            "- If you catch yourself writing 'we' + a verb implying client volume, DELETE the sentence.\n"
        ),
    }

    _storytelling_block = ""
    if _story_details:
        _proof_strategy = _PROOF_STRATEGIES[_proof_tier]
        if _has_years:
            _proof_strategy = _proof_strategy.replace(
                "{years}", str(brand_profile["years_in_business"])
            )
        if _has_clients:
            _proof_strategy = _proof_strategy.replace(
                "{clients}", str(brand_profile["client_count"])
            )

        _storytelling_block = (
            "VERIFIED BRAND DATA (you may reference these — they are real):\n"
            + "\n".join(f"  - {d}" for d in _story_details) + "\n\n"
            + _proof_strategy + "\n"
            "FABRICATION RULES:\n"
            "- You MAY reference: years in business, client count, location, industry, brand values.\n"
            "- You MAY use hypothetical framing: 'Imagine discovering...', "
            "'One of the most common situations we encounter...'\n"
            "- You MUST NOT fabricate specific claims: no invented dollar amounts, "
            "percentages, statistics, or quantities not in the brand profile above.\n"
            "  BAD: 'We saved a restaurant owner $47K last quarter' (fabricated event)\n"
            "  BAD: 'NYC businesses lose 10-15% growth annually' (fabricated statistic)\n"
            "  GOOD: 'After 20 years and 400+ clients, we know what happens when...' (real data)\n"
            "  GOOD: 'The first thing we check in any new engagement is...' (process authority)\n"
        )
    else:
        _storytelling_block = (
            "SOCIAL PROOF STRATEGY (NO DATA AVAILABLE — strict rules):\n"
            "This brand has no profile data. You MUST:\n"
            "- Lead with EDUCATIONAL AUTHORITY: teach something specific and useful.\n"
            "- Use PROCESS AUTHORITY: 'The first thing to check is...' / 'Here's what most people miss...'\n"
            "- NEVER reference clients, experience, years, or volume in any form.\n"
            "- NEVER use 'we've seen', 'our clients', 'many businesses', or similar.\n"
            "- The insight IS the credibility. Nothing else.\n"
        )

    # ── Social proof prompt guard (thin profiles only) ──
    _social_proof_guard = ""
    if _proof_tier == "thin_profile" or not _story_details:
        _social_proof_guard = (
            "\n⚠️ SOCIAL PROOF HARD BLOCK ⚠️\n"
            "This brand has NO verified client data. You MUST NOT:\n"
            "- Reference clients in any form (our clients, we've helped, clients tell us)\n"
            "- Claim experience volume (years, countless, many, numerous)\n"
            "- Use 'we see' or 'we find' to imply client observation patterns\n"
            "- Fabricate any social proof (testimonials, case studies, statistics)\n"
            "If your draft contains ANY of the above, DELETE those sentences before outputting.\n\n"
        )

    # ── Pillar-aware social proof relaxation ──
    _pillar = day_brief.get("pillar", "")
    if _pillar == "behind_the_scenes" and (_proof_tier == "thin_profile" or not _story_details):
        _social_proof_guard += (
            "PILLAR EXCEPTION — behind_the_scenes:\n"
            "You MAY describe the team's workflow, collaboration style, office environment, "
            "and professional process. 'Our team' and 'we' are fine for BTS content.\n"
            "You still MUST NOT claim client counts, revenue figures, years in business, "
            "or fabricate specific outcomes. The ban is on VOLUME CLAIMS, not team identity.\n\n"
        )

    # ── Education pillar boost for thin-profile brands ──
    if _pillar == "education" and (_proof_tier == "thin_profile" or not _story_details):
        _platform = day_brief.get("platform", "")
        _edu_tone = ""
        if _platform == "facebook":
            _edu_tone = (
                "FACEBOOK EDUCATION TONE: Write as if giving advice to a neighbor, "
                "not lecturing a class. Conversational, local, seasonal framing. "
                "Avoid listicle format — use narrative flow instead.\n"
            )
        elif _platform == "linkedin":
            _edu_tone = (
                "LINKEDIN EDUCATION TONE: Go deep. Name specific rules, methods, "
                "or step-by-step processes. LinkedIn audiences "
                "expect professional depth — surface-level tips underperform.\n"
                "LINKEDIN MOBILE: 70%+ of LinkedIn is consumed on mobile. "
                "Use bullet points for multi-step processes. Max 2 sentences per paragraph. "
                "No dense text blocks — break complex ideas into scannable chunks.\n"
            )
        _social_proof_guard += (
            "EDUCATION PILLAR — THIN PROFILE BOOST:\n"
            "Education is this brand's PRIMARY trust signal. Go DEEP, not broad.\n"
            "- Name a SPECIFIC technique, rule, framework, or method — not general advice\n"
            "- Include at least one concrete detail the reader can act on TODAY\n"
            "- Example of WEAK: 'Stay organized and plan ahead for better results'\n"
            "- Example of STRONG: 'Most businesses lose 10-15% of revenue to inefficient processes — "
            "here is a 3-step audit to find where yours are leaking'\n"
            "The reader should learn something they didn't know before reading this post.\n"
            f"{_edu_tone}\n"
        )

    _social_proof_checklist_item = ""
    if _proof_tier == "thin_profile" or not _story_details:
        _social_proof_checklist_item = (
            "☐ THIN-PROFILE SOCIAL PROOF (this brand has NO verified client data):\n"
            "  Did I write ANY of these? → DELETE the entire sentence:\n"
            "  - 'We've seen...' / 'We see...' / 'We find...'\n"
            "  - 'Our clients...' / 'Clients tell us...' / 'Clients typically...'\n"
            "  - 'We've helped...' / 'We've worked with...'\n"
            "  - 'Over the years...' / 'In our experience...'\n"
            "  - 'Many businesses...' / 'Countless...' / 'Time and again...'\n"
            "  → You have ZERO client data. The ONLY proof is teaching something specific.\n\n"
        )

    # ── CTA enforcement from strategy agent ──
    _cta_type = day_brief.get("cta_type", "engagement")
    _CTA_ENFORCEMENT = {
        "engagement": (
            "CTA CONSTRAINT: This post uses an ENGAGEMENT CTA only.\n"
            "End with ONE conversational question or discussion prompt.\n"
            "Do NOT include any conversion language (no 'book', 'DM', 'link in bio', 'visit').\n"
        ),
        "conversion": (
            "CTA CONSTRAINT: This post uses a CONVERSION CTA only.\n"
            "End with ONE clear action step (book, DM, save, visit).\n"
            "Do NOT also add an engagement question — one CTA only.\n"
        ),
        "implied": (
            "CTA CONSTRAINT: This post uses an IMPLIED CTA.\n"
            "The content should naturally lead the reader to want the brand's service.\n"
            "Do NOT add any explicit CTA — no questions, no 'book a call', no 'DM us'.\n"
        ),
        "none": (
            "CTA CONSTRAINT: This post has NO CTA.\n"
            "Do NOT include any call to action — no questions, no conversion language, no 'thoughts?'\n"
        ),
    }
    _cta_block = _CTA_ENFORCEMENT.get(_cta_type, _CTA_ENFORCEMENT["engagement"])

    # Dynamic char limit for self-review checklist
    _spec = get_platform(platform)
    _deriv_char_limit = (_spec.char_limits or {}).get(derivative_type) or (_spec.char_limits or {}).get("default", 0)
    _char_limit_reminder = (
        f"\nCHARACTER LIMIT FOR THIS POST: {platform} {derivative_type} = {_deriv_char_limit} chars max. "
        f"If your caption exceeds {_deriv_char_limit} characters, REWORD it to fit — "
        f"do NOT just cut off mid-sentence. The caption must be a complete thought.\n"
    ) if _deriv_char_limit else ""

    # Pillar-get helper: returns pillar-specific guidance or default
    def _pg(m: dict[str, str], d: str) -> str:
        return m.get(_pillar, d)

    # Format-specific instructions for derivative post types
    _DERIVATIVE_INSTRUCTIONS: dict[str, str] = {
        "carousel": (
            f"FORMAT: {platform.upper()} CAROUSEL ({_spec.carousel_slide_count} slides)\n"
            "Structure the caption as slide-by-slide copy:\n"
            "  Slide 1: Hook (compelling, 8-12 words — this becomes the cover). "
            "ALL hook rules above apply.\n"
            + {
                "education": (
                    "  Slide 2: Stakes — WHY this topic matters. What the reader gains or loses.\n"
                    f"  Slides 3-{_spec.carousel_slide_count - 2}: Each slide starts with a SHORT HEADLINE "
                    "(≤50 chars, ≤8 words). Teach ONE specific insight per slide — name a real "
                    "technique, rule, or method. Give a CONCRETE EXAMPLE showing it in practice. "
                    "NAMING TEST: You should be able to say 'This slide teaches [technique name]'.\n"
                ),
                "promotion": (
                    "  Slide 2: The problem/need — what pain point does this product solve?\n"
                    f"  Slides 3-{_spec.carousel_slide_count - 2}: Each slide starts with a SHORT HEADLINE "
                    "(≤50 chars, ≤8 words). Showcase ONE specific feature, benefit, or use case "
                    "per slide. Show the feature IN ACTION — a scenario, a before/after, or a "
                    "concrete result. NOT generic marketing claims.\n"
                ),
                "inspiration": (
                    "  Slide 2: The starting point — where the story begins (the struggle, "
                    "the challenge, the 'before').\n"
                    f"  Slides 3-{_spec.carousel_slide_count - 2}: Each slide starts with a SHORT HEADLINE "
                    "(≤50 chars, ≤8 words). Advance the transformation story — each slide is a "
                    "chapter with a specific moment, turning point, or realization. "
                    "Use concrete details (dates, places, emotions, decisions).\n"
                ),
                "behind_the_scenes": (
                    "  Slide 2: Set the scene — what are we looking at and why it matters.\n"
                    f"  Slides 3-{_spec.carousel_slide_count - 2}: Each slide starts with a SHORT HEADLINE "
                    "(≤50 chars, ≤8 words). Show ONE step, detail, or moment from the real process. "
                    "Be specific: tools used, decisions made, things that went wrong. "
                    "Authenticity > polish.\n"
                ),
                "user_generated": (
                    "  Slide 2: Introduce the person/customer — who they are and their context.\n"
                    f"  Slides 3-{_spec.carousel_slide_count - 2}: Each slide starts with a SHORT HEADLINE "
                    "(≤50 chars, ≤8 words). Tell their specific story — real quotes, real details, "
                    "real outcomes. Each slide advances the narrative. "
                    "Write in THEIR voice, not corporate voice.\n"
                ),
            }.get(_pillar, (
                "  Slide 2: Context — WHY this matters to the reader.\n"
                f"  Slides 3-{_spec.carousel_slide_count - 2}: Each slide starts with a SHORT HEADLINE "
                "(≤50 chars, ≤8 words). One distinct point per slide with a concrete detail.\n"
            ))
            + "  OPEN LOOPS: End each content slide with a teaser that makes the reader swipe. "
            "Use a DIFFERENT open loop on each slide — never repeat the same phrase. "
            "Match the brand's tone.\n"
            + {
                "education": (
                    "  Examples: 'Most teams stop here. That's the mistake.', "
                    "'The data tells a different story.', 'But that's only half of it.'\n"
                ),
                "promotion": (
                    "  Examples: 'But the best part isn't the feature itself.', "
                    "'Wait until you see what it does with [X].', 'That's just the surface.'\n"
                ),
                "inspiration": (
                    "  Examples: 'Then everything changed.', "
                    "'That was the moment.', 'But the real test was still ahead.'\n"
                ),
                "behind_the_scenes": (
                    "  Examples: 'Here's what most people don't see.', "
                    "'This is where it almost fell apart.', 'The final step surprised us too.'\n"
                ),
                "user_generated": (
                    "  Examples: 'In their own words:', "
                    "'What happened next was unexpected.', 'That's when it clicked for them.'\n"
                ),
            }.get(_pillar, "  Examples: 'But that's only half of it.', 'Here's what changed.'\n")
            + f"  Slide {_spec.carousel_slide_count - 1}: Recap — summarize key points "
            "in a scannable format (short bullets or numbered list).\n"
            + f"  Slide {_spec.carousel_slide_count} (final): SHORT HEADLINE (≤50 chars) + "
            + {
                "education": "actionable step the reader can do TODAY + CTA (save/bookmark).\n",
                "promotion": "clear next step to try or buy + CTA (link/shop/try free).\n",
                "inspiration": "the takeaway lesson + CTA (share/tag someone who needs this).\n",
                "behind_the_scenes": "what's coming next or invitation to follow the journey + CTA (follow).\n",
                "user_generated": "the customer's recommendation in their voice + CTA (share your story).\n",
            }.get(_pillar, "clear takeaway + CTA.\n")
            + f"Label each slide clearly: 'Slide 1:', 'Slide 2:', ... 'Slide {_spec.carousel_slide_count}:'.\n"
            f"Write EXACTLY {_spec.carousel_slide_count} slides — each must carry a DISTINCT point.\n"
            "DATA & PROOF: Include at least one specific number, data point, or concrete example "
            "across the carousel. Use ONLY data from the brand profile or well-known facts. "
            "NEVER fabricate statistics.\n"
            "SUBSTANCE CHECK: If any slide could apply to every business in any industry, "
            "it's too generic. Rewrite with a specific detail, technique, or example.\n"
            "  BAD: 'Follow up with your leads consistently.'\n"
            "  GOOD: 'The 3-touch follow-up: Day 1 email, Day 3 value-add, Day 7 direct ask.'\n"
            "SLIDE HEADLINES — generic labels get zero engagement. Forbidden headline words:\n"
            "  Education: No 'Technique', 'Method', 'Concept', 'Strategy', 'Step N' as headline. "
            "Instead NAME the technique ('The 80/20 Rule', 'SCAMPER Method', 'Eisenhower Matrix').\n"
            "  Promotion: No 'Feature', 'Benefit', 'How It Works', 'Use Case'. "
            "Instead NAME the feature + benefit ('Offline Sync So You Never Lose Work').\n"
            "  Inspiration: No 'The Struggle', 'The Journey', 'The Breakthrough'. "
            "Instead NAME the specific moment ('The Pivot That Saved Everything').\n"
            "  Behind the scenes: No 'The Setup', 'The Process', 'The Result'. "
            "Instead NAME the actual task ('Building Our New Studio').\n"
            "  User generated: No 'The Customer', 'The Problem', 'The Solution'. "
            "Instead USE their name and context ('How Sarah Doubled Her Grant Success Rate')."
        ),
        "thread_hook": (
            "FORMAT: THREAD\n"
            "Write 3-7 posts (use as many as the content requires — every post must earn its place).\n"
            "  1/ Hook that stops the scroll. ALL hook rules above apply.\n"
            f"  Middle posts: One key point per post, concise and punchy. "
            f"Each post should {_pg({'education': 'teach a specific technique or principle', 'inspiration': 'advance a transformation narrative or motivational arc', 'promotion': 'showcase a distinct feature, benefit, or use case', 'behind_the_scenes': 'reveal a process step, team moment, or behind-the-curtain detail', 'user_generated': 'highlight a customer experience, community moment, or real result'}, 'deliver a specific insight or story beat')}. "
            "No filler — if a post doesn't add something new, cut it.\n"
            f"  Last post: A strong closing that {_pg({'education': 'gives an actionable takeaway the reader can use today', 'inspiration': 'lands the emotional payoff or transformation moment', 'promotion': 'makes the value proposition undeniable without a hard sell', 'behind_the_scenes': 'connects the process back to the audience or invites them in', 'user_generated': 'celebrates the community or invites others to share'}, 'delivers a final insight')} — NOT a brand pitch.\n"
            "Per-post limit: X = 280 chars, Bluesky = 300 chars.\n"
            "Separate each post with a blank line. Each must stand alone.\n"
            "Note: Bluesky threads don't need 1/2/3/ numbering. X threads use 1/ 2/ 3/."
        ),
        "blog_snippet": (
            "FORMAT: LinkedIn THOUGHT LEADERSHIP excerpt\n"
            "Write 150-200 words total:\n"
            f"  - Bold opening: {_pg({'education': 'opinion-forward statement or contrarian take on a common practice', 'inspiration': 'vivid transformation moment or aspirational statement', 'promotion': 'bold product/service claim or problem-solution hook', 'behind_the_scenes': 'candid reveal about how something actually works internally', 'user_generated': 'spotlight on a real customer moment or community insight'}, 'opinion-forward statement or contrarian question')}\n"
            "  - 2-3 short paragraphs expanding the idea with a real insight or example\n"
            "  - Closing question to spark discussion in the comments\n"
            "Professional but conversational tone."
        ),
        "story": (
            "FORMAT: Instagram/Facebook STORY\n"
            "Write ≤50 words total — short, punchy, immediate:\n"
            f"  - First line: {_pg({'education': 'surprising fact or quick tip hook', 'inspiration': 'big emotion or transformation moment', 'promotion': 'bold product claim or irresistible offer', 'behind_the_scenes': 'candid peek or you-were-not-supposed-to-see-this energy', 'user_generated': 'customer shoutout or community highlight'}, 'bold question or surprising statement')}\n"
            "  - One clear call to action (swipe up / reply / DM us)\n"
            "No hashtags in the body — add them in the HASHTAGS section only."
        ),
        "pin": (
            "FORMAT: Pinterest PIN\n"
            "Write as two clearly labeled parts:\n"
            f"  PIN TITLE: ≤100 chars, keyword-rich — {_pg({'education': 'lead with the technique or framework name', 'inspiration': 'lead with the transformation or aspirational outcome', 'promotion': 'lead with the product/service benefit', 'behind_the_scenes': 'lead with the process or behind-the-curtain angle', 'user_generated': 'lead with the customer story or community angle'}, 'compelling headline')}\n"
            f"  PIN DESCRIPTION: 200-250 chars, SEO-optimized — {_pg({'education': 'describe what the reader will learn and why it matters', 'inspiration': 'paint the before/after or aspirational vision', 'promotion': 'highlight key features and the problem they solve', 'behind_the_scenes': 'tease the process or reveal that makes people curious', 'user_generated': 'share the customer perspective and invite community'}, 'natural keywords describing the content')}\n"
            "No hashtags — use searchable keywords naturally."
        ),
        "video_first": (
            "FORMAT: VIDEO-FIRST POST\n"
            "The VIDEO is the content. Your caption is a teaser, not an article.\n"
            "LENGTH: 1-3 sentences MAX.\n"
            "- Instagram/TikTok Reels/YouTube Shorts: 50-150 chars ideal, 200 max. "
            "Caption appears ON TOP of the video — shorter is better.\n"
            "- LinkedIn/Facebook video: under 500 chars. Give a reason to press play.\n"
            f"Hook angle: {_pg({'education': 'tease the technique or the I-wish-I-knew-this-sooner moment', 'inspiration': 'tease the emotional payoff or transformation', 'promotion': 'tease the product reveal or result', 'behind_the_scenes': 'tease the behind-the-curtain moment people rarely see', 'user_generated': 'tease the customer reaction or real-world result'}, 'create curiosity about what happens in the video')}.\n"
            "Do NOT describe what happens in the video — create curiosity.\n"
            "Do NOT include a brand paragraph — the video speaks for the brand."
        ),
        "original": (
            "FORMAT: STANDARD POST (single image + caption)\n"
            "Structure:\n"
            "  - Hook: 1 sentence that stops the scroll — specific, mid-story, or contrarian. "
            "Must land BEFORE the platform fold. ALL hook rules above apply.\n"
            f"  - Body: 2-4 short paragraphs (1-2 sentences each for mobile readability). "
            f"{_pg({'education': 'Teach a specific technique, framework, or actionable method', 'inspiration': 'Tell a transformation story or paint an aspirational vision', 'promotion': 'Showcase features, benefits, or a compelling use case', 'behind_the_scenes': 'Reveal a real process, team moment, or workflow detail', 'user_generated': 'Highlight a customer experience, review, or community moment'}, 'Share a specific insight or tell a micro-story')}. "
            "Include at least one concrete detail (number, example, or named method).\n"
            "  - Close: CTA or takeaway matching the assigned cta_type. "
            "Make the CTA specific to the content topic — not generic.\n"
            "LENGTH: Instagram 150-300 words (hook ≤125 chars), "
            "LinkedIn 150-300 words (hook ≤140 chars), "
            "Facebook 100-250 words (hook ≤140 chars), "
            "TikTok under 500 chars, Threads 200-500 chars, "
            "X under 280 chars (single punchy thought), "
            "Bluesky under 300 chars, Mastodon under 500 chars, "
            "YouTube Shorts under 300 chars.\n"
            "Do NOT write a brand paragraph. The image supports the caption."
        ),
    }
    derivative_instruction = _DERIVATIVE_INSTRUCTIONS.get(derivative_type, "")

    # Thin-profile overrides: redirect "be specific" away from client stories
    if derivative_instruction and (_proof_tier in ("thin_profile",) or not _story_details):
        _THIN_PROFILE_OVERRIDES: dict[str, str] = {
            "carousel": (
                "\nTHIN-PROFILE OVERRIDE (this brand has NO client data):\n"
                + {
                    "education": (
                        "  Content slides: Teach CONCRETE TECHNIQUES — step-by-step methods, "
                        "specific rules of thumb, or named frameworks. "
                        "Do NOT invent client stories, dollar amounts, or case studies.\n"
                        "  DATA OVERRIDE: Data points are OPTIONAL. Teaching depth IS your proof.\n"
                        "  Final slide: ONE thing they can do TODAY. "
                        "Do NOT say 'Book a consultation' unless CTA type is 'conversion'.\n"
                        "  SUBSTANCE means TEACHING DEPTH, not brand-specific claims."
                    ),
                    "promotion": (
                        "  Content slides: Focus on FEATURES and USE CASES — what the product does "
                        "and how it works. Do NOT invent customer testimonials or sales figures.\n"
                        "  Final slide: Direct the reader to try, explore, or learn more.\n"
                        "  SUBSTANCE means FEATURE SPECIFICITY, not social proof."
                    ),
                    "inspiration": (
                        "  Content slides: Tell a PLAUSIBLE transformation story grounded in the "
                        "brand's mission/values. Do NOT fabricate specific people or outcomes.\n"
                        "  Use the brand's own journey or industry-wide patterns as the story.\n"
                        "  SUBSTANCE means EMOTIONAL SPECIFICITY, not invented case studies."
                    ),
                    "behind_the_scenes": (
                        "  Content slides: Describe REALISTIC process details — tools, workflows, "
                        "decisions. You MAY say 'our team' and 'we' for BTS content.\n"
                        "  Do NOT claim client counts or revenue figures.\n"
                        "  SUBSTANCE means PROCESS DETAIL, not volume claims."
                    ),
                    "user_generated": (
                        "  Content slides: Frame as a TEMPLATE for customer stories without "
                        "fabricating specific customers. Use 'Imagine a customer who...' framing "
                        "or focus on the product experience.\n"
                        "  SUBSTANCE means AUTHENTIC VOICE, not invented testimonials."
                    ),
                }.get(_pillar, (
                    "  Do NOT invent client stories, dollar amounts, or case studies.\n"
                    "  SUBSTANCE means SPECIFICITY appropriate to the content type."
                ))
            ),
            "blog_snippet": (
                "\nTHIN-PROFILE OVERRIDE (this brand has NO client data):\n"
                f"  {_pg({'education': 'Your insight must be a TECHNIQUE or INDUSTRY FACT the reader can apply', 'inspiration': 'Ground your story in universal experiences — no fabricated transformations', 'promotion': 'Focus on the product/service itself — features, design, how it works. No invented testimonials', 'behind_the_scenes': 'Show real process and workflow — no claims about client volume or business scale', 'user_generated': 'Use hypothetical framing or invite stories — do not fabricate customer quotes'}, 'Lead with teaching depth — not brand-specific claims')}.\n"
                "  Do NOT reference clients, outcomes, or volume in any form."
            ),
            "thread_hook": (
                "\nTHIN-PROFILE OVERRIDE (this brand has NO client data):\n"
                f"  Each post must stand on {_pg({'education': 'a TECHNIQUE, FACT, or FRAMEWORK', 'inspiration': 'a universal truth or relatable moment', 'promotion': 'a product feature, benefit, or design detail', 'behind_the_scenes': 'a real process step or team workflow', 'user_generated': 'a community-focused prompt or hypothetical scenario'}, 'concrete substance')} — not a client story.\n"
                "  Do NOT reference clients, outcomes, or volume in any form."
            ),
            "original": (
                "\nTHIN-PROFILE OVERRIDE (this brand has NO client data):\n"
                f"  Body content must be grounded in {_pg({'education': 'specific techniques and actionable methods', 'inspiration': 'universal experiences and relatable moments', 'promotion': 'product/service features and how they work', 'behind_the_scenes': 'real process details and team workflows', 'user_generated': 'community prompts or hypothetical scenarios'}, 'concrete, verifiable substance')}.\n"
                "  Do NOT reference clients, outcomes, or volume in any form."
            ),
            "video_first": (
                "\nTHIN-PROFILE OVERRIDE (this brand has NO client data):\n"
                "  Do NOT reference client results or testimonials in the caption.\n"
                "  Let the video content speak — caption should only create curiosity."
            ),
        }
        _override = _THIN_PROFILE_OVERRIDES.get(derivative_type, "")
        if _override:
            derivative_instruction += _override

    _spec = get_platform(platform)
    platform_format = _spec.content_prompt
    # Derivative-type overrides for aspect ratio (e.g. story → 9:16, pin → 2:3)
    _DERIVATIVE_ASPECTS: dict[str, str] = {
        "story": "9:16",
        "pin": "2:3",
        "blog_snippet": "1.91:1",
    }
    # Platform-specific carousel aspect ratios
    _CAROUSEL_ASPECTS: dict[str, str] = {
        "instagram": "4:5",
        "linkedin": "1:1",
        "tiktok": "9:16",
        "facebook": "1:1",
        "x": "1:1",
    }
    # Platform-specific standard post aspect overrides
    _STANDARD_POST_ASPECTS: dict[str, str] = {
        "instagram": "4:5",
        "linkedin": "1:1",
        "x": "16:9",
    }
    if derivative_type == "carousel":
        _aspect = _CAROUSEL_ASPECTS.get(platform, _spec.image_aspect)
    elif derivative_type in _DERIVATIVE_ASPECTS:
        _aspect = _DERIVATIVE_ASPECTS[derivative_type]
    else:
        _aspect = _STANDARD_POST_ASPECTS.get(platform, _spec.image_aspect)
    aspect_hint = f"Generate a {_aspect} aspect ratio image." if _aspect != "1:1" else ""

    # Live platform trend intelligence (from strategy Phase 0)
    platform_trends = day_brief.get("platform_trends")
    trend_block = ""
    if platform_trends:
        trending_formats = platform_trends.get("trending_formats", [])
        trending_hooks = platform_trends.get("trending_hooks", [])
        algo_notes = platform_trends.get("algorithm_notes", "")
        if trending_formats or algo_notes:
            trend_block = (
                f"\nLIVE PLATFORM INTELLIGENCE ({platform.upper()}):\n"
                f"- What's working now: {', '.join(trending_formats[:3])}\n"
                f"- Trending hooks: {', '.join(trending_hooks[:3])}\n"
                f"- Algorithm notes: {algo_notes}\n"
                "Use this intelligence to make the content more relevant and algorithm-friendly.\n"
            )
    instruction_hint = (
        f"\n\nAdditional instructions for this generation: {instructions.strip()}"
        if instructions and instructions.strip()
        else ""
    )

    # ── BYOP mode ─────────────────────────────────────────────────────────────
    if custom_photo_bytes:
        yield {"event": "status", "data": {"message": "Analyzing your photo..."}}

        _voice_directive = f"\n{platform.upper()} VOICE: {_spec.voice}\n" if _spec.voice else ""
        byop_prompt = f"""You are a {platform} content specialist for {industry} brands. You write for {business_name}, targeting {target_audience}.
{_voice_directive}
Brand tone: {tone}
Visual style: {visual_style}
{caption_style_directive}
{social_voice_block}{f"CONTENT FORMAT:{chr(10)}{derivative_instruction}{chr(10)}" if derivative_instruction else ""}{f"{platform_format}{chr(10)}" if platform_format else ""}
{_build_dedup_block(prior_hooks)}Analyze this photo and write a {platform} post caption that:
- Complements and describes what's in the photo
- Fits the "{content_theme}" theme for the "{pillar}" content pillar
- Hook direction: "{caption_hook}" — use this ANGLE but rewrite it to be specific and surprising
- Carries this key message: {key_message}
{instruction_hint}

{_QUALITY_BLOCK}
{_HOOK_BLOCK}
{_hook_context}{_storytelling_block}
{_social_proof_guard}{_SELF_REVIEW_CHECKLIST}{_char_limit_reminder}
{_social_proof_checklist_item}{_cta_block}
After the caption, add relevant hashtags on a new line starting with HASHTAGS:
CRITICAL: Only output real hashtags. Never convert sentence fragments into hashtags.
"""

        try:
            image_part = types.Part(
                inline_data=types.Blob(data=custom_photo_bytes, mime_type=custom_photo_mime)
            )
            text_part = types.Part(text=byop_prompt)

            response = await asyncio.to_thread(
                get_genai_client().models.generate_content,
                model=GEMINI_MODEL,
                contents=[image_part, text_part],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT"],
                    temperature=0.7,
                ),
            )

            full_text = "".join(
                part.text for part in response.candidates[0].content.parts if part.text
            )

            if "HASHTAGS:" in full_text:
                caption_part, hashtag_part = full_text.split("HASHTAGS:", 1)
                full_caption = caption_part.strip()
                raw_tags = hashtag_part.strip().replace("\n", " ")
                parsed_hashtags = _sanitize_hashtags(
                    [t.strip() for t in raw_tags.split() if t.strip()],
                    platform,
                )
            else:
                full_caption = full_text.strip()
                parsed_hashtags = hashtags_hint

            # Save the user's photo under the post's GCS path
            yield {"event": "status", "data": {"message": "Saving your photo..."}}
            image_url = None
            image_gcs_uri = None
            try:
                image_url, image_gcs_uri = await upload_image_to_gcs(
                    custom_photo_bytes, custom_photo_mime, post_id
                )
                yield {
                    "event": "image",
                    "data": {"url": image_url, "mime_type": custom_photo_mime, "gcs_uri": image_gcs_uri},
                }
            except Exception as upload_err:
                logger.error("BYOP photo upload failed: %s", upload_err)
                b64 = base64.b64encode(custom_photo_bytes).decode()
                image_url = f"data:{custom_photo_mime};base64,{b64}"
                yield {
                    "event": "image",
                    "data": {
                        "url": image_url,
                        "mime_type": custom_photo_mime,
                        "fallback": True,
                    },
                }

            final_caption = await _smart_condense(_strip_markdown(full_caption), platform, derivative_type)
            final_caption = await _quality_retry(final_caption, platform, derivative_type)

            # ── Review gate — hold caption until 7+ ──
            yield {"event": "status", "data": {"message": "Reviewing content..."}}
            final_caption, parsed_hashtags, _gate_review = await _review_gate(
                final_caption, parsed_hashtags, platform, derivative_type, brand_profile, day_brief,
            )
            _gate_score = (_gate_review or {}).get("score", 0)

            # ── Attempt 3: full regeneration if review gate exhausted ──
            if _gate_score < 7:
                logger.warning("Full regeneration triggered (gate score=%d) for BYOP %s/%s",
                               _gate_score, platform, derivative_type)
                yield {"event": "status", "data": {"message": "Regenerating content..."}}
                try:
                    regen_response = await asyncio.to_thread(
                        get_genai_client().models.generate_content,
                        model=GEMINI_MODEL,
                        contents=[image_part, text_part],
                        config=types.GenerateContentConfig(temperature=0.8),
                    )
                    regen_text = "".join(
                        p.text for p in regen_response.candidates[0].content.parts if p.text
                    )
                    if "HASHTAGS:" in regen_text:
                        regen_cap, regen_ht = regen_text.split("HASHTAGS:", 1)
                        regen_caption = _strip_markdown(_fix_mojibake(regen_cap.strip()))
                        regen_hashtags = _sanitize_hashtags(
                            [t.strip() for t in regen_ht.strip().split() if t.strip()], platform
                        )
                    else:
                        regen_caption = _strip_markdown(_fix_mojibake(regen_text.strip()))
                        regen_hashtags = parsed_hashtags

                    regen_caption = await _smart_condense(regen_caption, platform, derivative_type)
                    regen_caption = await _quality_retry(regen_caption, platform, derivative_type)

                    _story = brand_profile.get("storytelling_strategy", {})
                    _proof_tier_r = _story.get("social_proof_tier") if isinstance(_story, dict) else None
                    _cta_type_r = day_brief.get("cta_type")
                    regen_review = await review_post(
                        {"caption": regen_caption, "hashtags": regen_hashtags,
                         "platform": platform, "derivative_type": derivative_type,
                         "pillar": day_brief.get("pillar", "education"),
                         "content_theme": day_brief.get("content_theme", "")},
                        brand_profile,
                        social_proof_tier=_proof_tier_r, cta_type=_cta_type_r,
                    )
                    regen_score = regen_review.get("score", 0)
                    logger.info("BYOP full regeneration score: %d for %s/%s", regen_score, platform, derivative_type)
                    if regen_score > _gate_score:
                        final_caption = regen_caption
                        parsed_hashtags = regen_hashtags
                        _gate_review = regen_review
                        logger.info("BYOP full regeneration improved score: %d -> %d", _gate_score, regen_score)
                except Exception as regen_err:
                    logger.warning("BYOP full regeneration failed (non-fatal): %s", regen_err)

            final_caption = _enforce_char_limit(final_caption, platform, derivative_type)  # safety net
            _validate_format(final_caption, derivative_type)

            # Yield reviewed caption so frontend displays it just before "complete"
            yield {
                "event": "caption",
                "data": {"text": final_caption, "chunk": False, "hashtags": parsed_hashtags},
            }
            yield {
                "event": "complete",
                "data": {
                    "post_id": post_id,
                    "caption": final_caption,
                    "hashtags": parsed_hashtags,
                    "image_url": image_url,
                    "image_gcs_uri": image_gcs_uri,
                    **({"review": _gate_review} if _gate_review else {}),
                },
            }

        except Exception as e:
            logger.error("BYOP generation error for post %s: %s", post_id, e)
            yield {"event": "error", "data": {"message": str(e)}}

        return  # Do not fall through to normal generation

    # ── Video-first mode (text-only caption, no image generation) ──────────────
    if derivative_type == "video_first":
        yield {"event": "status", "data": {"message": f"Writing {platform} video caption..."}}

        _voice_directive = f"\n{platform.upper()} VOICE: {_spec.voice}\n" if _spec.voice else ""
        video_prompt = f"""You are a {platform} content specialist for {industry} brands. You write for {business_name}, targeting {target_audience}.
{_voice_directive}
Brand tone: {tone}
{caption_style_directive}
{social_voice_block}{f"CONTENT FORMAT:{chr(10)}{derivative_instruction}{chr(10)}" if derivative_instruction else ""}{f"{platform_format}{chr(10)}" if platform_format else ""}{trend_block}
{_build_dedup_block(prior_hooks)}Create a {platform} video-first post for the "{pillar}" content pillar on the theme: "{content_theme}".

Hook direction: "{caption_hook}" — use this ANGLE but rewrite it to be specific and surprising.
Key message: {key_message}

Write a compelling caption to accompany a video clip. The video is the main content — the caption supports it.
{instruction_hint}

{_QUALITY_BLOCK}
{_HOOK_BLOCK}
{_hook_context}{_storytelling_block}
{_social_proof_guard}{_SELF_REVIEW_CHECKLIST}{_char_limit_reminder}
{_social_proof_checklist_item}{_cta_block}
After the caption, add relevant hashtags on a new line starting with HASHTAGS:
CRITICAL: Only output real hashtags. Never convert sentence fragments into hashtags.
"""

        try:
            response = await asyncio.to_thread(
                get_genai_client().models.generate_content,
                model=GEMINI_MODEL,
                contents=video_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT"],
                    temperature=0.7,
                ),
            )

            full_text = "".join(
                part.text for part in response.candidates[0].content.parts if part.text
            )

            if "HASHTAGS:" in full_text:
                caption_part, hashtag_part = full_text.split("HASHTAGS:", 1)
                full_caption = caption_part.strip()
                raw_tags = hashtag_part.strip().replace("\n", " ")
                parsed_hashtags = _sanitize_hashtags(
                    [t.strip() for t in raw_tags.split() if t.strip()],
                    platform,
                )
            else:
                full_caption = full_text.strip()
                parsed_hashtags = _sanitize_hashtags(hashtags_hint, platform)

            final_caption = await _smart_condense(_strip_markdown(full_caption), platform, derivative_type)
            final_caption = await _quality_retry(final_caption, platform, derivative_type)

            # ── Review gate — hold caption until 7+ ──
            yield {"event": "status", "data": {"message": "Reviewing content..."}}
            final_caption, parsed_hashtags, _gate_review = await _review_gate(
                final_caption, parsed_hashtags, platform, derivative_type, brand_profile, day_brief,
            )
            _gate_score = (_gate_review or {}).get("score", 0)

            # ── Attempt 3: full regeneration if review gate exhausted ──
            if _gate_score < 7:
                logger.warning("Full regeneration triggered (gate score=%d) for video_first %s/%s",
                               _gate_score, platform, derivative_type)
                yield {"event": "status", "data": {"message": "Regenerating content..."}}
                try:
                    regen_response = await asyncio.to_thread(
                        get_genai_client().models.generate_content,
                        model=GEMINI_MODEL,
                        contents=video_prompt,
                        config=types.GenerateContentConfig(temperature=0.8),
                    )
                    regen_text = "".join(
                        p.text for p in regen_response.candidates[0].content.parts if p.text
                    )
                    if "HASHTAGS:" in regen_text:
                        regen_cap, regen_ht = regen_text.split("HASHTAGS:", 1)
                        regen_caption = _strip_markdown(_fix_mojibake(regen_cap.strip()))
                        regen_hashtags = _sanitize_hashtags(
                            [t.strip() for t in regen_ht.strip().split() if t.strip()], platform
                        )
                    else:
                        regen_caption = _strip_markdown(_fix_mojibake(regen_text.strip()))
                        regen_hashtags = parsed_hashtags

                    regen_caption = await _smart_condense(regen_caption, platform, derivative_type)
                    regen_caption = await _quality_retry(regen_caption, platform, derivative_type)

                    _story = brand_profile.get("storytelling_strategy", {})
                    _proof_tier_r = _story.get("social_proof_tier") if isinstance(_story, dict) else None
                    _cta_type_r = day_brief.get("cta_type")
                    regen_review = await review_post(
                        {"caption": regen_caption, "hashtags": regen_hashtags,
                         "platform": platform, "derivative_type": derivative_type,
                         "pillar": day_brief.get("pillar", "education"),
                         "content_theme": day_brief.get("content_theme", "")},
                        brand_profile,
                        social_proof_tier=_proof_tier_r, cta_type=_cta_type_r,
                    )
                    regen_score = regen_review.get("score", 0)
                    logger.info("Video-first full regeneration score: %d for %s/%s", regen_score, platform, derivative_type)
                    if regen_score > _gate_score:
                        final_caption = regen_caption
                        parsed_hashtags = regen_hashtags
                        _gate_review = regen_review
                        logger.info("Video-first full regeneration improved score: %d -> %d", _gate_score, regen_score)
                except Exception as regen_err:
                    logger.warning("Video-first full regeneration failed (non-fatal): %s", regen_err)

            final_caption = _enforce_char_limit(final_caption, platform, derivative_type)  # safety net
            _validate_format(final_caption, derivative_type)

            yield {
                "event": "caption",
                "data": {"text": final_caption, "chunk": False, "hashtags": parsed_hashtags},
            }
            yield {
                "event": "complete",
                "data": {
                    "post_id": post_id,
                    "caption": final_caption,
                    "hashtags": parsed_hashtags,
                    "image_url": None,
                    "image_gcs_uri": None,
                    "awaiting_video": True,
                    **({"review": _gate_review} if _gate_review else {}),
                },
            }

        except Exception as e:
            logger.error("Video-first generation error for post %s: %s", post_id, e)
            yield {"event": "error", "data": {"message": str(e)}}

        return  # Skip image generation entirely

    # ── Normal mode (interleaved TEXT + IMAGE) ────────────────────────────────

    # Check budget
    if not bt.budget_tracker.can_generate_image():
        yield {"event": "error", "data": {"message": "Image budget exhausted"}}
        return

    yield {"event": "status", "data": {"message": f"Crafting {platform} post..."}}

    color_hint = f"Brand colors: {', '.join(colors[:3])}." if colors else ""
    style_ref_block = (
        "VISUAL CONSISTENCY: The provided reference image shows this brand's visual identity — "
        "color palette, lighting style, and mood. Every image you generate must feel cohesive "
        "with this reference. Match the warmth, saturation, and composition style exactly.\n"
    ) if style_reference_gcs_uri else ""
    _voice_directive = f"\n{platform.upper()} VOICE: {_spec.voice}\n" if _spec.voice else ""
    prompt = f"""You are a {platform} content specialist for {industry} brands. You write for {business_name}, targeting {target_audience}.
{_voice_directive}
Brand tone: {tone}
Visual style: {visual_style}
{caption_style_directive}
{social_voice_block}{image_style_directive}
{style_ref_block}{f"CONTENT FORMAT:{chr(10)}{derivative_instruction}{chr(10)}" if derivative_instruction else ""}{f"{platform_format}{chr(10)}" if platform_format else ""}{trend_block}
{_build_dedup_block(prior_hooks)}Create a {platform} post for the "{pillar}" content pillar on the theme: "{content_theme}".

Hook direction: "{caption_hook}" — use this ANGLE but rewrite it to be specific and surprising.
Key message: {key_message}

Write the caption (following the format above if specified), engaging and on-brand.
{instruction_hint}

{_QUALITY_BLOCK}
{_HOOK_BLOCK}
{_hook_context}{_storytelling_block}
{_social_proof_guard}{_SELF_REVIEW_CHECKLIST}{_char_limit_reminder}
{_social_proof_checklist_item}{_cta_block}
After the caption, add relevant hashtags on a new line starting with HASHTAGS:
CRITICAL: Only output real hashtags. Never convert sentence fragments into hashtags.
"""

    full_caption = ""
    image_bytes = None
    image_mime = "image/png"
    image_url = None
    image_gcs_uri = None
    cover_raw_bytes = None
    parsed_hashtags = None

    # Build multimodal contents: text prompt + brand reference images
    contents: list = [prompt]
    try:
        brand_refs = await get_brand_reference_images(brand_profile, max_images=3)
        if brand_refs:
            contents.append(
                "\nThe following images are brand reference assets (logo, product photos, "
                "style references). Use them to ensure the generated image is visually "
                "consistent with this brand's identity. Do NOT reproduce logos or text — "
                "use them only as visual style and color references."
            )
            for ref_bytes, ref_mime in brand_refs:
                contents.append(types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime))
            logger.info("Passing %d brand reference images to Gemini", len(brand_refs))
    except Exception as e:
        logger.warning("Failed to load brand reference images: %s", e)

    try:
        # ── Step 1: Text-only caption generation (GEMINI_MODEL — faster, cheaper) ──
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7),
        )

        for part in response.candidates[0].content.parts:
            if part.text:
                text = part.text
                if "HASHTAGS:" in text:
                    caption_part, hashtag_part = text.split("HASHTAGS:", 1)
                    full_caption += caption_part.strip()
                    raw_tags = hashtag_part.strip().replace("\n", " ")
                    parsed_hashtags = _sanitize_hashtags(
                        [t.strip() for t in raw_tags.split() if t.strip()],
                        platform,
                    )
                else:
                    full_caption += text

        final_hashtags = parsed_hashtags if parsed_hashtags else hashtags_hint
        # Fix mojibake, strip markdown, smart condense if over limit
        final_caption = _fix_mojibake(full_caption.strip())
        final_caption = await _smart_condense(_strip_markdown(final_caption), platform, derivative_type)

        # Format validation with 1 retry — caption only
        if not _validate_format(final_caption, derivative_type) and derivative_type in ("carousel", "thread_hook", "pin"):
            logger.info("Format validation failed for %s post %s — retrying caption only", derivative_type, post_id)
            yield {"event": "status", "data": {"message": f"Refining {derivative_type} format..."}}
            retry_prompt = (
                f"This caption FAILED format validation for {derivative_type.upper()}.\n\n"
                f"FORMAT RULES (you MUST follow these EXACTLY):\n{derivative_instruction}\n\n"
                f"ORIGINAL (BAD FORMAT):\n{final_caption}\n\n"
                f"Rewrite following the format rules. Same message, tone, and hook — fix the STRUCTURE ONLY.\n"
            )
            if derivative_type == "carousel":
                _slide_labels = ", ".join(f"'Slide {i+1}:'" for i in range(_spec.carousel_slide_count))
                retry_prompt += (
                    f"You MUST include {_slide_labels} labels. "
                    "Each slide MUST start on its own line with that exact label.\n"
                )
            elif derivative_type == "thread_hook":
                retry_prompt += (
                    "You MUST number each tweet as '1/', '2/', '3/' at the START of each segment. "
                    "Each numbered tweet MUST start on its own line.\n"
                )
            retry_prompt += "After the caption, add relevant hashtags on a new line starting with HASHTAGS:"
            try:
                retry_response = await asyncio.to_thread(
                    get_genai_client().models.generate_content,
                    model=GEMINI_MODEL,
                    contents=retry_prompt,
                    config=types.GenerateContentConfig(temperature=0.4),
                )
                retry_text = ""
                for rpart in retry_response.candidates[0].content.parts:
                    if rpart.text:
                        retry_text += rpart.text
                if retry_text.strip():
                    if "HASHTAGS:" in retry_text:
                        cap_part, ht_part = retry_text.split("HASHTAGS:", 1)
                        final_caption = _enforce_char_limit(_strip_markdown(cap_part.strip()), platform, derivative_type)
                        retry_tags = _sanitize_hashtags(
                            [t.strip() for t in ht_part.strip().split() if t.strip()],
                            platform,
                        )
                        if retry_tags:
                            final_hashtags = retry_tags
                    else:
                        final_caption = _enforce_char_limit(_strip_markdown(retry_text.strip()), platform, derivative_type)
                    logger.info("Format retry produced new caption for post %s", post_id)
            except Exception as retry_err:
                logger.warning("Format retry failed for post %s: %s — using original caption", post_id, retry_err)

        # Quality safety net — one targeted retry for literal violations
        final_caption = await _quality_retry(final_caption, platform, derivative_type)

        # ── Step 2: Review gate — hold caption until 7+ ──
        yield {"event": "status", "data": {"message": "Reviewing content..."}}
        final_caption, final_hashtags, _gate_review = await _review_gate(
            final_caption, final_hashtags, platform, derivative_type, brand_profile, day_brief,
        )
        _gate_score = (_gate_review or {}).get("score", 0)

        # ── Attempt 3: full regeneration if review gate exhausted ──
        if _gate_score < 7:
            logger.warning("Full regeneration triggered (gate score=%d) for %s/%s",
                           _gate_score, platform, derivative_type)
            yield {"event": "status", "data": {"message": "Regenerating content..."}}
            try:
                regen_response = await asyncio.to_thread(
                    get_genai_client().models.generate_content,
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.8),
                )
                regen_text = regen_response.text.strip()
                if "HASHTAGS:" in regen_text:
                    regen_cap, regen_ht = regen_text.split("HASHTAGS:", 1)
                    regen_caption = _strip_markdown(_fix_mojibake(regen_cap.strip()))
                    regen_hashtags = _sanitize_hashtags(
                        [t.strip() for t in regen_ht.strip().split() if t.strip()], platform
                    )
                else:
                    regen_caption = _strip_markdown(_fix_mojibake(regen_text))
                    regen_hashtags = final_hashtags

                regen_caption = await _smart_condense(regen_caption, platform, derivative_type)
                regen_caption = await _quality_retry(regen_caption, platform, derivative_type)

                _story = brand_profile.get("storytelling_strategy", {})
                _proof_tier_r = _story.get("social_proof_tier") if isinstance(_story, dict) else None
                _cta_type_r = day_brief.get("cta_type")
                regen_for_review = {
                    "caption": regen_caption, "hashtags": regen_hashtags,
                    "platform": platform, "derivative_type": derivative_type,
                    "pillar": day_brief.get("pillar", "education"),
                }
                regen_review = await review_post(
                    regen_for_review, brand_profile,
                    social_proof_tier=_proof_tier_r, cta_type=_cta_type_r,
                )
                regen_score = regen_review.get("score", 0)
                logger.info("Full regeneration score: %d for %s/%s", regen_score, platform, derivative_type)

                if regen_score > _gate_score:
                    final_caption = regen_caption
                    final_hashtags = regen_hashtags
                    _gate_review = regen_review
                    logger.info("Full regeneration improved score: %d -> %d", _gate_score, regen_score)
            except Exception as regen_err:
                logger.warning("Full regeneration failed (non-fatal): %s", regen_err)

        final_caption = _enforce_char_limit(final_caption, platform, derivative_type)  # safety net

        # Yield reviewed caption so frontend can display it just before "complete"
        yield {
            "event": "caption",
            "data": {"text": final_caption, "chunk": False, "hashtags": final_hashtags},
        }

        # ── Step 3: Image generation (after review gate passes) ──
        yield {"event": "status", "data": {"message": "Generating image..."}}

        # Load brand reference images for visual consistency
        img_contents: list = []
        try:
            brand_refs = await get_brand_reference_images(brand_profile, max_images=3)
            if brand_refs:
                for ref_bytes, ref_mime in brand_refs:
                    img_contents.append(types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime))
                logger.info("Passing %d brand reference images for image generation", len(brand_refs))
        except Exception as e:
            logger.warning("Failed to load brand reference images: %s", e)

        # Resolve image style: per-post override > brand default > photorealistic
        _image_style = _get_image_style(
            image_style_key or brand_profile.get("default_image_style")
        )
        img_prompt = _build_image_prompt(
            platform=platform,
            style=_image_style,
            enhanced_image_prompt=image_prompt,
            image_style_directive=image_style_directive,
            color_hint=color_hint,
            style_ref_block=style_ref_block,
            aspect=_aspect,
            derivative_type=derivative_type,
        )
        img_contents.insert(0, img_prompt)

        try:
            image_bytes, image_mime = await _generate_image_with_retry(img_contents)

            if image_bytes:
                # Post-processing: resize + platform-specific text overlay
                try:
                    image_bytes = resize_to_aspect(image_bytes, _aspect)
                    cover_raw_bytes = image_bytes  # preserve pre-overlay copy for slide style reference
                    if derivative_type == "carousel":
                        image_bytes = create_carousel_cover(
                            image_bytes, content_theme or caption_hook, colors, _aspect)
                    elif platform == "pinterest":
                        image_bytes = create_pinterest_pin(
                            image_bytes, content_theme, key_message[:80], colors)
                    elif platform in ("tiktok", "youtube_shorts"):
                        image_bytes = create_tiktok_cover(
                            image_bytes, caption_hook or content_theme, colors)
                    # Standard posts (IG, LI, FB, X, Threads, Mastodon, Bluesky): no text overlay
                    image_mime = "image/png"
                except Exception as pp_err:
                    logger.warning("Image post-processing failed (non-fatal): %s", pp_err)

                # Generate alt-text for accessibility-first platforms
                alt_text = await _generate_alt_text(image_bytes, content_theme, platform)

                try:
                    image_url, image_gcs_uri = await upload_image_to_gcs(image_bytes, image_mime, post_id)
                    bt.budget_tracker.record_image()
                    _img_event_data = {"url": image_url, "mime_type": image_mime, "gcs_uri": image_gcs_uri}
                    if alt_text:
                        _img_event_data["alt_text"] = alt_text
                    yield {
                        "event": "image",
                        "data": _img_event_data,
                    }
                except Exception as upload_err:
                    logger.error("Image upload failed: %s", upload_err)
                    b64 = base64.b64encode(image_bytes).decode()
                    yield {
                        "event": "image",
                        "data": {
                            "url": f"data:{image_mime};base64,{b64}",
                            "mime_type": image_mime,
                            "fallback": True,
                        }
                    }
            else:
                logger.error("Image generation returned no image for post %s", post_id)
        except Exception as img_err:
            logger.error("Image generation failed for post %s: %s", post_id, img_err)

        # ── Init image URL lists (carousel slides appended below) ──
        all_image_urls: list[str] = []
        all_image_gcs_uris: list[str] = []
        if image_url:
            all_image_urls.append(image_url)
        if image_gcs_uri:
            all_image_gcs_uris.append(image_gcs_uri)

        # ── Carousel: generate additional slide images ──
        if derivative_type == "carousel" and final_caption:
            slide_descriptions = _parse_slide_descriptions(final_caption, max_slides=_spec.carousel_slide_count)
            if len(slide_descriptions) > 1:
                yield {"event": "status", "data": {"message": "Generating carousel slides..."}}
                extra_slides = await _generate_carousel_images(
                    slide_descriptions,
                    business_name=business_name,
                    visual_style=visual_style,
                    color_hint=color_hint,
                    image_style_directive=image_style_directive,
                    style_ref_block=style_ref_block,
                    platform=platform,
                    post_id=post_id,
                    cover_image_bytes=cover_raw_bytes,
                    image_style=_image_style,
                )
                for slide_idx, (slide_bytes, slide_mime) in enumerate(extra_slides):
                    # Post-process each slide: resize + number badge + title
                    try:
                        slide_bytes = resize_to_aspect(slide_bytes, _aspect)
                        _slide_title = _extract_slide_headline(slide_descriptions[slide_idx + 1]) if slide_idx + 1 < len(slide_descriptions) else ""
                        # Final slide: if headline was truncated with ellipsis, use clean fallback
                        if slide_idx + 2 == len(slide_descriptions) and _slide_title.endswith('…'):
                            _slide_title = "Your Next Step"
                        slide_bytes = create_carousel_slide(
                            slide_bytes, _slide_title, colors, _aspect)
                        slide_mime = "image/png"
                    except Exception as pp_err:
                        logger.warning("Carousel slide post-processing failed: %s", pp_err)
                    try:
                        slide_url, slide_gcs = await upload_image_to_gcs(slide_bytes, slide_mime, post_id)
                        bt.budget_tracker.record_image()
                        all_image_urls.append(slide_url)
                        all_image_gcs_uris.append(slide_gcs)
                        yield {
                            "event": "image",
                            "data": {"url": slide_url, "mime_type": slide_mime, "gcs_uri": slide_gcs}
                        }
                    except Exception as upload_err:
                        logger.error("Carousel slide upload failed: %s", upload_err)

                # Re-render cover with actual Slide 1 hook text (fixes cover/caption mismatch)
                if slide_descriptions and cover_raw_bytes:
                    try:
                        _cover_hook = _extract_slide_headline(slide_descriptions[0])
                        if _cover_hook and _cover_hook != (content_theme or caption_hook):
                            _new_cover = create_carousel_cover(cover_raw_bytes, _cover_hook, colors, _aspect)
                            _cover_url, _cover_gcs = await upload_image_to_gcs(_new_cover, "image/png", post_id)
                            if all_image_urls:
                                all_image_urls[0] = _cover_url
                            if all_image_gcs_uris:
                                all_image_gcs_uris[0] = _cover_gcs
                            image_url = _cover_url
                            image_gcs_uri = _cover_gcs
                            yield {"event": "image_update", "data": {"index": 0, "url": _cover_url, "mime_type": "image/png", "gcs_uri": _cover_gcs}}
                    except Exception as cover_err:
                        logger.warning("Cover re-render failed (non-fatal): %s", cover_err)

        yield {
            "event": "complete",
            "data": {
                "post_id": post_id,
                "caption": final_caption,
                "hashtags": final_hashtags,
                "image_url": image_url,
                "image_gcs_uri": image_gcs_uri,
                "image_urls": all_image_urls,
                "image_gcs_uris": all_image_gcs_uris,
                **({"review": _gate_review} if _gate_review else {}),
            }
        }

    except Exception as e:
        logger.error("Content generation error for post %s: %s", post_id, e)
        yield {"event": "error", "data": {"message": str(e)}}
