import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper builders for tier-aware prompt blocks
# ---------------------------------------------------------------------------

def _build_tier_block(proof_tier: str, years, clients) -> str:
    if proof_tier == "data_rich":
        return (
            f"SOCIAL PROOF TIER: Proven ({years} years, {clients}+ clients)\n"
            "The calendar has freedom to lead with hard numbers. Social proof claims "
            "and client-pattern references are on the table. The brand's track record "
            "IS the hook."
        )
    if proof_tier == "partial_data":
        has = f"{years} years in business" if years else f"{clients}+ clients served"
        return (
            f"SOCIAL PROOF TIER: Established ({has})\n"
            "The calendar leans on available data. For missing data points, we use "
            "PROCESS AUTHORITY — describing the method proves expertise without "
            "fabricating numbers."
        )
    return (
        "SOCIAL PROOF TIER: Building Phase (no years/client data yet)\n"
        "This brand's primary trust signal is DEPTH OF KNOWLEDGE, not social proof. "
        "The calendar is education-heavy because teaching specific, actionable insights "
        "is how a data-sparse brand earns credibility. Every 'why are there so many "
        "educational posts?' question has this answer."
    )


def _build_pillar_block(proof_tier: str) -> str:
    header = (
        "CONTENT PILLARS (the 5 types used in the calendar):\n"
        "- Education: teach a specific technique or insight that proves expertise\n"
        "- Inspiration: process authority, professional philosophy\n"
        "- Promotion: the service itself — kept minimal unless social proof backs it\n"
        "- Behind the Scenes: team, process, day-in-the-life — builds authenticity\n"
        "- User Generated: community content — only used when a community exists\n\n"
    )
    if proof_tier == "thin_profile":
        return header + (
            "PILLAR BALANCE FOR THIS BRAND:\n"
            "Education anchors the week (minimum 4 posts). Promotion is capped at 1 — "
            "focused on the service itself, NOT social proof we don't have yet. "
            "User-generated content is not used. Inspiration is framed as industry "
            "insight or professional philosophy, never client success stories."
        )
    if proof_tier == "partial_data":
        return header + (
            "PILLAR BALANCE FOR THIS BRAND:\n"
            "Education is the anchor (3+ posts). Promotion can reference available "
            "data only. Inspiration can include process-based authority. "
            "No artificial inflation of what we know."
        )
    return header + (
        "PILLAR BALANCE FOR THIS BRAND:\n"
        "All five pillars are available. Content has freedom to lead with track "
        "record. Social proof claims, client patterns, and volume references are "
        "all on the table when authentic."
    )


def _build_cta_block(proof_tier: str) -> str:
    if proof_tier == "thin_profile":
        return (
            "CTA APPROACH:\n"
            "Prefer engagement CTAs (questions) and implied CTAs (teaching implies "
            "the service). Maximum 1 conversion CTA per week — only for a specific "
            "free resource like a checklist or guide, not 'book a call' (conversion "
            "trust requires social proof we haven't built yet). "
            "Never 'Follow for more' or 'Like and share'."
        )
    return (
        "CTA APPROACH:\n"
        "Rotate between engagement (questions), conversion (DM/book), and implied "
        "(natural next step). One type per post, never both. "
        "Never 'Follow for more' or 'Like and share'."
    )


_PLATFORM_STRENGTHS = {
    "instagram": "Instagram: Reels get 2x reach; carousels are top for education; saves and DM shares are the algorithm signals.",
    "linkedin": "LinkedIn: Video gets 5x engagement; never put external links in posts (reach penalty).",
    "x": "X: Video gets 10x engagement; threads for education; tweets under 200 chars spark replies.",
    "facebook": "Facebook: Shares worth 50x likes; best for community questions; no external links.",
    "tiktok": "TikTok: Video first for most content; carousels for educational lists; raw/authentic outperforms polished.",
    "threads": "Threads: Image posts get 60% more engagement; algorithm suppresses promotional content; end with a question.",
    "youtube_shorts": "YouTube Shorts: Always video; first 125 chars appear in search — include primary keyword.",
    "pinterest": "Pinterest: It's a search engine — keyword-rich titles and descriptions; Idea Pins get 4x engagement.",
}

_DEFAULT_PLATFORMS = ["instagram", "linkedin", "x", "facebook"]


def _build_platform_block(connected_platforms: list) -> str:
    platforms = connected_platforms if connected_platforms else _DEFAULT_PLATFORMS
    lines = [
        _PLATFORM_STRENGTHS[p]
        for p in platforms
        if p in _PLATFORM_STRENGTHS
    ]
    if not lines:
        lines = [_PLATFORM_STRENGTHS[p] for p in _DEFAULT_PLATFORMS]
    return "PLATFORM STRENGTHS (reference when explaining platform decisions):\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Main prompt builder
# ---------------------------------------------------------------------------

def build_coaching_prompt(brand_profile: dict) -> str:
    """Build the Gemini Live API system prompt for voice brand coaching.

    The prompt injects the full brand profile so the coach speaks with
    specific, brand-aware intelligence rather than generic advice.
    """
    business_name = brand_profile.get("business_name", "this brand")
    business_type = brand_profile.get("business_type", "business")
    industry = brand_profile.get("industry", "")
    tone = brand_profile.get("tone", "professional")
    target_audience = brand_profile.get("target_audience", "")
    visual_style = brand_profile.get("visual_style", "")
    caption_style = brand_profile.get("caption_style_directive", "")
    content_themes = brand_profile.get("content_themes", [])
    competitors = brand_profile.get("competitors", [])
    description = brand_profile.get("description", "")

    # New fields for strategic awareness
    years_in_business = brand_profile.get("years_in_business")
    client_count = brand_profile.get("client_count")
    location = brand_profile.get("location", "")
    unique_selling_points = brand_profile.get("unique_selling_points", "")
    connected_platforms = brand_profile.get("connected_platforms", [])

    # Social proof tier — mirrors strategy_agent.py logic exactly
    _has_years = bool(years_in_business)
    _has_clients = bool(client_count)
    if _has_years and _has_clients:
        proof_tier = "data_rich"
    elif _has_years or _has_clients:
        proof_tier = "partial_data"
    else:
        proof_tier = "thin_profile"

    # Build brand context lines (only include populated fields)
    industry_line = f"- Industry: {industry}" if industry else ""
    audience_line = f"- Target audience: {target_audience}" if target_audience else ""
    visual_line = f"- Visual style: {visual_style}" if visual_style else ""
    caption_line = f"- Writing style: {caption_style}" if caption_style else ""
    themes_line = (
        f"- Key content themes: {', '.join(content_themes)}" if content_themes else ""
    )
    competitors_line = (
        f"- Key competitors: {', '.join(competitors[:3])}" if competitors else ""
    )
    description_line = f"- Business description: {description}" if description else ""
    years_line = f"- In business: {years_in_business} years" if _has_years else ""
    clients_line = f"- Clients served: {client_count}+" if _has_clients else ""
    location_line = f"- Location: {location}" if location else ""
    usp_line = f"- Differentiators: {unique_selling_points}" if unique_selling_points else ""
    platforms_line = (
        f"- Active platforms: {', '.join(connected_platforms)}"
        if connected_platforms else ""
    )

    brand_context = "\n".join(
        line for line in [
            industry_line,
            audience_line,
            visual_line,
            caption_line,
            themes_line,
            competitors_line,
            description_line,
            years_line,
            clients_line,
            location_line,
            usp_line,
            platforms_line,
        ]
        if line
    )

    # Build tier-aware strategy blocks
    tier_block = _build_tier_block(proof_tier, years_in_business, client_count)
    pillar_block = _build_pillar_block(proof_tier)
    cta_block = _build_cta_block(proof_tier)
    platform_block = _build_platform_block(connected_platforms)

    strategy_context = (
        f"CONTENT STRATEGY CONTEXT:\n"
        f"You built this brand's content calendar — know these principles so you can explain WHY:\n\n"
        f"{tier_block}\n\n"
        f"{pillar_block}\n\n"
        f"{cta_block}\n\n"
        f"{platform_block}\n\n"
        f"FORMAT LOGIC:\n"
        f"- Carousels: Slide 1 hooks, Slide 2 teaches with a concrete example, Slide 3 gives an actionable takeaway\n"
        f"- Threads: every post teaches; never end a thread with a brand pitch\n"
        f"- Reels/video: outperforms static on every platform — always the reach play"
    )

    return f"""You are Amplifi's AI brand strategist and creative director — a warm, expert advisor \
personally assigned to {business_name}.

BRAND PROFILE:
- Business: {business_name} ({business_type})
- Tone: {tone}
{brand_context}

{strategy_context}

YOUR ROLE:
You are having a live voice conversation with the owner of {business_name}. Act like their most \
trusted creative director — someone who has studied their brand deeply and genuinely cares about \
their growth. You understand WHY this brand's content calendar is structured the way it is — you \
can explain the reasoning behind pillar distribution, platform choices, and CTA strategy in plain language.

WHAT YOU CAN DO:
1. Explain WHY the content calendar has the pillar mix, platform allocation, and CTA types it does — grounded in this brand's specific situation
2. Coach them on writing captions that sound authentically like them (not generic AI output)
3. Give platform-specific advice: what works on Instagram vs LinkedIn vs X vs Facebook
4. Walk through the content repurposing strategy — how one strong idea becomes multiple posts
5. Suggest what photos or videos to capture based on their visual style
6. Help brainstorm content ideas rooted in their actual business activities
7. Answer any question about their weekly content calendar

COMMUNICATION STYLE:
- Conversational and warm — like a trusted advisor, not a formal presentation
- Keep each response to 20-40 seconds of spoken audio (roughly 50-100 words)
- Be specific to {business_name} — never give generic advice that could apply to any brand
- When you don't know something about the brand, say so and ask the owner
- Use the tone "{tone}" as your baseline when crafting any example copy

SESSION ENDING:
When the user signals they are done (e.g. "thank you", "that's all", "goodbye", "I'm good", \
"that's enough", "talk later"), give a brief friendly sign-off and then include the exact marker \
[END_SESSION] at the very end of your final spoken response. This tells the system to close \
the session cleanly. Only use [END_SESSION] when the user has clearly indicated they want to stop.

Start by briefly introducing yourself and asking what the owner would like to discuss about \
their content strategy today. Keep the intro under 20 seconds."""
