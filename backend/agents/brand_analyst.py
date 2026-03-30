import asyncio
import json
import logging
import httpx
from google import genai
from google.genai import types
from backend.tools.web_scraper import fetch_website
from backend.tools.brand_tools import analyze_brand_colors, extract_brand_voice
from backend.config import GEMINI_MODEL, GOOGLE_API_KEY
from backend.clients import get_genai_client
from backend.services.storage_client import upload_brand_asset

logger = logging.getLogger(__name__)


async def _generate_style_reference(brand_id: str, profile: dict) -> str | None:
    """Generate a visual style reference image for the brand and upload to GCS.

    Returns the gs:// URI on success, None if generation fails.
    This is best-effort — callers must handle None gracefully.
    """
    client = get_genai_client()
    colors = ", ".join(profile.get("colors", []))
    tone = profile.get("tone", "professional")
    industry = profile.get("industry", "general")
    image_style_directive = profile.get("image_style_directive", "modern, clean")

    prompt = (
        f"Generate a style reference image for a {industry} brand with these characteristics:\n"
        f"Colors: {colors}\nTone: {tone}\nStyle directive: {image_style_directive}\n\n"
        "This is NOT a real post — it's a visual mood board reference showing:\n"
        "- The brand's color palette applied to a simple abstract composition\n"
        "- The lighting style (warm/cool/natural)\n"
        "- The texture and mood (minimal/rich/rustic)\n"
        "Generate a single cohesive image a designer could use as a reference."
    )

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.7,
            ),
        )
        if not response.candidates:
            return None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                mime = part.inline_data.mime_type or "image/png"
                ext = mime.split("/")[-1] if "/" in mime else "png"
                gcs_uri = await upload_brand_asset(
                    brand_id,
                    part.inline_data.data,
                    f"style_reference.{ext}",
                    mime,
                )
                return gcs_uri
    except Exception as e:
        logger.warning("Style reference generation failed for brand %s: %s", brand_id, e)
    return None


async def run_brand_analysis(
    description: str,
    website_url: str | None = None,
    uploaded_assets: list[str] | None = None,
    brand_id: str | None = None,
    social_voice_analysis: dict | None = None,
) -> dict:
    """Run the Brand Analyst agent to build a complete brand profile.

    Args:
        description: Free-text business description (min 20 chars, required)
        website_url: Optional website URL to scrape
        uploaded_assets: Optional list of GCS URIs for uploaded brand assets
        brand_id: Optional brand ID — used for style reference image upload
        social_voice_analysis: Optional existing social voice data; when present,
            the analyst uses it to inform tone and caption_style_directive so
            re-analysis doesn't override a voice the user has already connected.

    Returns: Complete brand profile dict
    """
    client = get_genai_client()

    # Step 1: Gather website data if URL provided
    website_data = {}
    if website_url:
        logger.info(f"Fetching website: {website_url}")
        website_data = await fetch_website(website_url)
        color_analysis = analyze_brand_colors(website_data.get("colors_found", []))
        voice_analysis = extract_brand_voice(website_data.get("text_content", ""))
    else:
        color_analysis = {}
        voice_analysis = {}

    # Step 2: Build analysis prompt
    website_context = ""
    if website_data and not website_data.get("error"):
        website_context = f"""
WEBSITE DATA:
- Title: {website_data.get('title', 'N/A')}
- Description: {website_data.get('description', 'N/A')}
- Text content (first 3000 chars): {website_data.get('text_content', '')[:3000]}
- Colors found on site: {', '.join(website_data.get('colors_found', [])[:10])}
- Navigation items: {', '.join(website_data.get('nav_items', [])[:10])}
- Pre-analyzed colors: Primary={color_analysis.get('primary', 'N/A')}, Secondary={color_analysis.get('secondary', 'N/A')}
- Detected brand voice signals: {', '.join(voice_analysis.get('detected_tones', []))}
"""

    # Inject existing social voice so re-analysis preserves the user's connected voice
    social_voice_context = ""
    if social_voice_analysis:
        chars = social_voice_analysis.get("voice_characteristics", [])
        phrases = social_voice_analysis.get("common_phrases", [])
        patterns = social_voice_analysis.get("successful_patterns", [])
        if chars or phrases:
            social_voice_context = f"""
EXISTING SOCIAL MEDIA VOICE (already analyzed from connected account):
- Voice characteristics: {', '.join(chars)}
- Common phrases: {', '.join(phrases)}
- Successful patterns: {', '.join(patterns)}

IMPORTANT: When setting TONE and CAPTION_STYLE_DIRECTIVE, ensure they are consistent with
and build upon this existing voice, not replace it. The goal is refinement, not reinvention.
"""

    prompt = f"""You are a brand strategist analyzing a business to build a comprehensive brand profile for social media content creation.

BUSINESS DESCRIPTION: {description}
{website_context}{social_voice_context}

Infer the business type and tailor your analysis:
- local_business: local/physical businesses (restaurants, salons, gyms, shops)
- service: consulting, coaching, agencies, professional services
- personal_brand: solopreneurs, creators, influencers, coaches with personal name brands
- ecommerce: online stores, DTC brands, product-focused businesses

Analyze the provided information and extract:

1. BUSINESS_NAME: The brand/business name (infer from description if needed)
2. BUSINESS_TYPE: One of: local_business, service, personal_brand, ecommerce
3. INDUSTRY: The industry category (e.g., "Food & Beverage", "Fitness & Wellness", "B2B Software")
4. TONE: Select exactly 3 adjectives from this list: professional, friendly, authoritative, playful, warm, bold, minimal, luxurious, casual, inspiring, educational, witty, empathetic, confident, sophisticated, approachable, artisanal, energetic
5. COLORS: Array of 3 hex colors [primary, secondary, accent]. If a website was provided, extract the ACTUAL brand colors from the site CSS/design. If no website, choose colors that are conventional and appropriate for the industry (e.g., blue/navy for finance, green for health/organic, warm tones for food)
6. TARGET_AUDIENCE: One sentence describing demographics and psychographics
7. VISUAL_STYLE: Select one from: clean-minimal, warm-organic, bold-vibrant, dark-luxurious, bright-playful, professional-corporate, rustic-artisan, modern-tech, elegant-refined
8. CONTENT_THEMES: Array of 5-8 content topics this brand should post about
9. COMPETITORS: Array of 2-3 competitor names or domains
10. IMAGE_STYLE_DIRECTIVE: A 2-3 sentence visual identity fragment. Be EXTREMELY specific about colors, lighting, composition, textures. This will be prepended to every image generation prompt.
    BAD: "professional and clean"
    GOOD: "warm earth tones with terracotta and sage green accents, soft natural lighting with golden hour warmth, minimalist compositions with generous whitespace, organic textures like linen and raw wood, shot from slightly above at 30-degree angle"
11. CAPTION_STYLE_DIRECTIVE: A 2-4 sentence writing RHYTHM guide. Describe tone, cadence, and stylistic patterns.
    INCLUDE: sentence length, punctuation style, paragraph rhythm, perspective (first/third person), vocabulary register, emoji usage policy
    EXCLUDE: Do NOT include content structure instructions. These are handled separately by the content system:
    - "start with a question" / "open with a question"
    - "follow with a solution" / "describe how the brand helps"
    - "include a call to action" / "end with a CTA"
    - "share a story/insight" / "include a statistic"
    - "use bullet points" / "use numbered lists"
    - "mention competitors" / "reference industry trends"
    BAD: "Start with a question about their pain point. Follow with how the brand solves it. End with a CTA."
    GOOD: "One-sentence hooks under 10 words. Personal anecdotes as the second beat. Counterintuitive insights as the third beat. Em dashes liberally. Never use exclamation marks."
12. IMAGE_GENERATION_RISK: Assess the risk of AI-generated images for this business type:
    - "high": food photography, fashion, real estate, jewelry, automotive, cosmetics, restaurants — industries where bad AI images are worse than no images. Authenticity is critical.
    - "medium": fitness, travel, education, events — AI images acceptable but user photos are strongly preferred for authenticity.
    - "low": SaaS, consulting, coaching, finance, tech — abstract/graphic/conceptual images work well for AI generation.
13. BYOP_RECOMMENDATION: A concise 1-2 sentence recommendation explaining whether they should use their own photos.
    For "high" risk: strongly recommend using real photos with an industry-specific reason.
    For "medium": gently suggest that real photos improve engagement.
    For "low": confirm that AI-generated images work great for their content type.

Return ONLY a valid JSON object with these exact keys:
{{
  "business_name": "string",
  "business_type": "local_business|service|personal_brand|ecommerce",
  "industry": "string",
  "tone": "string (comma-separated adjectives)",
  "colors": ["#hex1", "#hex2", "#hex3"],
  "target_audience": "string",
  "visual_style": "string",
  "content_themes": ["theme1", "theme2", ...],
  "competitors": ["competitor1", "competitor2"],
  "image_style_directive": "string",
  "caption_style_directive": "string",
  "image_generation_risk": "high|medium|low",
  "byop_recommendation": "string"
}}
"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.15,
                response_mime_type="application/json",
            ),
        )

        profile = json.loads(response.text.strip())

    except Exception as e:
        logger.error(f"Brand analysis failed: {e}")
        # Fallback: return minimal profile from description
        profile = _fallback_profile(description, website_url)

    # Generate visual style reference image (best-effort)
    if brand_id:
        style_ref_gcs_uri = await _generate_style_reference(brand_id, profile)
        if style_ref_gcs_uri:
            profile["style_reference_gcs_uri"] = style_ref_gcs_uri

    # Download logo from website if detected and no user-uploaded logo exists
    scraped_logo_url = website_data.get("logo_url") if website_data else None
    if scraped_logo_url and brand_id:
        try:
            logo_gcs_uri = await _download_website_logo(brand_id, scraped_logo_url)
            if logo_gcs_uri:
                profile["logo_url"] = logo_gcs_uri
                logger.info("Saved website logo for brand %s: %s", brand_id, logo_gcs_uri)
        except Exception as e:
            logger.warning("Failed to download website logo: %s", e)

    return profile


async def _download_website_logo(brand_id: str, logo_url: str) -> str | None:
    """Download a logo image from a URL and upload to GCS. Returns GCS URI or None."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(logo_url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; AmplisparkBot/1.0)"
            })
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            logger.warning("Logo URL returned non-image content-type: %s", content_type)
            return None

        logo_bytes = resp.content
        if len(logo_bytes) < 200:  # too small to be a real logo
            return None

        # Determine filename from content type
        ext = "png"
        if "jpeg" in content_type or "jpg" in content_type:
            ext = "jpg"
        elif "svg" in content_type:
            ext = "svg"
        elif "webp" in content_type:
            ext = "webp"

        gcs_uri = await upload_brand_asset(brand_id, logo_bytes, f"logo.{ext}", content_type)
        return gcs_uri
    except Exception as e:
        logger.warning("Logo download failed from %s: %s", logo_url, e)
        return None


def _fallback_profile(description: str, website_url: str | None) -> dict:
    """Minimal fallback brand profile when AI analysis fails."""
    words = description.split()
    business_name = " ".join(words[:3]).title() if len(words) >= 3 else description[:30].title()
    return {
        "business_name": business_name,
        "business_type": "general",
        "industry": "General Business",
        "tone": "professional, approachable, authentic",
        "colors": ["#5B5FF6", "#8B5CF6", "#FF6B6B"],
        "target_audience": "Adults 25-45 interested in this type of business",
        "visual_style": "clean, modern, professional aesthetic",
        "content_themes": ["behind the scenes", "tips and advice", "product highlights", "customer stories", "team culture"],
        "competitors": [],
        "image_style_directive": "clean, modern aesthetic with consistent brand colors, professional lighting, crisp compositions with generous whitespace",
        "caption_style_directive": "Short punchy sentences under 15 words. Mix first-person and second-person perspective. Use em dashes for asides. Conversational register — write like a knowledgeable friend, not a brochure.",
        "image_generation_risk": "low",
        "byop_recommendation": "AI-generated images work well for this business type. For best results, upload your own photos when you have them.",
    }
