"""Quality checking and review gate logic for generated captions."""

import asyncio
import logging
import re

from google.genai import types

from backend.clients import get_genai_client
from backend.config import GEMINI_MODEL
from backend.platforms import get as get_platform
from backend.agents.review_agent import review_post
from backend.agents.caption_pipeline import (
    _enforce_char_limit,
    _fix_mojibake,
    _strip_markdown,
)
from backend.agents.carousel_builder import _SLIDE_RE
from backend.agents.hashtag_engine import _sanitize_hashtags

logger = logging.getLogger(__name__)


# --- Regex safety net for literal quality violations ---

_BANNED_OPENERS_RE = re.compile(
    r"^(?:"
    r"Are you\b|"
    r"Did you know\b|"
    r"What if\b|"
    r"In today'?s\b|"
    r"As a [a-z]|"
    r"When it comes to\b|"
    r"Here'?s the thing\b|"
    r"The truth is\b|"
    r"Let me tell you\b|"
    r"Still [a-z]+ing\b|"
    r"[A-Z][a-z]+ won'?t tell you\b|"
    r"You might be [a-z]+ing\b|"
    r"Imagine [a-z]+ing\b|"
    r"What your [a-z]+ isn'?t telling\b"
    r")",
    re.IGNORECASE,
)

_VAGUE_SOCIAL_PROOF_RE = re.compile(
    r"\b(?:countless|many (?:businesses|clients|owners|people|professionals)"
    r"|so many (?:businesses|clients|owners|people)|numerous (?:clients|businesses))\b",
    re.IGNORECASE,
)

# Discourse marker stripping — handles "But what if", "And did you know",
# "So, are you" etc. without adding individual regex patterns.
_DISCOURSE_MARKER_RE = re.compile(
    r"^(?:(?:but|and|so|yet|or|now|well|look|hey|listen|"
    r"honestly|actually|seriously|basically|simply|truly|"
    r"really|frankly|clearly|obviously|ok(?:ay)?|right"
    r")\b[,:\s]*)+",
    re.IGNORECASE,
)


def _check_quality_violations(caption: str, platform: str, derivative_type: str) -> list[str]:
    """Lightweight regex safety net for literal violations the self-review missed."""
    violations = []
    first_line = caption.split("\n")[0].strip()
    if derivative_type == "carousel" and "Slide 1" in caption:
        m = re.search(r"Slide\s*1[:\-\u2013]\s*(.*?)(?:\n|$)", caption, re.IGNORECASE)
        if m:
            first_line = m.group(1).strip()
    if platform != "pinterest":
        # Check each sentence in the opening line, stripping discourse markers
        # to catch variants like "But what if" → "what if" (already banned)
        for sentence in re.split(r'[.?!:]\s+', first_line):
            cleaned = _DISCOURSE_MARKER_RE.sub("", sentence.strip())
            if cleaned and _BANNED_OPENERS_RE.match(cleaned):
                violations.append(f"BANNED_HOOK: '{sentence.strip()[:60]}'")
                break
    m = _VAGUE_SOCIAL_PROOF_RE.search(caption)
    if m:
        violations.append(f"VAGUE_SOCIAL_PROOF: '{m.group()}'")
    if len(re.findall(r"!\s", caption + " ")) > 1:
        violations.append("EXCLAMATION_SPAM")
    return violations


async def _quality_retry(final_caption: str, platform: str, derivative_type: str) -> str:
    """If regex safety net catches violations, do one targeted LLM retry."""
    violations = _check_quality_violations(final_caption, platform, derivative_type)
    if not violations:
        return final_caption
    logger.warning("Quality safety net caught: %s — retrying", violations)
    retry_prompt = (
        f"Fix these specific issues in the caption below:\n"
        f"{chr(10).join(f'- {v}' for v in violations)}\n\n"
        f"Caption:\n{final_caption}\n\n"
        f"Rewrite fixing ONLY the flagged issues. Keep tone, structure, and length. "
        f"Output the corrected caption only, no hashtags, no explanation."
    )
    resp = await asyncio.to_thread(
        get_genai_client().models.generate_content, model=GEMINI_MODEL, contents=retry_prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    retried = _enforce_char_limit(_strip_markdown(_fix_mojibake(resp.text.strip())), platform, derivative_type)
    new_violations = _check_quality_violations(retried, platform, derivative_type)
    if len(new_violations) < len(violations):
        logger.info("Quality retry improved: %d → %d violations",
                     len(violations), len(new_violations))
        return retried
    logger.warning("Quality retry didn't improve — keeping original")
    return final_caption


async def _review_gate(
    final_caption: str,
    parsed_hashtags: list[str],
    platform: str,
    derivative_type: str,
    brand_profile: dict,
    day_brief: dict,
) -> tuple[str, list[str], dict | None]:
    """Run inline review; if score < 7, do one targeted rewrite using revision_notes.

    Returns (caption, hashtags, review_result). The review_result can be saved
    to Firestore so the frontend doesn't need a separate review API call.
    """
    try:
        # Extract context for review agent
        _story = brand_profile.get("storytelling_strategy", {})
        _proof_tier = _story.get("social_proof_tier") if isinstance(_story, dict) else None
        _cta_type = day_brief.get("cta_type")

        _pillar_rg = day_brief.get("pillar", "education")

        post_for_review = {
            "caption": final_caption,
            "hashtags": parsed_hashtags,
            "platform": platform,
            "derivative_type": derivative_type,
            "pillar": day_brief.get("pillar", "education"),
            "content_theme": day_brief.get("content_theme", ""),
        }
        review = await review_post(
            post_for_review, brand_profile,
            social_proof_tier=_proof_tier, cta_type=_cta_type,
        )
        score = review.get("score", 7)
        logger.info("Review gate score: %d for %s/%s", score, platform, derivative_type)

        if score >= 7:
            return final_caption, parsed_hashtags, review

        revision_notes = review.get("revision_notes")
        revised_hashtags = review.get("revised_hashtags")
        if not revision_notes:
            return final_caption, parsed_hashtags, review

        logger.warning(
            "Review gate triggered (score=%d) — rewriting with: %s", score, revision_notes
        )

        # Build targeted rewrite prompt using revision_notes + constraints
        notes_text = (
            revision_notes
            if isinstance(revision_notes, str)
            else "\n".join(f"- {n}" for n in revision_notes)
        )

        # Context from brand profile
        _biz = brand_profile.get("business_name", "Brand")
        _ind = brand_profile.get("industry", "")
        _aud = brand_profile.get("target_audience", "general audience")
        _tone = brand_profile.get("tone", "professional")

        # Hard constraint blocks (non-negotiable)
        _rewrite_constraints = ""
        if _proof_tier in ("thin_profile", None) or not _story:
            _rewrite_constraints += (
                "- SOCIAL PROOF: This brand has NO verified client data. "
                "DELETE any client stories, dollar amounts, percentages, or case studies — "
                "they are fabricated. Prove expertise by teaching a concrete technique instead.\n"
            )
        if _cta_type:
            _cta_labels = {
                "engagement": "end with ONE conversational question (no conversion language like 'book', 'DM', 'visit')",
                "conversion": "end with ONE action step (book/DM/save — no engagement question)",
                "implied": "NO explicit CTA — content implies the next step naturally",
                "none": "NO CTA of any kind",
            }
            _rewrite_constraints += (
                f"- CTA TYPE: This post uses a {_cta_type} CTA — "
                f"{_cta_labels.get(_cta_type, 'engagement style')}.\n"
            )

        # Format preservation notes per derivative type
        _spec = get_platform(platform)
        _char_limit = (_spec.char_limits or {}).get(derivative_type) or (_spec.char_limits or {}).get("default", 0)
        _limit_note = f" HARD LIMIT: {_char_limit} characters for {platform} {derivative_type}." if _char_limit else ""
        _FORMAT_NOTES = {
            "carousel": (
                f"STRUCTURAL CONSTRAINT (HARD RULE — violating this breaks the image pipeline):\n"
                f"The following Slide labels are MACHINE-PARSED to generate individual images. "
                f"You MUST preserve EVERY label exactly: "
                f"{', '.join(f'Slide {i+1}:' for i in range(_spec.carousel_slide_count))}.\n"
                f"- Do NOT remove, merge, renumber, or reword any Slide N: label\n"
                f"- Do NOT restructure the caption to eliminate slide boundaries\n"
                f"- Apply reviewer suggestions WITHIN individual slides, not by reorganizing\n"
                f"Content pillar: '{_pillar_rg}' — preserve pillar-appropriate content. "
                "Slide headlines ≤50 chars, ≤8 words — no generic words (Technique, Method, Step N). "
                "Keep sentences short for mobile readability."
            ),
            "thread_hook": (
                "Preserve numbered post format (1/, 2/, 3/) for X. "
                "Bluesky threads do NOT need numbering. "
                "Each post <=280 chars for X, <=300 for Bluesky. "
                "Each post must contain a complete, standalone thought. "
                f"Pillar '{_pillar_rg}' — each post must match the pillar approach."
            ),
            "blog_snippet": (
                f"Maintain 2-3 short paragraphs. 150-200 words total.{_limit_note} "
                "Closing question must be specific to the content — not generic."
            ),
            "pin": (
                "Preserve PIN TITLE: and PIN DESCRIPTION: labels exactly (machine-parsed downstream). "
                "PIN TITLE ≤100 chars with action verb and primary keyword. "
                "PIN DESCRIPTION 200-250 chars with natural SEO keywords. "
                "No emoji, no hashtags, no first-person."
            ),
            "video_first": f"VIDEO CAPTION — teaser only, not an article. 1-2 sentences MAX.{_limit_note} Create curiosity, don't describe the video. No brand paragraph.",
            "story": f"STORY — 1 sentence max, ultra-short and punchy.{_limit_note} CTA is REQUIRED (swipe up / reply / DM). No hashtags in body.",
            "original": f"STANDARD POST — hook before fold + body + close. 1-2 sentence paragraphs for mobile readability.{_limit_note}",
        }
        _fmt = _FORMAT_NOTES.get(derivative_type, "")
        _format_block = f"FORMAT: {derivative_type}\n{_fmt}\n\n" if _fmt else ""

        retry_prompt = (
            f"You are a {platform} content specialist for {_biz}"
            f"{f' ({_ind})' if _ind else ''}, targeting {_aud}. "
            f"Tone: {_tone}.\n\n"
            f"HARD RULES (non-negotiable — these override ANY suggestion below):\n"
            f"{_rewrite_constraints}"
            f"- Do NOT invent client stories, dollar amounts, or statistics\n"
            f"- Prove expertise by teaching something specific and actionable\n"
            f"- BANNED HOOKS — do NOT open with any of these (or variants with 'But', 'And', 'So' prefixes): "
            f"\"Are you...?\", \"Did you know...?\", \"What if...?\", \"In today's...\", "
            f"\"As a...\", \"When it comes to...\", \"Here's the thing:\", \"The truth is:\", "
            f"\"Let me tell you\", \"Still [X]ing...?\", \"[X] won't tell you\", "
            f"\"You might be [X]ing\", \"Imagine [X]ing\"\n"
            f"- MOMENTUM KILLERS — do NOT use: \"Sound familiar?\", \"Let's break it down\", "
            f"\"Here's why it matters\", \"Let me explain\", \"Here's why you need to\"\n"
            f"- Open with a SPECIFIC, CONCRETE statement or a pattern-interrupt instead\n\n"
            f"{_format_block}"
            f"REVIEWER SUGGESTIONS (apply within existing format structure — "
            f"do NOT remove/merge/renumber structural labels like "
            f"Slide N:, 1/, PIN TITLE:, PIN DESCRIPTION:):\n"
            f"{notes_text}\n\n"
            f"CURRENT CAPTION:\n{final_caption}\n\n"
            f"Rewrite the caption, fixing the issues while respecting the hard rules. "
            f"You may adjust the hook or shorten text if needed for mobile readability. "
            f"Output the corrected caption only. No explanation, no hashtags."
        )
        resp = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=retry_prompt,
            config=types.GenerateContentConfig(temperature=0.4),
        )
        rewritten = _enforce_char_limit(
            _strip_markdown(_fix_mojibake(resp.text.strip())),
            platform,
            derivative_type,
        )
        # Carousel safety: reject rewrites that lost slide structure
        if derivative_type == "carousel":
            orig_slides = len(_SLIDE_RE.findall(final_caption))
            new_slides = len(_SLIDE_RE.findall(rewritten))
            if orig_slides > 1 and new_slides < orig_slides:
                logger.warning(
                    "Review gate rewrite lost slides (%d→%d) — keeping original",
                    orig_slides, new_slides,
                )
                return final_caption, parsed_hashtags, review
        if revised_hashtags and isinstance(revised_hashtags, list):
            parsed_hashtags = _sanitize_hashtags(revised_hashtags, platform)
        logger.info("Review gate rewrite complete for %s/%s", platform, derivative_type)

        # Re-review the rewritten caption so we have an accurate score to cache
        rewritten_for_review = {
            "caption": rewritten,
            "hashtags": parsed_hashtags,
            "platform": platform,
            "derivative_type": derivative_type,
            "pillar": day_brief.get("pillar", "education"),
            "content_theme": day_brief.get("content_theme", ""),
        }
        final_review = await review_post(
            rewritten_for_review, brand_profile,
            social_proof_tier=_proof_tier, cta_type=_cta_type,
        )
        final_score = final_review.get("score", 0)
        logger.info("Review gate post-rewrite score: %d for %s/%s",
                     final_score, platform, derivative_type)

        if final_score >= 7:
            return rewritten, parsed_hashtags, final_review

        # ── Attempt 2: stronger rewrite with full day brief context ──
        logger.warning("Review gate attempt 2 (score=%d) — stronger rewrite for %s/%s",
                       final_score, platform, derivative_type)

        _pillar = day_brief.get("pillar", "")
        _theme = day_brief.get("content_theme", "")
        _hook_dir = day_brief.get("caption_hook", "")
        _key_msg = day_brief.get("key_message", "")

        strong_notes = final_review.get("revision_notes", "")
        if isinstance(strong_notes, list):
            strong_notes = "\n".join(f"- {n}" for n in strong_notes)

        strong_prompt = (
            f"You are a {platform} content specialist for {_biz}"
            f"{f' ({_ind})' if _ind else ''}, targeting {_aud}. Tone: {_tone}.\n\n"
            f"The previous caption scored {final_score}/10 and FAILED quality review. "
            f"You must write a SUBSTANTIALLY DIFFERENT version — do not patch the old one.\n\n"
            f"CONTENT BRIEF (follow this closely):\n"
            f"- Pillar: {_pillar}\n"
            f"- Theme: {_theme}\n"
            f"- Hook angle: {_hook_dir}\n"
            f"- Key message: {_key_msg}\n"
            f"- CTA type: {_cta_type or 'engagement'}\n\n"
            f"REVIEWER FEEDBACK (fix within existing structure — "
            f"do NOT remove/merge/renumber structural labels):\n{strong_notes}\n\n"
            f"HARD RULES:\n{_rewrite_constraints}"
            f"- BANNED HOOKS — do NOT open with: "
            f"\"Are you...?\", \"Did you know...?\", \"What if...?\", \"In today's...\", "
            f"\"As a...\", \"When it comes to...\", \"Here's the thing:\", \"The truth is:\"\n"
            f"- Open with a SPECIFIC, CONCRETE statement or pattern-interrupt\n"
            f"- Prove expertise by teaching, not claiming\n\n"
            f"{_format_block}"
            f"Write a complete new caption. Output the caption only — no explanation, no hashtags."
        )
        resp2 = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=strong_prompt,
            config=types.GenerateContentConfig(temperature=0.6),
        )
        strong_rewrite = _enforce_char_limit(
            _strip_markdown(_fix_mojibake(resp2.text.strip())),
            platform, derivative_type,
        )
        # Carousel safety: reject rewrites that lost slide structure
        if derivative_type == "carousel":
            orig_slides = len(_SLIDE_RE.findall(final_caption))
            strong_slides = len(_SLIDE_RE.findall(strong_rewrite))
            if orig_slides > 1 and strong_slides < orig_slides:
                logger.warning(
                    "Review gate attempt 2 lost slides (%d→%d) — keeping original",
                    orig_slides, strong_slides,
                )
                return final_caption, parsed_hashtags, review

        # Re-review attempt 2
        strong_for_review = {
            "caption": strong_rewrite,
            "hashtags": parsed_hashtags,
            "platform": platform,
            "derivative_type": derivative_type,
            "pillar": day_brief.get("pillar", "education"),
            "content_theme": day_brief.get("content_theme", ""),
        }
        strong_review = await review_post(
            strong_for_review, brand_profile,
            social_proof_tier=_proof_tier, cta_type=_cta_type,
        )
        strong_score = strong_review.get("score", 0)
        logger.info("Review gate attempt 2 score: %d for %s/%s",
                     strong_score, platform, derivative_type)

        if strong_score >= 7:
            if strong_review.get("revised_hashtags"):
                parsed_hashtags = _sanitize_hashtags(strong_review["revised_hashtags"], platform)
            return strong_rewrite, parsed_hashtags, strong_review

        # ── Attempt 2 also failed — return the best version we have ──
        logger.warning("Review gate exhausted — best score %d for %s/%s",
                       max(final_score, strong_score), platform, derivative_type)
        if strong_score >= final_score:
            return strong_rewrite, parsed_hashtags, strong_review
        return rewritten, parsed_hashtags, final_review

    except Exception as e:
        logger.warning("Review gate failed (non-fatal): %s — keeping original", e)
        return final_caption, parsed_hashtags, None
