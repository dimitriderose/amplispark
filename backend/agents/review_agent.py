import asyncio
import json
import logging
from google import genai
from google.genai import types
from backend.config import GOOGLE_API_KEY, GEMINI_MODEL
from backend.clients import get_genai_client
from backend.platforms import get_review_guidelines_block, get as get_platform

logger = logging.getLogger(__name__)


# --- Platform-specific review checks (Fix 11d) ---

_PLATFORM_REVIEW_CHECKS = {
    "instagram": (
        "INSTAGRAM-SPECIFIC CHECKS:\n"
        "- FOLD CHECK: First 125 chars must be a complete, compelling hook. "
        "If the first 125 chars are mid-sentence or contain the brand name, deduct 1 point.\n"
        "- MOBILE READABILITY: Paragraphs longer than 2 sentences — deduct 1 point."
    ),
    "linkedin": (
        "LINKEDIN-SPECIFIC CHECKS:\n"
        "- FOLD CHECK: First 140 chars must be a complete hook that compels 'see more' click. "
        "If weak or mid-sentence, deduct 2 points — this determines all LinkedIn reach.\n"
        "- MOBILE READABILITY: Paragraphs longer than 2 sentences — deduct 1 point. "
        "70%+ of LinkedIn consumption is mobile.\n"
        "- EXTERNAL LINKS in post body — deduct 3 points (40-50% reach penalty)."
    ),
    "tiktok": (
        "TIKTOK-SPECIFIC CHECKS:\n"
        "- CAPITALIZATION: Formal/corporate capitalization (e.g., 'At Derose & Associates, "
        "We Help...') reads as AI-generated on TikTok — deduct 1 point. "
        "TikTok voice is overwhelmingly lowercase.\n"
        "- FOLD CHECK: First 55-75 chars appear before truncation. Must hook immediately.\n"
        "- KEYWORD DENSITY: Carousel/photo posts should contain 2-3 searchable keywords "
        "someone would type into TikTok search."
    ),
    "facebook": (
        "FACEBOOK-SPECIFIC CHECKS:\n"
        "- SHAREABILITY: Would a reader share this with a friend? If purely promotional, "
        "deduct 2 points. Facebook organic reach requires shares.\n"
        "- COMMUNITY ENGAGEMENT: Does this invite personal stories or opinions? "
        "Broadcast-style posts get suppressed — conversation starters get amplified.\n"
        "- ENGAGEMENT CTA: On Facebook, engagement questions should be the default "
        "(not conversion CTAs). If a non-boosted post uses a conversion CTA, deduct 1 point."
    ),
    "x": (
        "X-SPECIFIC CHECKS:\n"
        "- CHARACTER COUNT: Hard 280 limit per tweet. Flag any tweet exceeding 280.\n"
        "- HASHTAG BLOCKS: Any post with 2+ hashtags grouped together — deduct 1 point "
        "(dead giveaway of AI-generated X content)."
    ),
    "pinterest": (
        "PINTEREST-SPECIFIC CHECKS:\n"
        "- SEO CHECK: Pin title and description must contain searchable keywords. "
        "If the title is clever/witty instead of keyword-rich, deduct 2 points "
        "(Pinterest is a search engine — cleverness kills discoverability).\n"
        "- NO HASHTAGS: Any hashtags in the content — deduct 1 point.\n"
        "- NO FIRST-PERSON: 'We', 'our', 'I' in pin description — deduct 1 point. "
        "Pins are discovered by strangers via search, not followers.\n"
        "- ACTION VERBS: Title should contain an action verb ('Try', 'Learn', 'Get'). "
        "Passive titles get fewer clicks.\n"
        "- TITLE LENGTH: Title over 100 chars — deduct 2 points."
    ),
    "youtube_shorts": (
        "YOUTUBE SHORTS-SPECIFIC CHECKS:\n"
        "- FORMAT: This is ALWAYS a video post. Caption must be a teaser, not standalone text.\n"
        "- CAPTION LENGTH: Flag if >200 chars.\n"
        "- #SHORTS HASHTAG: If '#Shorts' appears, deduct 1 point (unnecessary).\n"
        "- KEYWORD SEO: Caption should contain 2-3 searchable keywords for YouTube Search.\n"
        "- SUBSCRIBE CTA: 'Subscribe' is a valid CTA — do NOT penalize it under generic CTA check."
    ),
    "threads": (
        "THREADS-SPECIFIC CHECKS:\n"
        "- PROMOTIONAL CONTENT: If the post reads like a brand announcement or marketing message, "
        "deduct 3 points. Threads algorithm actively suppresses promotion.\n"
        "- CONVERSION CTA: Any conversion CTA ('Book a call', 'DM us', 'Visit our site') "
        "— deduct 2 points. Engagement questions only.\n"
        "- AUTHENTICITY: Does this sound like a real person sharing a thought, or a brand "
        "broadcasting? If broadcasting, deduct 2 points.\n"
        "- LENGTH: Flag if >400 chars. Sweet spot is 200-300."
    ),
    "mastodon": (
        "MASTODON-SPECIFIC CHECKS:\n"
        "- CAMELCASE HASHTAGS: All hashtags must be CamelCase (#SmallBusiness, not #smallbusiness). "
        "Accessibility requirement for screen readers. Non-CamelCase — deduct 2 points.\n"
        "- ENGAGEMENT BAIT: Any explicit engagement request ('What do you think?', "
        "'Boost if you agree') — deduct 2 points. Mastodon treats this as spam.\n"
        "- CORPORATE VOICE: If the post sounds like a marketing department wrote it, "
        "deduct 2 points.\n"
        "- CONVERSION CTA: Any conversion CTA — deduct 3 points.\n"
        "- CONTENT WARNING: Flag if the post touches sensitive topics without noting a CW may be needed."
    ),
    "bluesky": (
        "BLUESKY-SPECIFIC CHECKS:\n"
        "- CHARACTER COUNT: Hard 300-char limit. Flag any post exceeding 300.\n"
        "- THREAD FORMAT: Each post must be <=300 chars (NOT 280).\n"
        "- ENGAGEMENT BAIT: Generic engagement questions ('What do you think?', 'Thoughts?') "
        "— deduct 2 points.\n"
        "- SPECIFICITY: Posts must be about a specific topic. Vague motivational content "
        "('Believe in your journey') — deduct 2 points.\n"
        "- PLATITUDES: Bluesky users actively reject generic platitudes."
    ),
}

# --- Pillar-specific depth checks for ALL derivatives ---

_PILLAR_DEPTH_CHECKS = {
    "carousel": {
        "education": "Each middle slide must teach a SPECIFIC named technique/framework/method with concrete example/number/scenario",
        "promotion": "Each middle slide must highlight a SPECIFIC feature/benefit with concrete use case/outcome/comparison",
        "inspiration": "Each middle slide must advance a SPECIFIC transformation story with concrete details",
        "behind_the_scenes": "Each middle slide must reveal a REAL process step/tool/decision/mistake with specific details",
        "user_generated": "Each middle slide must feature AUTHENTIC specifics — real quotes, specific results, named situations",
    },
    "video_first": {
        "education": "Teaser should hint at the technique or I-wish-I-knew-this-sooner moment",
        "promotion": "Teaser should hint at the product reveal or result without describing it",
        "inspiration": "Teaser should hint at the emotional payoff or transformation",
        "behind_the_scenes": "Teaser should hint at the behind-the-curtain moment people rarely see",
        "user_generated": "Teaser should hint at the customer reaction or real-world result",
    },
    "thread_hook": {
        "education": "Each post must teach a specific technique or principle — not generic advice",
        "promotion": "Each post must showcase a distinct feature, benefit, or use case",
        "inspiration": "Each post must advance a transformation narrative or motivational arc",
        "behind_the_scenes": "Each post must reveal a process step, team moment, or behind-the-curtain detail",
        "user_generated": "Each post must highlight a customer experience, community moment, or real result",
    },
    "story": {
        "education": "Lead with a surprising fact or quick-tip hook",
        "promotion": "Lead with a bold product claim or irresistible offer",
        "inspiration": "Lead with a big emotion or transformation moment",
        "behind_the_scenes": "Lead with a candid peek or you-were-not-supposed-to-see-this energy",
        "user_generated": "Lead with a customer shoutout or community highlight",
    },
    "blog_snippet": {
        "education": "Open with an opinion-forward statement or contrarian take on a common practice",
        "promotion": "Open with a bold product/service claim or problem-solution hook",
        "inspiration": "Open with a vivid transformation moment or aspirational statement",
        "behind_the_scenes": "Open with a candid reveal about how something actually works internally",
        "user_generated": "Open with a spotlight on a real customer moment or community insight",
    },
    "pin": {
        "education": "Title must lead with the technique or framework name",
        "promotion": "Title must lead with the product/service benefit",
        "inspiration": "Title must lead with the transformation or aspirational outcome",
        "behind_the_scenes": "Title must lead with the process or behind-the-curtain angle",
        "user_generated": "Title must lead with the customer story or community angle",
    },
    "original": {
        "education": "Body must teach a specific technique, framework, or actionable method — not general advice",
        "promotion": "Body must showcase specific features, benefits, or a compelling use case — not generic marketing",
        "inspiration": "Body must tell a concrete transformation story with real details — not vague motivation",
        "behind_the_scenes": "Body must reveal real process details, tools, or decisions — not surface-level",
        "user_generated": "Body must feature authentic quotes, specific results, or named situations",
    },
}

# --- Derivative-specific format checks ---

_DERIVATIVE_CHECKS = {
    "video_first": (
        "VIDEO-FIRST FORMAT CHECK:\n"
        "- Caption = 1-3 sentences MAX (teaser, not article)\n"
        "- Char limit: {char_limit} chars. Flag if exceeded.\n"
        "- Must create curiosity, not describe the video. Reads like standalone post = deduct 2 pts\n"
        "- CTA rules apply but relaxed — cliffhanger works as implied CTA\n"
        "- No brand paragraph — video speaks for brand\n"
        "- PILLAR ({content_pillar}): {pillar_depth_check}\n"
        "- REVISION SCOPE: target teaser angle or length — do NOT restructure into full post"
    ),
    "carousel": (
        "CAROUSEL FORMAT CHECK:\n"
        "- Must have EXACTLY {expected_slide_count} slides: Slide 1: through Slide {expected_slide_count}:\n"
        "- 'Slide N:' labels are MACHINE-PARSED to generate slide images — "
        "revision_notes must NEVER remove, merge, or renumber them\n"
        "- Slide 1 = hook (<=10 words), no banned hooks\n"
        "- Slide headlines <=50 chars, <=8 words. Generic labels (Technique, Method, Step N, "
        "Feature, Benefit) = deduct 1 pt. Must NAME the specific technique/feature/moment.\n"
        "- Middle slides: clear PROGRESSION. Chopped paragraphs = deduct 1 pt. "
        "Repeated ideas = deduct 1 pt.\n"
        "- Each content slide ends with a different open loop driving swipe\n"
        "- Final slide: clear takeaway + CTA specific to content topic\n"
        "- Char limit: {char_limit} chars total. Flag if exceeded.\n"
        "- PILLAR ({content_pillar}): {pillar_depth_check}\n"
        "- Generic content (any brand could use it) = deduct 2 pts\n"
        "- Caption vs slides: caption must NOT duplicate slide text. >50% verbatim = deduct 2 pts\n"
        "- REVISION SCOPE: target SPECIFIC slides by number (e.g., 'Slide 3: replace generic "
        "headline'). Do NOT suggest removing/merging/renumbering slides."
    ),
    "thread_hook": (
        "THREAD FORMAT CHECK:\n"
        "- 3-7 posts total. Flag if <3 or >7\n"
        "- X threads use 1/, 2/, 3/. Bluesky threads do NOT need numbering.\n"
        "- Per-post limit: X = 280 chars, Bluesky = 300 chars. Flag any post exceeding limit.\n"
        "- 1/ must be a hook, no banned patterns\n"
        "- Each post = COMPLETE standalone thought. Transition-only posts = deduct 1 pt.\n"
        "- Repeated ideas = deduct 1 pt\n"
        "- PILLAR ({content_pillar}): {pillar_depth_check}\n"
        "- REVISION SCOPE: target SPECIFIC post numbers (e.g., '3/: add concrete example'). "
        "Do NOT remove/merge/renumber posts."
    ),
    "story": (
        "STORY FORMAT CHECK:\n"
        "- <=50 words total. Char limit: {char_limit} chars. Flag if exceeded.\n"
        "- Must be punchy and immediate — no preamble\n"
        "- CTA REQUIRED (swipe up / reply / DM). Missing CTA = deduct 2 pts\n"
        "- No hashtags in body text\n"
        "- PILLAR ({content_pillar}): {pillar_depth_check}\n"
        "- REVISION SCOPE: surgical edits only (e.g., 'replace opening with punchier hook')"
    ),
    "blog_snippet": (
        "BLOG SNIPPET FORMAT CHECK:\n"
        "- 150-200 words total. Char limit: {char_limit} chars. Flag if exceeded.\n"
        "- Opens with bold opinion or specific contrarian question (not generic 'Are you...?')\n"
        "- 2-3 short paragraphs with real insight — not padding\n"
        "- Closing question specific to content topic (not generic 'What do you think?')\n"
        "- PILLAR ({content_pillar}): {pillar_depth_check}\n"
        "- REVISION SCOPE: target opening, body insight, or closing question"
    ),
    "pin": (
        "PIN FORMAT CHECK:\n"
        "- Must have PIN TITLE: and PIN DESCRIPTION: labels (machine-parsed downstream)\n"
        "- PIN TITLE <=100 chars, keyword-rich, action verb, benefit-driven\n"
        "- PIN DESCRIPTION 200-250 chars, natural SEO keywords\n"
        "- No emoji, no hashtags, no first-person\n"
        "- PILLAR ({content_pillar}): {pillar_depth_check}\n"
        "- REVISION SCOPE: specify which part (e.g., 'PIN TITLE: add action verb'). "
        "Do NOT remove PIN TITLE:/PIN DESCRIPTION: labels."
    ),
    "original": (
        "STANDARD POST FORMAT CHECK:\n"
        "- Hook before platform fold (IG <=125, LinkedIn <=140, X <=280 total, Bluesky <=300)\n"
        "- Body: 1-2 sentence paragraphs for mobile readability. >2 sentences = deduct 1 pt\n"
        "- Char limit: {char_limit} chars. Flag if exceeded.\n"
        "- PILLAR ({content_pillar}): {pillar_depth_check}\n"
        "- Close must match assigned CTA type\n"
        "- REVISION SCOPE: target hook, body content, or CTA"
    ),
}


async def review_post(
    post: dict,
    brand_profile: dict,
    social_proof_tier: str | None = None,
    cta_type: str | None = None,
) -> dict:
    """
    AI review of a generated post against brand guidelines.
    Returns a ReviewResult dict with scores and suggestions.
    """
    # Fix 11a: Extract derivative_type from post
    derivative_type = post.get("derivative_type", "original")
    platform = post.get("platform", "instagram")
    caption = post.get("caption", "")
    hashtags = post.get("hashtags", [])
    content_theme = post.get("content_theme", "")
    content_pillar = post.get("pillar", "education")

    # Platform spec lookups for char limits and slide counts
    _spec = get_platform(platform)
    _char_limit = (_spec.char_limits or {}).get(derivative_type) or (_spec.char_limits or {}).get("default", 0)

    business_name = brand_profile.get("business_name", "Brand")
    tone = brand_profile.get("tone", "professional")
    target_audience = brand_profile.get("target_audience", "general audience")
    industry = brand_profile.get("industry", "")

    # Fix 11b: Wrap caption_style_directive to scope to tone only
    _raw_style = brand_profile.get("caption_style_directive", "")
    caption_style_directive = (
        f"Brand writing rhythm (for TONE reference only — do not penalize "
        f"content that deviates from structural instructions like 'start with a question' "
        f"or 'include a CTA'):\n{_raw_style}" if _raw_style else ""
    )

    # Build platform-specific and derivative-specific check blocks
    platform_checks = _PLATFORM_REVIEW_CHECKS.get(platform, "")
    derivative_checks = _DERIVATIVE_CHECKS.get(derivative_type, "")

    # Resolve pillar-adaptive depth check and platform data for all derivatives
    if derivative_checks:
        _depth_map = _PILLAR_DEPTH_CHECKS.get(derivative_type, {})
        _depth = _depth_map.get(content_pillar, _depth_map.get("education", ""))
        derivative_checks = derivative_checks.format(
            content_pillar=content_pillar,
            pillar_depth_check=_depth,
            expected_slide_count=_spec.carousel_slide_count,
            char_limit=_char_limit or "no hard limit",
        )

    # Conditional social proof check for thin-profile brands
    social_proof_check = ""
    if social_proof_tier in ("thin_profile", None) or not brand_profile.get("storytelling_strategy"):
        social_proof_check = (
            "THIN-PROFILE SOCIAL PROOF CHECK (CRITICAL — this brand has NO verified client data):\n"
            "- ANY reference to clients, client counts, years of experience, or client outcomes "
            "is FABRICATED — deduct 3 points\n"
            "- Specific dollar amounts, percentages, or statistics not in the brand profile — "
            "deduct 3 points (these are made up)\n"
            "- 'We helped a client...', 'One client saved...', 'A local business...' — "
            "ALL fabricated, deduct 3 points\n"
            "- 'We've seen...', 'Our clients...', 'Many businesses...' — deduct 2 points\n"
            "- The ONLY valid proof is teaching a specific, actionable insight\n"
            "- SPECIFICITY for thin-profile brands means TEACHING DEPTH in the brand's industry — "
            "not brand stories, client data, or unique approach claims. A post that teaches a concrete "
            "technique IS specific, even if it doesn't mention the brand's track record.\n"
            "- IMPORTANT FOR REVISION_NOTES: Do NOT suggest 'add brand-specific examples' or "
            "'reference the brand's unique approach' — this brand has NO data for that. "
            "Instead suggest: 'replace the fabricated claim with a specific, teachable insight' "
            "or 'remove the client story and teach a concrete technique instead.'\n\n"
        )

    # Conditional CTA type enforcement
    cta_check = ""
    if cta_type:
        _CTA_REVIEW = {
            "engagement": (
                "CTA TYPE CHECK: This post was assigned an ENGAGEMENT CTA.\n"
                "- Must end with a conversational question or discussion prompt\n"
                "- Any conversion language ('book', 'DM', 'link in bio', 'visit', 'save this') — deduct 2 points\n"
                "- For cta_effectiveness scoring: score 8-10 if the post ends with a specific, "
                "thought-provoking question relevant to the content. Score 5-7 if the question is generic "
                "('What do you think?', 'Thoughts?'). Score 1-4 only if there's no question at all "
                "or it includes conversion language.\n\n"
            ),
            "conversion": (
                "CTA TYPE CHECK: This post was assigned a CONVERSION CTA.\n"
                "- Must end with one clear action step (book, DM, save, visit)\n"
                "- Should NOT also have an engagement question (dual CTA) — deduct 1 point\n"
                "- For cta_effectiveness scoring: score 8-10 if the CTA is clear, specific, and has "
                "one action step. Score 5-7 if the CTA is present but vague or there's a dual CTA. "
                "Score 1-4 only if there's no conversion CTA at all.\n\n"
            ),
            "implied": (
                "CTA TYPE CHECK: This post was assigned an IMPLIED CTA.\n"
                "- Content should naturally lead reader to want the service\n"
                "- Any explicit CTA (questions, 'book a call', 'DM us') — deduct 2 points\n"
                "- For cta_effectiveness scoring: score 8-10 if the content naturally implies value or "
                "next steps without any explicit ask. Score 5-7 if the implication is weak but no explicit "
                "CTA exists. Do NOT score low for 'no explicit CTA' — implied is the intent.\n\n"
            ),
            "none": (
                "CTA TYPE CHECK: This post was assigned NO CTA.\n"
                "- Any call to action whatsoever (questions, conversion, 'thoughts?') — deduct 2 points\n"
                "- For cta_effectiveness scoring: score 8-10 if the post correctly avoids CTAs. "
                "Do NOT score low for 'no CTA' — that is the INTENDED behavior for this post.\n\n"
            ),
        }
        cta_check = _CTA_REVIEW.get(cta_type, "")

    # ── Thin-profile scoring rubric adjustment ──
    _thin_profile_rubric = ""
    if social_proof_tier in ("thin_profile", None) or not brand_profile.get("storytelling_strategy"):
        _thin_profile_rubric = (
            "\nTHIN-PROFILE SCORING NOTE:\n"
            "This brand has no client data. Education depth IS the differentiator.\n"
            "- Score 7+ REQUIRES teaching a specific, named technique or actionable insight\n"
            "- Generic advice ('plan ahead', 'stay organized', 'consult a professional') caps at 6\n"
            "- Content that could apply to any business in the industry without changes caps at 5\n"
        )

    prompt = f"""You are an objective social media content reviewer for {business_name}.
Your job is to evaluate whether this content meets professional publishing standards.
Be specific and evidence-based. Do NOT inflate scores to be polite — if the content
is generic or has issues, say so directly with concrete reasons.

Brand tone: {tone}
Industry: {industry}
Target audience: {target_audience}
{caption_style_directive}

Review this {platform} post (derivative type: {derivative_type}):
Content topic: {content_theme}
Caption: "{caption}"
Hashtags: {hashtags}

{get_review_guidelines_block()}

SCORING RUBRIC (follow this strictly):
1-3: Unusable — wrong platform format, off-brand, factual errors, broken formatting
4-5: Below average — brand paragraphs, generic hooks, dual CTAs, vague social proof,
     or content that could apply to any business
6: Acceptable — on-brand, no major quality violations, but unremarkable.
   One minor issue (slightly generic hook, or one too many emojis)
7: Good — no quality rule violations, genuine hook with a pattern interrupt,
   platform-appropriate format, specific to the brand
8: Strong — teaches something actionable, hook creates a knowledge gap,
   CTA matches post intent, would perform above average on {platform}
9-10: Exceptional — viral potential, perfectly crafted for platform algorithm,
   voice indistinguishable from best human creators
{_thin_profile_rubric}
Most AI-generated content should score 5-7. Scoring 8+ should be RARE.
If you give 8+, you must explain exactly why in strengths.

MANDATORY CHECKS (flag these and reduce score accordingly):
- Caption contains markdown formatting (**bold**, *italic*, [links]()) — instant fail
- BANNED HOOKS: Opens with "Are you...?", "Did you know...?", "What if...?",
  "In today's...", "As a...", "When it comes to...", "Here's the thing:",
  "The truth is:", "Let me tell you something:", "Stop [verb]-ing...",
  "Most people don't realize...", "Here's the truth about...",
  "Nobody is talking about..." — deduct 2 points.
  EXCEPTION: "Stop [verb]-ing" is acceptable on TikTok/Reels where imperatives are native.
- BRAND PARAGRAPH: A full paragraph dedicated to describing the brand's services,
  history, or value proposition (brand-as-subject, not narrator) — deduct 2 points
- CTA CONFLICT: Both an engagement question AND a conversion CTA in the same post — deduct 1 point
- VAGUE SOCIAL PROOF: "We've seen countless...", "Many businesses...",
  "So many clients..." without real numbers — deduct 1 point
- FABRICATED CLAIMS: Made-up statistics, dollar amounts, percentages, or client
  stories not supported by brand profile data — deduct 2 points
- GENERIC CTAs: "Follow for more!", "Like and share", "Drop a comment below!" — deduct 2 points
- EMOJI OVERLOAD: More than 2 emojis in a single caption — deduct 1 point
- EMOJI BULLET LISTS: Using emojis as bullet points (fire Point one, pin Point two) — deduct 1 point
- REPETITIVE STRUCTURE: 3+ sentences starting with "It's" or "This is" — deduct 1 point
- EXCLAMATION SPAM: More than 1 sentence ending with "!" — deduct 1 point
- THIRD-PERSON VOICE: Writing about the brand in third person instead of first person — deduct 1 point
- HASHTAG COUNT: Exceeds platform best practice (Instagram 3-5, X 0-1, LinkedIn 3-5, TikTok 4-6,
  Pinterest 0, YouTube Shorts 3-5, Threads 0-3, Mastodon 3-5 CamelCase, Bluesky 1-3) — deduct 1 point
- Caption length violates platform limits (X>280, Threads>500, Bluesky>300)
- Content could apply to ANY business — nothing specific to {business_name}
- Hashtags contain sentence fragments, common words, or repeated brand name
- Caption contains external URLs/links (LinkedIn/Facebook penalize heavily)
- MOMENTUM KILLERS: "Sound familiar?", "Let's break it down",
  "Here's why it matters", "Let me explain" — deduct 1 point

{platform_checks}

{derivative_checks}

{social_proof_check}{cta_check}CAPTION QUALITY CHECK (carousel and thread posts):
- Caption must NOT duplicate slide/post text — it should add context, a personal angle, or a hook
- Mobile readability: insert line breaks every 2-3 sentences. Wall of text — deduct 1 point
- Must end with an engagement prompt or CTA appropriate to the assigned cta_type
- Caption that reads like a summary of the slides/posts — deduct 1 point

Flag captions that are too long for their platform. Check hashtags for junk (sentence fragments, common words like #the, #for, #your).

Evaluate and respond with JSON only:
{{
  "score": <integer 1-10, overall brand quality score — use the rubric above>,
  "brand_alignment": <"strong"|"moderate"|"weak">,
  "strengths": [<list of 2-3 strength strings>],
  "improvements": [<list of 1-3 improvement suggestions — be specific, not vague>],
  "approved": <true if score >= 8, false otherwise>,
  "revision_notes": <if score < 8: 1-3 SPECIFIC, SCOPED edit instructions. For structured formats (carousel, thread, pin), target individual sections by label (e.g., "Slide 3: replace generic headline with named technique", "3/: add a concrete example", "PIN TITLE: add action verb and primary keyword"). Do NOT suggest removing, merging, or renumbering structural labels (Slide N:, 1/, PIN TITLE:, PIN DESCRIPTION:). If score >= 8, null.>,
  "revised_hashtags": <cleaned/validated hashtag array. RULES: (1) every hashtag must match
    a topic ACTUALLY discussed in the caption — remove mismatches (e.g., #SOPs when SOPs
    aren't mentioned), (2) no sentence fragments or common words, (3) respect platform limits:
    IG 3-5, LinkedIn 3-5, TikTok 4-6, X 0-1, Pinterest 0, YT Shorts 3-5, Threads 0-3,
    Mastodon 3-5 CamelCase, Bluesky 1-3>,
  "engagement_scores": {{
    "hook_strength": <integer 1-10: how compelling the opening line is — will people stop scrolling?>,
    "relevance": <integer 1-10: how on-brand and relevant to target audience>,
    "cta_effectiveness": <integer 1-10: how clear and motivating the call-to-action is>,
    "platform_fit": <integer 1-10: how well the format, length, and hashtag use fits {platform}>,
    "teaching_depth": <integer 1-10: pillar-specific depth score.
      education: 8-10 = named technique/framework + example, 5-7 = general advice, 1-4 = platitudes.
      promotion: 8-10 = specific feature + use case, 5-7 = benefits without proof, 1-4 = generic claims.
      inspiration: 8-10 = concrete transformation with details, 5-7 = relatable but vague, 1-4 = generic.
      behind_the_scenes: 8-10 = real process detail + specifics, 5-7 = surface peek, 1-4 = staged.
      user_generated: 8-10 = authentic quotes/results, 5-7 = paraphrased, 1-4 = fabricated.
      This post's pillar: {content_pillar}. Score accordingly.>
  }},
  "engagement_prediction": <"low"|"medium"|"high"|"viral" — predicted relative engagement vs average for {platform}>
}}"""

    try:
        response = await asyncio.to_thread(
            get_genai_client().models.generate_content,
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
        final_score = int(result.get("score", 5))
        # Hard-coded threshold — don't trust the model's approved field
        approved = final_score >= 8
        return {
            "score": final_score,
            "brand_alignment": result.get("brand_alignment", "moderate"),
            "strengths": result.get("strengths", []),
            "improvements": result.get("improvements", []),
            "approved": approved,
            "revision_notes": result.get("revision_notes"),
            "revised_hashtags": result.get("revised_hashtags"),
            "engagement_scores": {
                "hook_strength": int(raw_engagement.get("hook_strength", 5)),
                "relevance": int(raw_engagement.get("relevance", 5)),
                "cta_effectiveness": int(raw_engagement.get("cta_effectiveness", 5)),
                "platform_fit": int(raw_engagement.get("platform_fit", 5)),
                "teaching_depth": int(raw_engagement.get("teaching_depth", 0)),
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
            "revision_notes": None,
            "engagement_scores": {
                "hook_strength": 5,
                "relevance": 5,
                "cta_effectiveness": 5,
                "platform_fit": 5,
                "teaching_depth": 0,
            },
            "engagement_prediction": "medium",
        }
