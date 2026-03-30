import asyncio
import json
import logging
from datetime import datetime, timezone
from google import genai
from google.genai import types
from backend.config import GOOGLE_API_KEY, GEMINI_MODEL
from backend.clients import get_genai_client
from backend.constants import PILLARS, DERIVATIVE_TYPES, get_proof_tier
from backend.platforms import keys as platform_keys, get as get_platform
from backend.services import firestore_client

logger = logging.getLogger(__name__)


# ── Platform intelligence ─────────────────────────────────────────────────────

async def _research_best_platforms(
    brand_profile: dict,
    available_platforms: list[str],
) -> list[dict]:
    """Research which social platforms are best for this business.

    Uses Google Search grounding to get current data on platform demographics
    and effectiveness for this specific industry + audience.

    Returns ranked list: [{"platform": "instagram", "reason": "...", "priority": 1}, ...]
    """
    business_type = brand_profile.get("business_type", "")
    industry = brand_profile.get("industry", "")
    target_audience = brand_profile.get("target_audience", "")
    content_themes = brand_profile.get("content_themes", [])
    tone = brand_profile.get("tone", "")

    # Check Firestore cache first (keyed by industry + business_type, TTL 7 days)
    try:
        cached = await firestore_client.get_platform_recommendations(industry, business_type)
        if cached:
            logger.info("Platform recommendations cache hit: %s / %s", industry, business_type)
            return cached
    except Exception:
        pass

    prompt = (
        f"Research the best social media platforms for a {business_type} "
        f"in the {industry} industry.\n"
        f"Target audience: {target_audience}\n"
        f"Brand tone: {tone}\n"
        f"Content themes: {', '.join(content_themes[:5]) if content_themes else 'general'}\n\n"
        f"Available platforms: {', '.join(available_platforms)}\n\n"
        "Based on current data (2025-2026), rank the TOP 5 platforms for this "
        "specific business type and audience. Consider:\n"
        "- Which platforms does this target audience actually use?\n"
        "- Which platforms favor this type of content/industry?\n"
        "- Where are similar businesses seeing the most engagement?\n"
        "- Platform demographics alignment with the target audience\n\n"
        "Return ONLY a valid JSON array of objects, ranked best to worst:\n"
        '[{"platform": "instagram", "reason": "Why this platform fits", "priority": 1}, ...]'
    )

    try:
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        if len(raw) > 500_000:
            logger.warning("LLM output too large (%d bytes), truncating", len(raw))
            raw = raw[:500_000]
        recommendations = json.loads(raw.strip())

        # Validate — only keep platforms from our available list
        valid = [r for r in recommendations if r.get("platform") in available_platforms]

        # Cache for 7 days (best-effort)
        try:
            await firestore_client.save_platform_recommendations(industry, business_type, valid)
        except Exception:
            pass

        return valid[:5]
    except json.JSONDecodeError as jde:
        logger.warning("Platform recommendation: invalid JSON from LLM (first 200 chars): %s — %s", raw[:200], jde)
        return []
    except Exception as e:
        logger.warning("Platform recommendation research failed: %s", e)
        return []


async def _research_posting_frequency(
    brand_profile: dict,
    platforms: list[str],
) -> dict[str, dict]:
    """Research optimal weekly posting frequency + best times per platform.

    Uses Google Search grounding to get current best practices.
    Returns: {"instagram": {"posts_per_week": 7, "best_times": ["6:00 PM", ...]}, ...}
    """
    business_type = brand_profile.get("business_type", "")
    industry = brand_profile.get("industry", "")
    target_audience = brand_profile.get("target_audience", "")

    # Check Firestore cache (keyed by industry + business_type + platforms, TTL 7 days)
    try:
        cached = await firestore_client.get_posting_frequency(industry, business_type, platforms)
        if cached:
            logger.info("Posting frequency cache hit: %s / %s", industry, business_type)
            return cached
    except Exception:
        pass

    prompt = (
        f"Research the optimal weekly posting frequency for a {business_type} "
        f"in the {industry} industry on each of these platforms: {', '.join(platforms)}.\n"
        f"Target audience: {target_audience}\n\n"
        "Based on current data (2025-2026), for each platform provide:\n"
        "1. Optimal posts per week (integer 1-7)\n"
        "2. Best posting times (top 2-3 times in HH:MM AM/PM format)\n\n"
        "Consider:\n"
        "- Platform algorithm preferences for posting frequency\n"
        "- Industry benchmarks for engagement vs frequency\n"
        "- Audience expectations and peak activity times on each platform\n"
        "- Quality vs quantity trade-offs\n\n"
        "Return ONLY a valid JSON object:\n"
        '{"instagram": {"posts_per_week": 7, "best_times": ["6:00 PM", "12:00 PM", "9:00 AM"]}, ...}'
    )

    try:
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        if len(raw) > 500_000:
            logger.warning("LLM output too large (%d bytes), truncating", len(raw))
            raw = raw[:500_000]
        freq = json.loads(raw.strip())

        # Validate — clamp to 1-7, only keep selected platforms
        result: dict[str, dict] = {}
        for p in platforms:
            entry = freq.get(p, {})
            if isinstance(entry, (int, float)):
                result[p] = {"posts_per_week": max(1, min(7, int(entry))), "best_times": []}
            else:
                result[p] = {
                    "posts_per_week": max(1, min(7, int(entry.get("posts_per_week", 5)))),
                    "best_times": [str(t) for t in entry.get("best_times", [])][:3],
                }

        # Cache (best-effort)
        try:
            await firestore_client.save_posting_frequency(industry, business_type, platforms, result)
        except Exception:
            pass

        logger.info("Posting frequency researched for %s/%s: %s", industry, business_type,
                     {p: v["posts_per_week"] for p, v in result.items()})
        return result
    except json.JSONDecodeError as jde:
        logger.warning("Posting frequency: invalid JSON from LLM (first 200 chars): %s — %s", raw[:200], jde)
        return {p: {"posts_per_week": 7, "best_times": []} for p in platforms}
    except Exception as e:
        logger.warning("Posting frequency research failed: %s", e)
        # Fallback: all platforms daily
        return {p: {"posts_per_week": 7, "best_times": []} for p in platforms}


async def _research_platform_trends(platform: str, industry: str) -> dict | None:
    """Fetch current platform+industry trends via Google Search grounding.

    Results are cached in Firestore for 7 days.
    Returns None if research fails — callers treat it as optional enhancement.
    """
    # Check cache first
    try:
        cached = await firestore_client.get_platform_trends(platform, industry)
        if cached:
            logger.info("Platform trends cache hit: %s / %s", platform, industry)
            return cached
    except Exception as e:
        logger.warning("Trend cache read error: %s", e)

    # Fetch from Gemini with Google Search grounding
    try:
        prompt = (
            f"Research the current content strategy best practices on {platform} "
            f"for the {industry} industry. What's working right now?\n"
            "- What content FORMATS are getting the most engagement? (carousel, video, text, etc.)\n"
            "- Trending topics or hooks for this industry\n"
            "- Algorithm preferences (what's being boosted vs suppressed?)\n"
            "- Best posting time recommendations\n"
            "- Character/length sweet spots for captions\n\n"
            'Return ONLY a valid JSON object with these keys: '
            '{"trending_formats": [...], "trending_hooks": [...], '
            '"algorithm_notes": "...", "best_posting_times": [...], '
            '"best_content_format": "...", "caption_sweet_spot": "..."}'
        )
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        if len(raw) > 500_000:
            logger.warning("LLM output too large (%d bytes), truncating", len(raw))
            raw = raw[:500_000]
        trends = json.loads(raw.strip())

        # Save to cache (best-effort)
        try:
            await firestore_client.save_platform_trends(platform, industry, trends)
        except Exception as ce:
            logger.warning("Trend cache write error: %s", ce)

        return trends
    except json.JSONDecodeError as jde:
        logger.warning("Platform trend research: invalid JSON from LLM (first 200 chars): %s — %s", raw[:200], jde)
        return None
    except Exception as e:
        logger.warning("Platform trend research failed (%s/%s): %s", platform, industry, e)
        return None


async def _research_industry_hooks(industry: str, platforms: list[str]) -> str:
    """Search for best-performing hook patterns for this industry across all platforms.

    Returns a text block with hook examples/patterns, or "" on failure.
    Called once per plan (not per post) to amortize latency.
    """
    if not industry:
        return ""
    platform_str = ", ".join(platforms[:5])
    try:
        prompt = (
            f"Research the most effective social media hooks and opening lines for "
            f"{industry} businesses on {platform_str}.\n"
            "What types of hooks stop the scroll and drive engagement for this industry?\n"
            "- Specific hook structures that work (contrarian, story, number, question)\n"
            "- Real examples of high-performing opening lines\n"
            "- What makes a hook specific to this industry vs generic\n\n"
            "Return a concise summary (under 200 words) of the best hook patterns."
        )
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        result = response.text.strip()
        logger.info("Industry hook research completed for %s", industry)
        return result
    except Exception as e:
        logger.warning("Industry hook research failed (%s): %s", industry, e)
        return ""


async def _research_visual_trends(platform: str, industry: str) -> dict | None:
    """Fetch current visual/image style trends via Google Search grounding.

    Results are cached in Firestore for 7 days.
    Returns None if research fails — callers treat it as optional enhancement.
    """
    # Check cache first
    try:
        cached = await firestore_client.get_platform_trends(f"visual_{platform}", industry)
        if cached:
            logger.info("Visual trends cache hit: %s / %s", platform, industry)
            return cached
    except Exception as e:
        logger.warning("Visual trend cache read error: %s", e)

    # Fetch from Gemini with Google Search grounding
    try:
        month_year = datetime.now(timezone.utc).strftime('%B %Y')
        prompt = (
            f"Research what image styles and visual content formats are currently driving the\n"
            f"highest engagement for {industry} brands on {platform} in {month_year}.\n"
            "- What image styles perform best? (bold graphics, lifestyle photography, text overlays, minimal, etc.)\n"
            "- Single image vs carousel vs infographic — which gets more reach right now?\n"
            "- Trending composition patterns (close-ups, split screen, before/after, etc.)\n"
            "- Color trends or aesthetic shifts specific to this industry on this platform\n\n"
            f"Also provide 5 specific scene descriptions for {industry} content on {platform}.\n"
            "Each scene: subject, setting, lighting, camera angle, mood.\n"
            "Example: 'Close-up of hands holding a product with warm side-lighting, "
            "blurred workspace background, confident and focused mood'\n"
            "NOT generic like 'professional image about the industry'.\n\n"
            "Return ONLY a valid JSON object with these keys:\n"
            '{"trending_styles": [...], "format_performance": "...", "composition_tips": [...], "color_trends": "...", "scene_suggestions": [...]}'
        )
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        if len(raw) > 500_000:
            logger.warning("LLM output too large (%d bytes), truncating", len(raw))
            raw = raw[:500_000]
        result = json.loads(raw.strip())

        # Save to cache (best-effort)
        try:
            await firestore_client.save_platform_trends(f"visual_{platform}", industry, result)
        except Exception as ce:
            logger.warning("Visual trend cache write error: %s", ce)

        return result
    except json.JSONDecodeError as jde:
        logger.warning("Visual trend research: invalid JSON from LLM (first 200 chars): %s — %s", raw[:200], jde)
        return None
    except Exception as e:
        logger.warning("Visual trend research failed (%s/%s): %s", platform, industry, e)
        return None


async def _research_video_trends(platform: str, industry: str) -> dict | None:
    """Fetch current short-form video trend patterns via Google Search grounding.

    Results are cached in Firestore for 7 days.
    Returns None if research fails — callers treat it as optional enhancement.
    """
    # Check cache first
    try:
        cached = await firestore_client.get_platform_trends(f"video_{platform}", industry)
        if cached:
            logger.info("Video trends cache hit: %s / %s", platform, industry)
            return cached
    except Exception as e:
        logger.warning("Video trend cache read error: %s", e)

    # Fetch from Gemini with Google Search grounding
    try:
        month_year = datetime.now(timezone.utc).strftime('%B %Y')
        prompt = (
            f"Research what short-form video formats and hook patterns are driving the highest\n"
            f"engagement for {industry} brands on {platform} in {month_year}.\n"
            "- What video formats are trending? (myth-bust reveal, talking head, b-roll montage, text-on-screen, etc.)\n"
            "- Optimal video lengths currently performing best (in seconds)\n"
            "- Hook patterns that drive 3-second retention (opening question, bold statement, visual hook, etc.)\n"
            "- Audio trends (voiceover, trending sounds, silence + captions, etc.)\n\n"
            "Return ONLY a valid JSON object with these keys:\n"
            '{"trending_formats": [...], "optimal_lengths": "...", "hook_patterns": [...], "audio_notes": "..."}'
        )
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        if len(raw) > 500_000:
            logger.warning("LLM output too large (%d bytes), truncating", len(raw))
            raw = raw[:500_000]
        result = json.loads(raw.strip())

        # Save to cache (best-effort)
        try:
            await firestore_client.save_platform_trends(f"video_{platform}", industry, result)
        except Exception as ce:
            logger.warning("Video trend cache write error: %s", ce)

        return result
    except json.JSONDecodeError as jde:
        logger.warning("Video trend research: invalid JSON from LLM (first 200 chars): %s — %s", raw[:200], jde)
        return None
    except Exception as e:
        logger.warning("Video trend research failed (%s/%s): %s", platform, industry, e)
        return None


# ── Format-aware planning notes ───────────────────────────────────────────────

_FORMAT_GUIDE = """PLATFORM FORMAT GUIDANCE (match content format to what works on each platform):

INSTAGRAM — Reels FIRST, then Carousel:
  - Reels get 2x the reach of static posts. Always consider video_first.
  - Assign derivative_type "video_first" for at least 1 out of every 3 Instagram posts.
  - Carousels remain #1 for educational content — use for how-to/tip content.
  - Static image posts (derivative_type "original") only for announcements or quotes.
  - DM shares and saves are the #1 algorithm signals.

LINKEDIN — Video for thought leadership, Carousel for education:
  - Video gets 5x engagement vs text-only posts.
  - Use "video_first" for personal stories, behind-the-scenes, talking head content.
  - Use "carousel" for frameworks, checklists, how-to content.
  - Use "blog_snippet" for opinion pieces.
  - NEVER include external links in captions.

X/TWITTER — Video is dominant:
  - 4 out of 5 sessions now include video. Video tweets get 10x engagement.
  - Use derivative_type "video_first" for attention-grabbing content.
  - Use "thread_hook" for multi-point educational content.
  - Use "original" (text+image) for quick takes and replies.
  - Single tweets: keep under 200 chars, designed to spark quick replies.

TIKTOK — Video FIRST, then Photo Carousel:
  - Video is the dominant format. Use "video_first" for most TikTok content.
  - Photo carousels getting algorithm-boosted reach for educational content.
  - Use "carousel" for TikTok educational/list content.
  - Problem-solution and behind-the-scenes content outperforms polished.

FACEBOOK — Reels growing fast, Carousel for engagement:
  - Reels are prioritized in the algorithm. Use "video_first" for broad reach.
  - Use "carousel" for storytelling and educational content.
  - Use "original" for community-oriented question posts.
  - Shares/saves worth 50x likes. NEVER include external links in captions.

THREADS — Conversation Starter + Image:
  - Image posts get 60% more engagement than text-only.
  - Algorithm SUPPRESSES promotional content — be authentic.
  - Video growing as Meta pushes Reels infrastructure. Use "video_first" for dynamic content.
  - End with a question or hot take.

PINTEREST — SEO Pin + Visual:
  - Idea Pins (multi-image) get 4x engagement of standard pins.
  - Idea Pin video growing fast — use "video_first" for how-to and behind-the-scenes.
  - Pinterest is a SEARCH ENGINE — keyword-rich titles and descriptions.
  - Use derivative_type "pin" — caption format is PIN TITLE + PIN DESCRIPTION.

YOUTUBE SHORTS — Video Only:
  - Video-first platform. Our job is to generate the description/caption.
  - ALWAYS use derivative_type "video_first".
  - First 125 chars appear in search — include primary keyword.

MASTODON — Text + Essential Hashtags:
  - NO algorithm — hashtags ARE the only discovery mechanism.
  - Community-first, anti-spam. Earn boosts by being genuinely useful.
  - Video supported — use "video_first" sparingly for impactful content.
  - CamelCase hashtags are critical for accessibility and discovery.

BLUESKY — Thread or Short Take + Image:
  - Threads get 3x engagement vs single posts.
  - Custom feeds drive 5x impressions. Video supported — early mover advantage.
  - Replies are the #1 metric, not likes.
  - Use "thread_hook" for multi-point content.
  - 300 char limit, so single posts must be ultra-concise.

VIDEO vs IMAGE DECISION:
Choose derivative_type "video_first" when the content is:
- Behind-the-scenes / day-in-the-life (movement matters)
- Before/after transformations
- Quick tips or tutorials (show, don't tell)
- Personal stories or testimonials
- Trending topics that benefit from urgency/energy

Choose IMAGE-based types ("original", "carousel") when the content is:
- Data-heavy / infographic (static is easier to read)
- Step-by-step guides (carousel with slides)
- Quotes or announcements
- SEO-focused content (Pinterest, long-form LinkedIn)
"""


# ── Main strategy agent ──────────────────────────────────────────────────────

async def run_strategy(
    brand_id: str,
    brand_profile: dict,
    num_days: int = 7,
    business_events: str | None = None,
    platforms: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Run the Strategy Agent to generate a multi-day content plan.

    Args:
        brand_id: The brand identifier.
        brand_profile: Full brand profile dict from Firestore.
        num_days: Number of day briefs to generate (default 7).
        business_events: Optional string describing real business events this week.
        platforms: Optional list of platform keys. If None, AI recommends platforms.

    Returns:
        Tuple of (list of day brief dicts, trend_summary dict).
    """
    industry = brand_profile.get("industry", "")
    all_platforms = platform_keys()
    original_platforms = platforms  # Save before mutation to track user-selected vs AI

    # ── Phase 0a: Determine platforms ─────────────────────────────────────────
    platform_reasoning = ""
    if platforms:
        # User specified platforms — validate and use them directly
        platforms = [p for p in platforms if p in all_platforms or p == "twitter"]
        if not platforms:
            platforms = ["instagram", "linkedin"]
        logger.info("User-selected platforms for %s: %s", brand_id, platforms)
    else:
        # AI selects best platforms for this business
        recommendations = await _research_best_platforms(brand_profile, all_platforms)
        if recommendations:
            platforms = [r["platform"] for r in recommendations]
            platform_reasoning = "\n".join(
                f"- {r['platform'].upper()}: {r['reason']}" for r in recommendations
            )
            logger.info("AI-recommended platforms for %s: %s", brand_id, platforms)
        else:
            platforms = ["instagram", "linkedin", "x", "facebook"]
            platform_reasoning = ""

    # Track whether platforms were user-selected (vs AI-recommended)
    user_selected_platforms = original_platforms is not None

    # ── Phase 0b: Fetch trends + industry hooks + posting frequency ────────
    trend_platforms = platforms[:5]  # Limit to 5 to avoid rate limits
    primary_platform = trend_platforms[0] if trend_platforms else "instagram"
    trend_results = await asyncio.gather(
        *[_research_platform_trends(p, industry) for p in trend_platforms],
        _research_industry_hooks(industry, platforms),
        _research_posting_frequency(brand_profile, platforms),
        _research_visual_trends(primary_platform, industry),
        _research_video_trends(primary_platform, industry),
        return_exceptions=True,
    )
    # Unpack visual and video from the end (added last)
    video_result_raw = trend_results[-1]
    visual_result_raw = trend_results[-2]
    trend_results = trend_results[:-2]  # strip them before existing unpacking

    visual_trends: dict | None = visual_result_raw if isinstance(visual_result_raw, dict) else None
    video_trends: dict | None = video_result_raw if isinstance(video_result_raw, dict) else None

    # Last two results: hook research, then posting frequency
    freq_result_raw = trend_results[-1]
    freq_result: dict[str, dict] = (
        freq_result_raw if isinstance(freq_result_raw, dict)
        else {p: {"posts_per_week": 7, "best_times": []} for p in platforms}
    )
    trend_results = trend_results[:-1]  # Remove freq from trend_results
    # Last result is the hook research; the rest are per-platform trends
    hook_research_result = trend_results[-1]
    hook_research: str = hook_research_result if isinstance(hook_research_result, str) else ""
    trend_results = trend_results[:-1]
    trends_context = ""
    platform_trends_map: dict[str, dict] = {}
    for p, result in zip(trend_platforms, trend_results):
        if isinstance(result, dict):
            platform_trends_map[p] = result
            trends_context += (
                f"\nCURRENT TRENDS ({p.upper()} · {industry}):\n"
                f"- Trending formats: {', '.join(result.get('trending_formats', [])[:4])}\n"
                f"- Trending hooks: {', '.join(result.get('trending_hooks', [])[:4])}\n"
                f"- Algorithm notes: {result.get('algorithm_notes', 'N/A')}\n"
                f"- Best posting times: {', '.join(result.get('best_posting_times', [])[:3])}\n"
            )
    if trends_context:
        trends_context += (
            "\nIncorporate these trends where they fit the brand. "
            "Don't force them — only use what is authentic.\n"
        )

    # Add hook research to trends context if available
    hook_research_block = ""
    if hook_research:
        hook_research_block = (
            f"\nINDUSTRY HOOK RESEARCH ({industry}):\n{hook_research}\n"
            "Use these hook patterns as inspiration for caption_hook values. "
            "Adapt them to be specific to this brand, not generic.\n"
        )

    visual_research_block = ""
    if visual_trends:
        styles = ", ".join(str(s) for s in visual_trends.get("trending_styles", [])[:4])
        fmt = str(visual_trends.get("format_performance", ""))[:200]
        tips = "; ".join(str(t) for t in visual_trends.get("composition_tips", [])[:3])
        scenes = "\n  ".join(str(s) for s in visual_trends.get("scene_suggestions", [])[:5])
        visual_research_block = (
            f"\nVISUAL RESEARCH ({primary_platform.upper()}, {industry}):\n"
            f"- Trending styles: {styles}\n"
            f"- Format performance: {fmt}\n"
            f"- Composition tips: {tips}\n"
            + (f"- Scene suggestions:\n  {scenes}\n" if scenes else "")
            + "Use these findings to write specific image_prompt values — not generic 'professional image about X.'\n"
        )

    video_research_block = ""
    if video_trends:
        fmts = ", ".join(str(f) for f in video_trends.get("trending_formats", [])[:4])
        lengths = str(video_trends.get("optimal_lengths", ""))[:200]
        hooks = "; ".join(str(h) for h in video_trends.get("hook_patterns", [])[:3])
        video_research_block = (
            f"\nVIDEO RESEARCH ({primary_platform.upper()}, {industry}):\n"
            f"- Trending formats: {fmts}\n"
            f"- Optimal lengths: {lengths}\n"
            f"- Hook patterns: {hooks}\n"
            "For posts with derivative_type 'video_first', use these patterns in caption_hook and image_prompt.\n"
        )

    # ── Compute per-platform brief counts from researched frequency ──────────
    num_platforms = len(platforms)
    platform_briefs: dict[str, int] = {}
    platform_times: dict[str, list[str]] = {}
    for p in platforms:
        entry = freq_result.get(p, {"posts_per_week": 5, "best_times": []})
        weekly_freq = entry["posts_per_week"]
        platform_briefs[p] = max(1, round(weekly_freq * num_days / 7))
        platform_times[p] = entry.get("best_times", [])

    total_briefs = sum(platform_briefs.values())

    freq_context = "\n".join(
        f"- {p.upper()}: {platform_briefs[p]} posts this {num_days}-day period "
        f"({freq_result.get(p, {}).get('posts_per_week', 5)}x/week recommended)"
        + (f" — best times: {', '.join(platform_times[p])}" if platform_times[p] else "")
        for p in platforms
    )

    logger.info("Brief distribution for %s: %s (total=%d)", brand_id, platform_briefs, total_briefs)

    # ── Build strategy prompt ─────────────────────────────────────────────────
    platform_list = ", ".join(platforms)
    platform_rec_block = ""
    if platform_reasoning:
        platform_rec_block = (
            f"\nRECOMMENDED PLATFORMS (based on industry + audience research):\n"
            f"{platform_reasoning}\n"
        )

    # Temporal awareness
    now = datetime.now(timezone.utc)
    _month = now.month
    _season = (
        "Winter" if _month in (12, 1, 2) else
        "Spring" if _month in (3, 4, 5) else
        "Summer" if _month in (6, 7, 8) else "Fall"
    )
    temporal_context = (
        f"TODAY: {now.strftime('%A, %B %d, %Y')} (Week {now.isocalendar()[1]})\n"
        f"SEASON: {_season}\n"
        "Make content time-relevant. Reference the current season, upcoming holidays, "
        "or industry events happening this week. Generic 'evergreen' content for every day is lazy.\n"
    )

    # Curated brand profile (not raw JSON dump)
    curated_profile = (
        f"Business: {brand_profile.get('business_name', 'Brand')}\n"
        f"Industry: {brand_profile.get('industry', '')}\n"
        f"Type: {brand_profile.get('business_type', '')}\n"
        f"Tone: {brand_profile.get('tone', '')}\n"
        f"Target audience: {brand_profile.get('target_audience', '')}\n"
        f"Content themes: {', '.join(brand_profile.get('content_themes', []))}\n"
        f"Visual style: {brand_profile.get('visual_style', '')}\n"
        f"Colors: {', '.join(brand_profile.get('colors', []))}\n"
    )

    # ── Social proof tier → pillar + format guidance ──
    _proof_tier = get_proof_tier(
        brand_profile.get("years_in_business"),
        brand_profile.get("client_count"),
    )

    _pillar_guidance = ""
    if _proof_tier == "thin_profile":
        _pillar_guidance = (
            "\nPILLAR DISTRIBUTION — THIN PROFILE (this brand has NO client reviews, "
            "testimonials, years-in-business, or client count):\n"
            f"Education is this brand's PRIMARY trust-builder. In a {num_days}-day plan:\n"
            "- MINIMUM 4 education posts — teach specific, actionable insights that prove expertise\n"
            "- Maximum 1 promotion post — focus on the service itself, NOT social proof or results\n"
            "- behind_the_scenes: allowed on Facebook (max 1-2), max 1 on other platforms\n"
            "- Do NOT assign 'inspiration' with client success stories — this brand has ZERO client "
            "data. If using inspiration, frame as INDUSTRY INSIGHT or professional philosophy.\n"
            "- Do NOT assign 'user_generated' — there is no user content to reference.\n"
            "Strategy: prove expertise through DEPTH OF KNOWLEDGE, not breadth of claims.\n\n"
            "PLATFORM-SPECIFIC FORMAT RULES FOR THIN PROFILES:\n"
            "- Instagram education → ALWAYS 'carousel'. Cap 'video_first' at 1/week on IG.\n"
            "- LinkedIn → 'carousel' or 'original' (long-form). ALL LI posts = education. "
            "Never 'video_first' on LinkedIn for this brand.\n"
            "- X → 'thread_hook'. 1 post/week max. Always education.\n"
            "- Facebook → 'original'. Conversational + local tone. Best platform for BTS. "
            "MINIMUM 2 Facebook posts per week for local businesses — FB drives the most "
            "community engagement for professional services.\n"
            "- Facebook CTA: ALWAYS 'engagement' (genuine question).\n\n"
            "CTA RULES FOR THIN PROFILES:\n"
            "- Prefer 'implied' and 'engagement' — these work without social proof\n"
            "- Max 1 'conversion' per week — and only for a specific free resource (checklist, guide), "
            "NOT 'book a consultation' (no proof = no conversion trust)\n"
            "- 'none' is fine for pure educational threads\n"
        )
    elif _proof_tier == "partial_data":
        _pillar_guidance = (
            "\nPILLAR DISTRIBUTION — PARTIAL DATA:\n"
            f"Education should anchor the calendar. In a {num_days}-day plan:\n"
            "- At least 3 education posts\n"
            "- Promotion posts should lean on available data only (don't inflate)\n"
            "- Inspiration posts: use process authority, not fabricated client outcomes\n"
        )

    # ── Conditional angle list based on proof tier ──
    _angle_list = (
        "  - Teach a specific tip (name the actual thing, not just 'tips and tricks')\n"
        "  - Myth-bust (a common misconception in the industry)\n"
        "  - Behind-the-scenes or human moment (team, process, day-in-the-life)\n"
        "  - Timely hook (upcoming deadline, seasonal event, industry news)\n"
    )
    if _proof_tier == "thin_profile":
        _angle_list += (
            "  - Common mistake (walk through a specific error and the correct approach)\n"
            "  - Contrarian take (challenge conventional wisdom in the industry)\n"
        )
    else:
        _angle_list += (
            "  - Client perspective (anonymized pain point → resolution pattern)\n"
            "  - Contrarian take (challenge conventional wisdom in the industry)\n"
        )

    # ── Format guide override for thin-profile brands ──
    _format_override = ""
    if _proof_tier == "thin_profile":
        _format_override = (
            "\nFORMAT GUIDE OVERRIDE — THIN PROFILE (supersedes general guidance above):\n"
            "This brand has no face-on-camera talent, no testimonials, and no visual demos. "
            "AI-generated video clips look generic and hurt credibility for professional services.\n"
            "- LIMIT video_first to MAX 1 post across the ENTIRE week\n"
            "- Prefer 'carousel' for education (save-worthy, high-reach format)\n"
            "- Prefer 'thread_hook' on X (educational threads outperform video for B2B)\n"
            "- Never use video_first on LinkedIn for this brand type\n"
            "- 'Personal stories or testimonials' is NOT available as a video angle\n"
        )

    prompt = f"""You are a social media strategy expert and creative director.

Your job is to generate a {num_days}-day content calendar for the following brand.
The brand publishes on {num_platforms} platform(s): {platform_list}.

{temporal_context}

BRAND PROFILE:
{curated_profile}
{platform_rec_block}{trends_context}{hook_research_block}{visual_research_block}{video_research_block}
BUSINESS_EVENTS_THIS_WEEK: {business_events or "None provided — generate thematic pillars based on brand profile and current season/timing."}

Generate exactly {total_briefs} day briefs across {num_days} days and {num_platforms} platforms.

POSTING FREQUENCY (researched for this business type):
{freq_context}

MULTI-PLATFORM DAY DISTRIBUTION:
- Distribute each platform's posts across the {num_days} days as evenly as possible
- High-frequency platforms (e.g. 7 posts) appear every day
- Lower-frequency platforms (e.g. 3 posts) appear on select days — spread evenly, not clumped
- Multiple briefs on the same day_index MUST have different platforms
- Adapt content_theme, caption_hook, image_prompt, and derivative_type per platform
- Posts on the same day may share a thematic angle but MUST differ in format, tone, and hook
- Assign suggested_time from the platform's best posting times (rotate through them across the week)

Content pillars to use: education, inspiration, promotion, behind_the_scenes, user_generated
{_pillar_guidance}
{_FORMAT_GUIDE}
{_format_override}

CAROUSEL POSTS (IMPORTANT):
For Instagram and LinkedIn posts, decide whether the post works better as a SINGLE IMAGE or a CAROUSEL (3 slides).
Use derivative_type "carousel" for posts with educational, how-to, tip-based, listicle, before/after, or multi-point content.
Use derivative_type "original" for posts with single mood shots, announcements, quotes, or simple product features.

CONTENT REPURPOSING (IMPORTANT — follow this carefully):
Choose exactly 2 "hero" content ideas that will be repurposed across different platforms this week.
For each hero idea:
  - ONE day is the ORIGINAL hero post: derivative_type "original" or "carousel", ideally on the top-priority platform.
  - EXACTLY ONE other day repurposes that idea for a different platform and format:
      derivative_type must be one of: "carousel", "thread_hook", "blog_snippet", "story", "pin", "video_first"
  - All days in the same repurposing group MUST share the same pillar_id string (e.g., "series_0").
  - Adapt content_theme, caption_hook, and image_prompt to suit the derivative platform/format.
Remaining days (at least 3 of 7) each get their own UNIQUE topic — not a reword of the hero ideas.

CTA VARIETY (CRITICAL):
Each day's caption_hook and key_message must drive a DIFFERENT call to action. Track what you've used:
- Day 0: question CTA ("What's your biggest challenge with X?")
- Day 1: save CTA ("Save this for your next quarterly review")
- Day 2: share CTA ("Tag someone who needs this")
- Day 3: action CTA ("DM us 'GUIDE' for a free checklist")
- Day 4: story CTA ("Tell us your experience in the comments")
- Day 5+: mix from above, never repeat back-to-back
NEVER use "Follow for more" or "Like and share" — these are engagement bait from 2019.

CTA TYPE DEFINITIONS (assign one per day):
- "engagement": a conversational question or discussion prompt (e.g., "What's your biggest challenge with X?")
- "conversion": a direct action CTA (e.g., "DM us 'GUIDE'", "Book a call", "Save this")
- "implied": the content implies the next step without explicitly asking (e.g., teaching something that naturally leads to wanting the service)
- "none": no CTA — used for Mastodon, Threads, or pure educational content
DISTRIBUTION: across a 5-day plan, use at least 2 different types. Never use "conversion" back-to-back. Mastodon MUST be "none". Threads MUST be "engagement" or "none".

QUALITY STANDARDS FOR DAY BRIEFS:
BAD content_theme: "Tips and insights for our industry" (vague, generic)
GOOD content_theme: "3 hidden costs that eat into margins every Q1" (specific, timely, actionable)

BAD caption_hook: "Something worth stopping for" (meaningless)
BAD caption_hook: "Are you struggling with growth?" (banned pattern)
BAD caption_hook: "Did you know most businesses miss this?" (banned pattern)
GOOD caption_hook: "Most businesses lose 15% of revenue to this one overlooked process" (specific, creates curiosity)
BANNED HOOK PATTERNS (the content generator will reject these — do NOT suggest them):
  These patterns are banned ANYWHERE in the hook, not just at the start:
  "Are you...?", "Did you know...?", "What if...?", "In today's...",
  "As a...", "When it comes to...", "Here's the thing:", "The truth is:"
GOOD hooks use: specific numbers, contrarian statements, or pattern-interrupts.

BAD image_prompt: "Professional brand photo with clean composition"
GOOD image_prompt: "Overhead flatlay of business documents, laptop, and coffee on a dark oak desk, warm lighting, brand accent color in a pen and notebook"

ANGLE DIVERSITY (CRITICAL — this is what separates good content from spam):
Each day MUST cover a DIFFERENT angle. Even if the brand only offers one core service,
vary the ANGLE, not the message. Use these lenses:
{_angle_list}SELF-CHECK: If two content_themes could be summarized as the same sentence, they are TOO SIMILAR. Rewrite one.

Each day brief MUST have these exact fields:
- day_index: integer (0-based, so first day is 0, last day is {num_days - 1})
- platform: one of {json.dumps(platforms)}
- pillar: one of "education", "inspiration", "promotion", "behind_the_scenes", "user_generated"
- pillar_id: string — repurposing group ID (e.g., "series_0")
- content_theme: string — specific topic or angle (5-10 words)
- caption_hook: string — opening line to stop the scroll (under 15 words)
- key_message: string — main takeaway (1-2 sentences)
- image_prompt: string — detailed visual description for AI image generation (2-3 sentences)
- hashtags: array of relevant hashtag strings (without #). COUNT PER PLATFORM:
  Instagram 3-5, LinkedIn 3-5, X 1-2, Facebook 3-5, TikTok 4-6,
  Pinterest 2-5, YouTube Shorts 3-5, Threads 0-3, Mastodon 3-5 (CamelCase), Bluesky 1-3
- derivative_type: one of "original", "carousel", "thread_hook", "blog_snippet", "story", "pin", "video_first"
- event_anchor: string or null
- cta_type: one of "engagement", "conversion", "implied", "none" — the CTA style for this post
- suggested_time: string — best time to post this content (e.g. "6:00 PM"). Use the platform's researched best posting times, rotating through them.

Make the content_theme and caption_hook specific to the brand's industry, tone, and audience.
The image_prompt should reference the brand's visual style and colors if provided.
When writing image_prompt values, describe a SPECIFIC scene — subject, setting, lighting, camera angle, mood. Never write generic descriptions like 'professional photo of happy people'.

EVENT-AWARE PLANNING:
- If BUSINESS_EVENTS_THIS_WEEK is provided, identify 1-2 impactful events and make them content pillars
- Events become the "promotion" or "behind_the_scenes" day brief
- Add "event_anchor" field where content is tied to a business event (null otherwise)

Return ONLY a valid JSON array of {total_briefs} objects. No markdown, no extra text.
"""

    try:
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )

        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        if len(raw) > 500_000:
            logger.warning("LLM output too large (%d bytes), truncating", len(raw))
            raw = raw[:500_000]
        days = json.loads(raw)
        if not isinstance(days, list):
            raise ValueError(f"Expected JSON array, got {type(days)}")

        # Normalize and validate each day
        validated = []
        for i, day in enumerate(days[:total_briefs]):
            validated.append(
                _normalize_day(day, i, brand_profile, platforms, platform_trends_map, hook_research)
            )

        # Pad if AI returned fewer briefs than expected
        while len(validated) < total_briefs:
            validated.append(_fallback_day(len(validated), brand_profile, platforms))

        # Cap group sizes
        validated = _enforce_group_size(validated)

        # Platform concentration no longer needed — frequency research handles distribution

        trend_summary = {
            "researched_at": datetime.now(timezone.utc).isoformat(),
            "platform_trends": platform_trends_map,
            "visual_trends": visual_trends,
            "video_trends": video_trends,
        }
        return validated, trend_summary

    except json.JSONDecodeError as jde:
        logger.warning("Strategy agent: invalid JSON from LLM (first 200 chars): %s — %s", raw[:200], jde)
        return _fallback_plan(num_days, brand_profile, platforms), {}
    except Exception as e:
        logger.error(f"Strategy agent failed for brand {brand_id}: {e}")
        return _fallback_plan(num_days, brand_profile, platforms), {}


def _normalize_day(
    day: dict,
    index: int,
    brand_profile: dict,
    platforms: list[str],
    platform_trends_map: dict[str, dict] | None = None,
    hook_research: str = "",
) -> dict:
    """Ensure a day brief has all required fields with valid values."""
    all_platforms = platform_keys()
    platform = get_platform(day.get("platform", "")).key
    if platform not in platforms:
        platform = platforms[index % len(platforms)]

    pillar = day.get("pillar", "").lower().replace(" ", "_")
    if pillar not in PILLARS:
        pillar = PILLARS[index % len(PILLARS)]

    hashtags = day.get("hashtags", [])
    if not isinstance(hashtags, list):
        hashtags = []
    # Strip # prefix if present
    hashtags = [h.lstrip("#") for h in hashtags if isinstance(h, str)]

    derivative_type = str(day.get("derivative_type", "original")).lower()
    if derivative_type not in DERIVATIVE_TYPES:
        derivative_type = "original"

    result = {
        "day_index": int(day.get("day_index", index)),
        "platform": platform,
        "pillar": pillar,
        "pillar_id": str(day.get("pillar_id", f"series_{index}")),
        "content_theme": str(day.get("content_theme", f"Day {index + 1} content")),
        "caption_hook": str(day.get("caption_hook", "Something worth stopping for.")),
        "key_message": str(day.get("key_message", "Share your brand story.")),
        "image_prompt": str(day.get("image_prompt", f"Scene depicting {brand_profile.get('industry', 'business')} professional context for {brand_profile.get('business_name', 'your brand')}. Clean composition with clear focal point. Natural, professional lighting.")),
        "hashtags": hashtags[:8],
        "derivative_type": derivative_type,
        "event_anchor": day.get("event_anchor", None),
        "suggested_time": str(day.get("suggested_time", "")),
    }

    # Normalize cta_type with platform overrides
    cta_type = str(day.get("cta_type", "engagement")).lower()
    if cta_type not in ("engagement", "conversion", "implied", "none"):
        cta_type = "engagement"
    if platform == "mastodon":
        cta_type = "none"
    elif platform == "threads" and cta_type == "conversion":
        cta_type = "engagement"
    result["cta_type"] = cta_type

    # Attach platform trend intelligence for content creator
    if platform_trends_map and platform in platform_trends_map:
        result["platform_trends"] = platform_trends_map[platform]

    # Attach industry hook research for content creator
    if hook_research:
        result["hook_research"] = hook_research

    return result


def _fallback_day(
    index: int,
    brand_profile: dict,
    platforms: list[str] | None = None,
) -> dict:
    """Generate a single fallback day brief when AI fails."""
    if not platforms:
        platforms = ["instagram", "linkedin", "x", "facebook"]
    business_name = brand_profile.get("business_name", "your brand")
    industry = brand_profile.get("industry", "business")
    platform = platforms[index % len(platforms)]
    pillar = PILLARS[index % len(PILLARS)]

    themes_by_pillar = {
        "education": f"Tips and insights for {industry} enthusiasts",
        "inspiration": f"Why we do what we do at {business_name}",
        "promotion": f"Discover what makes {business_name} different",
        "behind_the_scenes": f"A day in the life at {business_name}",
        "user_generated": f"Our community shares their stories",
    }

    hooks_by_pillar = {
        "education": "Here's what most people don't know.",
        "inspiration": "This is the moment everything changed.",
        "promotion": "Meet the product you didn't know you needed.",
        "behind_the_scenes": "Ever wonder what happens behind closed doors?",
        "user_generated": "Real stories from real people.",
    }

    return {
        "day_index": index,
        "platform": platform,
        "pillar": pillar,
        "pillar_id": f"series_{index}",
        "content_theme": themes_by_pillar[pillar],
        "caption_hook": hooks_by_pillar[pillar],
        "key_message": f"Showcase the value and authenticity of {business_name}.",
        "image_prompt": (
            f"Scene depicting {industry} professional context for {business_name}. "
            "Clean composition with clear focal point, rule of thirds. "
            "Natural, professional lighting with soft shadows. "
            f"Brand visual style: {brand_profile.get('visual_style', 'modern and clean')}."
        ),
        "hashtags": [
            industry.lower().replace(" ", ""),
            business_name.lower().replace(" ", ""),
            pillar.replace("_", ""),
            platform,
            "smallbusiness",
            "contentcreator",
        ],
        "derivative_type": "original",
        "event_anchor": None,
        "cta_type": "engagement",
    }


def _enforce_group_size(days: list[dict], max_group_size: int = 3) -> list[dict]:
    """Break out excess days from oversized pillar_id groups.

    Prevents the LLM from assigning the same pillar_id to all days, which would
    color every card with the same series accent and make grouping meaningless.
    Any day beyond the first max_group_size in a group gets a unique standalone ID.
    """
    group_seen: dict[str, int] = {}
    standalone_idx = 9000  # start high to avoid collisions with "series_N" IDs
    result = []
    for day in days:
        pid = day["pillar_id"]
        count = group_seen.get(pid, 0)
        if count >= max_group_size:
            day = {**day, "pillar_id": f"series_{standalone_idx}", "derivative_type": "original"}
            standalone_idx += 1
        else:
            group_seen[pid] = count + 1
        result.append(day)
    return result


def _enforce_platform_concentration(
    days: list[dict],
    platforms: list[str],
    max_unique: int = 4,
) -> list[dict]:
    """Consolidate least-used platforms onto most-used if too many unique platforms appear."""
    from collections import Counter

    platform_counts = Counter(d["platform"] for d in days)
    unique = list(platform_counts.keys())
    if len(unique) <= max_unique:
        return days

    # Keep the top max_unique platforms by frequency
    top_platforms = [p for p, _ in platform_counts.most_common(max_unique)]
    result = []
    for day in days:
        if day["platform"] not in top_platforms:
            # Reassign to the most frequent platform
            old = day["platform"]
            day = {**day, "platform": top_platforms[0]}
            logger.info("Platform concentration: moved day %d from %s to %s",
                        day["day_index"], old, top_platforms[0])
        result.append(day)
    return result


def _fallback_plan(
    num_days: int,
    brand_profile: dict,
    platforms: list[str] | None = None,
) -> list[dict]:
    """Generate a complete fallback plan when AI strategy fails."""
    logger.warning("Using fallback content plan generation.")
    return [_fallback_day(i, brand_profile, platforms) for i in range(num_days)]


async def refresh_research(
    platforms: list[str], industry: str, primary_platform: str,
) -> dict:
    """Re-run all trend research tracks in parallel.

    Public API for routers — avoids importing private _research_* functions.
    Returns a trend_summary dict.
    """
    # Clear cache so research is truly fresh
    for p in platforms[:5]:
        try:
            await firestore_client.save_platform_trends(p, industry, {})
        except Exception as e:
            logger.warning("Failed to clear trend cache for %s: %s", p, e)
    try:
        await firestore_client.save_platform_trends(f"visual_{primary_platform}", industry, {})
        await firestore_client.save_platform_trends(f"video_{primary_platform}", industry, {})
    except Exception as e:
        logger.warning("Failed to clear visual/video trend cache: %s", e)

    platform_trends_results, visual_result, video_result = await asyncio.gather(
        asyncio.gather(
            *[_research_platform_trends(p, industry) for p in platforms[:5]],
            return_exceptions=True,
        ),
        _research_visual_trends(primary_platform, industry),
        _research_video_trends(primary_platform, industry),
        return_exceptions=True,
    )

    platform_trends_map = {}
    if isinstance(platform_trends_results, (list, tuple)):
        for p, r in zip(platforms[:5], platform_trends_results):
            if isinstance(r, dict):
                platform_trends_map[p] = r

    return {
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "platform_trends": platform_trends_map,
        "visual_trends": visual_result if isinstance(visual_result, dict) else None,
        "video_trends": video_result if isinstance(video_result, dict) else None,
    }
