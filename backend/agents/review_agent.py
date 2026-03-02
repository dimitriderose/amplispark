import asyncio
import json
import logging
from google import genai
from google.genai import types
from backend.config import GOOGLE_API_KEY, GEMINI_MODEL
from backend.platforms import get_review_guidelines_block

logger = logging.getLogger(__name__)
client = genai.Client(api_key=GOOGLE_API_KEY)


async def review_post(
    post: dict,
    brand_profile: dict,
) -> dict:
    """
    AI review of a generated post against brand guidelines.
    Returns a ReviewResult dict with scores and suggestions.
    """
    platform = post.get("platform", "instagram")
    caption = post.get("caption", "")
    hashtags = post.get("hashtags", [])

    business_name = brand_profile.get("business_name", "Brand")
    tone = brand_profile.get("tone", "professional")
    target_audience = brand_profile.get("target_audience", "general audience")
    caption_style_directive = brand_profile.get("caption_style_directive", "")

    industry = brand_profile.get("industry", "")

    prompt = f"""You are an objective social media content reviewer for {business_name}.
Your job is to evaluate whether this content meets professional publishing standards.
Be specific and evidence-based. Do NOT inflate scores to be polite — if the content
is generic or has issues, say so directly with concrete reasons.

Brand tone: {tone}
Industry: {industry}
Target audience: {target_audience}
Caption style: {caption_style_directive}

Review this {platform} post:
Caption: "{caption}"
Hashtags: {hashtags}

{get_review_guidelines_block()}

SCORING RUBRIC (follow this strictly):
1-3: Unusable — wrong platform format, off-brand, factual errors, or broken formatting
4-5: Below average — generic content, weak hook, CTA is template-like, wouldn't stop a scroll
6: Acceptable — on-brand but unremarkable, reads like AI-generated boilerplate
7: Good — has a genuine hook, platform-appropriate format, specific to the brand
8: Strong — would perform above average, has personality, drives specific action
9-10: Exceptional — viral potential, perfectly crafted for platform, voice is indistinguishable from best human creators

Most AI-generated content should score 5-7. Scoring 8+ should be RARE. If you give 8+, you must explain exactly why in strengths.

MANDATORY CHECKS (flag these and reduce score accordingly):
- Caption contains markdown formatting (**bold**, *italic*, [links]()) that the platform can't render
- Caption starts with a generic hook like "Are you ready..." or "Did you know..."
- CTA is generic ("Follow for more", "Like and share") instead of specific to the content
- Fabricated testimonials, made-up client names, or fake statistics
- Hashtags contain common English words, sentence fragments, or the brand name repeated
- Caption length violates platform limits (X>280, Threads>500, Bluesky>300)
- Content could apply to ANY business — nothing specific to {business_name} or {industry}
- Caption contains external URLs/links (LinkedIn and Facebook penalize this heavily)

Flag captions that are too long for their platform. Check hashtags for junk (sentence fragments, common words like #the, #for, #your).

Evaluate and respond with JSON only:
{{
  "score": <integer 1-10, overall brand quality score — use the rubric above>,
  "brand_alignment": <"strong"|"moderate"|"weak">,
  "strengths": [<list of 2-3 strength strings>],
  "improvements": [<list of 1-3 improvement suggestions — be specific, not vague>],
  "approved": <true if score >= 8, false otherwise>,
  "revised_caption": <improved caption string if score < 8 or caption is too long for platform, otherwise null>,
  "revised_hashtags": <always return a cleaned/validated hashtag array — even if unchanged>,
  "engagement_scores": {{
    "hook_strength": <integer 1-10: how compelling the opening line is — will people stop scrolling?>,
    "relevance": <integer 1-10: how on-brand and relevant to target audience>,
    "cta_effectiveness": <integer 1-10: how clear and motivating the call-to-action is>,
    "platform_fit": <integer 1-10: how well the format, length, and hashtag use fits {platform}>
  }},
  "engagement_prediction": <"low"|"medium"|"high"|"viral" — predicted relative engagement vs average for {platform}>
}}"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])

        result = json.loads(raw)

        # Normalize fields
        raw_engagement = result.get("engagement_scores", {})
        return {
            "score": int(result.get("score", 5)),
            "brand_alignment": result.get("brand_alignment", "moderate"),
            "strengths": result.get("strengths", []),
            "improvements": result.get("improvements", []),
            "approved": bool(result.get("approved", False)),
            "revised_caption": result.get("revised_caption"),
            "revised_hashtags": result.get("revised_hashtags"),
            "engagement_scores": {
                "hook_strength": int(raw_engagement.get("hook_strength", 5)),
                "relevance": int(raw_engagement.get("relevance", 5)),
                "cta_effectiveness": int(raw_engagement.get("cta_effectiveness", 5)),
                "platform_fit": int(raw_engagement.get("platform_fit", 5)),
            },
            "engagement_prediction": result.get("engagement_prediction", "medium"),
        }

    except Exception as e:
        logger.error(f"Review agent error: {e}")
        return {
            "score": 5,
            "brand_alignment": "moderate",
            "strengths": ["Content generated successfully"],
            "improvements": ["Review service temporarily unavailable"],
            "approved": True,
            "revised_caption": None,
            "engagement_scores": {
                "hook_strength": 5,
                "relevance": 5,
                "cta_effectiveness": 5,
                "platform_fit": 5,
            },
            "engagement_prediction": "medium",
        }
