import asyncio
import base64
import logging
import re
from typing import AsyncIterator

from google import genai
from google.genai import types

from backend.config import GOOGLE_API_KEY, GEMINI_MODEL
from backend.platforms import get as get_platform

# Interleaved text+image generation requires an image-capable model
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
from backend.services import budget_tracker as bt
from backend.services.storage_client import upload_image_to_gcs
from backend.services.brand_assets import get_brand_reference_images

logger = logging.getLogger(__name__)
client = genai.Client(api_key=GOOGLE_API_KEY)

# Common English stopwords that should never be hashtags
_HASHTAG_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "is", "it", "by", "as", "be", "was", "are", "has", "had", "do",
    "if", "my", "me", "we", "he", "she", "no", "so", "up", "out", "not",
    "you", "your", "our", "its", "his", "her", "this", "that", "with",
    "from", "here", "heres", "image", "post", "caption",
})

_VALID_HASHTAG_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _enforce_char_limit(caption: str, platform: str) -> str:
    """Truncate caption to the platform's hard character limit if set."""
    spec = get_platform(platform)
    limit = spec.hard_char_limit
    if not limit or len(caption) <= limit:
        return caption
    truncated = caption[: limit - 1]
    last_space = truncated.rfind(" ")
    if last_space > limit // 2:
        truncated = truncated[:last_space]
    return truncated + "…"


def _sanitize_hashtags(raw_tags: list[str], platform: str) -> list[str]:
    """Clean and validate hashtags, enforcing per-platform limits."""
    limit = get_platform(platform).hashtag_limit
    clean = []
    for tag in raw_tags:
        tag = tag.strip().lstrip("#").strip()
        if len(tag) < 3:
            continue
        if tag.lower() in _HASHTAG_STOPWORDS:
            continue
        if not _VALID_HASHTAG_RE.match(tag):
            continue
        clean.append(tag)
    return clean[:limit]


_SLIDE_RE = re.compile(r"Slide\s*\d+\s*[:\-–]\s*", re.IGNORECASE)


def _parse_slide_descriptions(caption: str, max_slides: int = 3) -> list[str]:
    """Extract per-slide text from a carousel-formatted caption."""
    parts = _SLIDE_RE.split(caption)
    # First part is usually empty or preamble text before "Slide 1:"
    slides = [p.strip() for p in parts[1:] if p.strip()]
    return slides[:max_slides]


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting that social platforms can't render."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return text


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
) -> list[tuple[bytes, str]]:
    """Generate images for carousel slides 2+ in parallel.

    Returns list of (image_bytes, mime_type) tuples.
    Skips slide 0 if cover_image_bytes is already provided (from the interleaved call).
    """
    start = 1 if cover_image_bytes else 0
    slides_to_generate = slide_descriptions[start:3]  # max 2 additional
    if not slides_to_generate:
        return []

    async def _gen_one(slide_text: str, slide_num: int) -> tuple[bytes, str] | None:
        prompt = (
            f"Generate a social media carousel slide image (slide {slide_num}).\n"
            f"Brand: {business_name}. Visual style: {visual_style}.\n"
            f"{color_hint}\n"
            f"Slide content: {slide_text[:300]}\n"
            f"{image_style_directive}\n"
            f"{style_ref_block}"
            "Create a clean, visually striking image that illustrates this slide's message.\n"
            "Do NOT include any text, watermarks, or captions in the image."
        )
        try:
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=GEMINI_IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.9,
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


async def generate_post(
    plan_id: str,
    day_brief: dict,
    brand_profile: dict,
    post_id: str,
    custom_photo_bytes: bytes | None = None,
    custom_photo_mime: str = "image/jpeg",
    instructions: str | None = None,
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
    hashtags_hint = day_brief.get("hashtags", [])
    derivative_type = day_brief.get("derivative_type", "original")

    business_name = brand_profile.get("business_name", "Brand")
    industry = brand_profile.get("industry", "")
    target_audience = brand_profile.get("target_audience", "general audience")
    tone = brand_profile.get("tone", "professional")
    visual_style = brand_profile.get("visual_style", "")
    image_style_directive = brand_profile.get("image_style_directive", "")
    caption_style_directive = brand_profile.get("caption_style_directive", "")
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
        "FORMATTING: Write plain text only. Do NOT use markdown formatting — no **bold**, "
        "*italic*, __underline__, or [links](url). Social platforms cannot render markdown. "
        "Use CAPS or emoji for emphasis instead if needed.\n\n"
        "AVOID these common AI-generated content patterns:\n"
        "- Starting with \"Are you ready to...\" or \"Did you know...\"\n"
        "- Ending every post with \"Drop a comment below!\" or \"Follow for more!\"\n"
        "- Using phrases like \"game-changer\", \"unlock your potential\", \"take it to the next level\"\n"
        "- Writing generic content that could apply to any business in any industry\n"
        "- Using emojis as bullet points (fire, pin, lightbulb) unless the brand style explicitly calls for it"
    )

    # Format-specific instructions for derivative post types
    _DERIVATIVE_INSTRUCTIONS: dict[str, str] = {
        "carousel": (
            "FORMAT: Instagram/LinkedIn CAROUSEL (3 slides)\n"
            "Structure the caption as slide-by-slide copy:\n"
            "  Slide 1: Hook (compelling, ≤10 words — this becomes the cover)\n"
            "  Slide 2: Core insight with a bold heading + 1-line body\n"
            "  Slide 3: Key takeaway + call to action\n"
            "Label each slide clearly: 'Slide 1:', 'Slide 2:', 'Slide 3:'."
        ),
        "thread_hook": (
            "FORMAT: Twitter/X THREAD\n"
            "Write 5 tweets, numbered:\n"
            "  1/ Hook that stops the scroll (≤280 chars, must create curiosity)\n"
            "  2/ – 4/ One key insight per tweet, concise and punchy (≤280 chars each)\n"
            "  5/ Takeaway + call to action (≤280 chars)\n"
            "Separate each tweet with a blank line. Each must stand alone."
        ),
        "blog_snippet": (
            "FORMAT: LinkedIn THOUGHT LEADERSHIP excerpt\n"
            "Write 150–200 words total:\n"
            "  - Bold opening statement (opinion-forward, 1 sentence)\n"
            "  - 2–3 short paragraphs expanding the idea with a real insight or example\n"
            "  - Closing question to spark discussion in the comments\n"
            "Professional but conversational tone."
        ),
        "story": (
            "FORMAT: Instagram/Facebook STORY\n"
            "Write ≤50 words total — short, punchy, immediate:\n"
            "  - First line: big emotion, bold question, or surprising statement\n"
            "  - One clear call to action (swipe up / reply / DM us)\n"
            "No hashtags in the body — add them in the HASHTAGS section only."
        ),
        "pin": (
            "FORMAT: Pinterest PIN\n"
            "Write as two clearly labeled parts:\n"
            "  PIN TITLE: ≤100 chars, keyword-rich, compelling headline\n"
            "  PIN DESCRIPTION: 200-250 chars, SEO-optimized with natural keywords\n"
            "No hashtags — use searchable keywords naturally."
        ),
        "video_first": (
            "FORMAT: VIDEO-FIRST POST\n"
            "Write a short, compelling caption to accompany a video clip.\n"
            "The video is the main content — the caption supports it.\n"
            "Keep the caption concise (under the platform's character limit).\n"
            "Include a hook that makes people want to watch the video.\n"
            "Do NOT describe the video — create curiosity or add context."
        ),
    }
    derivative_instruction = _DERIVATIVE_INSTRUCTIONS.get(derivative_type, "")
    _spec = get_platform(platform)
    platform_format = _spec.content_prompt
    aspect_hint = f"Generate a {_spec.image_aspect} aspect ratio image." if _spec.image_aspect != "1:1" else ""

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

        byop_prompt = f"""You are a {platform} content specialist for {industry} brands. You write for {business_name}, targeting {target_audience}.

Brand tone: {tone}
Visual style: {visual_style}
{caption_style_directive}
{social_voice_block}{f"CONTENT FORMAT:{chr(10)}{derivative_instruction}{chr(10)}" if derivative_instruction else ""}{f"{platform_format}{chr(10)}" if platform_format else ""}
{_QUALITY_BLOCK}

Analyze this photo and write a {platform} post caption that:
- Complements and describes what's in the photo
- Fits the "{content_theme}" theme for the "{pillar}" content pillar
- Your caption MUST begin with this hook (use it verbatim or improve it, but keep the core idea): "{caption_hook}"
- Carries this key message: {key_message}
- Ends with a call to action
{instruction_hint}
After the caption, add relevant hashtags on a new line starting with HASHTAGS:
CRITICAL: Only output real hashtags. Never convert sentence fragments into hashtags.
"""

        try:
            image_part = types.Part(
                inline_data=types.Blob(data=custom_photo_bytes, mime_type=custom_photo_mime)
            )
            text_part = types.Part(text=byop_prompt)

            response = await asyncio.to_thread(
                client.models.generate_content,
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

            yield {
                "event": "caption",
                "data": {"text": full_caption, "chunk": False, "hashtags": parsed_hashtags},
            }

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

            final_caption = _enforce_char_limit(_strip_markdown(full_caption), platform)
            _validate_format(final_caption, derivative_type)
            yield {
                "event": "complete",
                "data": {
                    "post_id": post_id,
                    "caption": final_caption,
                    "hashtags": parsed_hashtags,
                    "image_url": image_url,
                    "image_gcs_uri": image_gcs_uri,
                },
            }

        except Exception as e:
            logger.error("BYOP generation error for post %s: %s", post_id, e)
            yield {"event": "error", "data": {"message": str(e)}}

        return  # Do not fall through to normal generation

    # ── Video-first mode (text-only caption, no image generation) ──────────────
    if derivative_type == "video_first":
        yield {"event": "status", "data": {"message": f"Writing {platform} video caption..."}}

        video_prompt = f"""You are a {platform} content specialist for {industry} brands. You write for {business_name}, targeting {target_audience}.

Brand tone: {tone}
{caption_style_directive}
{social_voice_block}{f"CONTENT FORMAT:{chr(10)}{derivative_instruction}{chr(10)}" if derivative_instruction else ""}{f"{platform_format}{chr(10)}" if platform_format else ""}{trend_block}
{_QUALITY_BLOCK}

Create a {platform} video-first post for the "{pillar}" content pillar on the theme: "{content_theme}".

Your caption MUST begin with this hook (use it verbatim or improve it, but keep the core idea): "{caption_hook}"
Key message: {key_message}

Write a compelling caption to accompany a video clip. The video is the main content — the caption supports it.
{instruction_hint}
After the caption, add relevant hashtags on a new line starting with HASHTAGS:
CRITICAL: Only output real hashtags. Never convert sentence fragments into hashtags.
"""

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
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

            final_caption = _enforce_char_limit(_strip_markdown(full_caption), platform)
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
    prompt = f"""You are a {platform} content specialist for {industry} brands. You write for {business_name}, targeting {target_audience}.

Brand tone: {tone}
Visual style: {visual_style}
{caption_style_directive}
{social_voice_block}{image_style_directive}
{style_ref_block}{f"CONTENT FORMAT:{chr(10)}{derivative_instruction}{chr(10)}" if derivative_instruction else ""}{f"{platform_format}{chr(10)}" if platform_format else ""}{trend_block}
{_QUALITY_BLOCK}

Create a {platform} post for the "{pillar}" content pillar on the theme: "{content_theme}".

Your caption MUST begin with this hook (use it verbatim or improve it, but keep the core idea): "{caption_hook}"
Key message: {key_message}

Write the caption first (following the format above if specified), engaging and on-brand, ending with a call to action.
Then generate a stunning {platform}-optimized image.
{f"{aspect_hint}{chr(10)}" if aspect_hint else ""}
{color_hint}
Image visual: {image_prompt}
{instruction_hint}
After the caption, add relevant hashtags on a new line starting with HASHTAGS:
CRITICAL: Only output real hashtags. Never convert sentence fragments into hashtags.
"""

    full_caption = ""
    image_bytes = None
    image_mime = "image/png"
    image_url = None
    image_gcs_uri = None
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
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.7,
            ),
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
                    yield {
                        "event": "caption",
                        "data": {
                            "text": full_caption,
                            "chunk": False,
                            "hashtags": parsed_hashtags if parsed_hashtags else hashtags_hint,
                        }
                    }
                else:
                    full_caption += text
                    yield {
                        "event": "caption",
                        "data": {"text": text, "chunk": True}
                    }

            elif part.inline_data:
                image_bytes = part.inline_data.data
                image_mime = part.inline_data.mime_type or "image/png"

                yield {"event": "status", "data": {"message": "Uploading image..."}}

                try:
                    image_url, image_gcs_uri = await upload_image_to_gcs(image_bytes, image_mime, post_id)
                    bt.budget_tracker.record_image()
                    yield {
                        "event": "image",
                        "data": {"url": image_url, "mime_type": image_mime, "gcs_uri": image_gcs_uri}
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

        # Fallback: if Gemini didn't return an image in the interleaved response,
        # make a separate image-only generation call.
        if image_bytes is None:
            logger.warning("No image in interleaved response for post %s — retrying image-only", post_id)
            yield {"event": "status", "data": {"message": "Generating image..."}}
            try:
                img_prompt = (
                    f"Generate a stunning {platform}-optimized social media image.\n"
                    f"{aspect_hint + chr(10) if aspect_hint else ''}"
                    f"Brand: {business_name}. Visual style: {visual_style}.\n"
                    f"{color_hint}\n"
                    f"Image visual: {image_prompt}\n"
                    f"{image_style_directive}\n"
                    f"{style_ref_block}"
                    "Do NOT include any text, watermarks, or captions in the image."
                )
                img_response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_IMAGE_MODEL,
                    contents=img_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        temperature=0.9,
                    ),
                )
                for img_part in img_response.candidates[0].content.parts:
                    if img_part.inline_data:
                        image_bytes = img_part.inline_data.data
                        image_mime = img_part.inline_data.mime_type or "image/png"
                        break

                if image_bytes:
                    try:
                        image_url, image_gcs_uri = await upload_image_to_gcs(image_bytes, image_mime, post_id)
                        bt.budget_tracker.record_image()
                        yield {
                            "event": "image",
                            "data": {"url": image_url, "mime_type": image_mime, "gcs_uri": image_gcs_uri}
                        }
                    except Exception as upload_err:
                        logger.error("Fallback image upload failed: %s", upload_err)
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
                    logger.error("Fallback image generation also returned no image for post %s", post_id)
            except Exception as img_err:
                logger.error("Fallback image generation failed for post %s: %s", post_id, img_err)

        # ── Carousel: generate additional slide images ──────────────────────
        all_image_urls: list[str] = []
        all_image_gcs_uris: list[str] = []
        if image_url:
            all_image_urls.append(image_url)
        if image_gcs_uri:
            all_image_gcs_uris.append(image_gcs_uri)

        if derivative_type == "carousel" and full_caption:
            slide_descriptions = _parse_slide_descriptions(full_caption)
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
                    cover_image_bytes=image_bytes,
                )
                for slide_bytes, slide_mime in extra_slides:
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

        final_hashtags = parsed_hashtags if parsed_hashtags else hashtags_hint
        # Strip markdown + enforce hard character limits (X=280, Bluesky=300, Threads/Mastodon=500)
        final_caption = _enforce_char_limit(_strip_markdown(full_caption.strip()), platform)
        _validate_format(final_caption, derivative_type)
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
            }
        }

    except Exception as e:
        logger.error("Content generation error for post %s: %s", post_id, e)
        yield {"event": "error", "data": {"message": str(e)}}
