"""Shared constants used across multiple agents.

Single source of truth for pillars, derivative types, platform strengths,
and proof-tier classification.  Import from here instead of duplicating.
"""

PILLARS = [
    "education",
    "inspiration",
    "promotion",
    "behind_the_scenes",
    "user_generated",
]

DERIVATIVE_TYPES = [
    "original",
    "carousel",
    "thread_hook",
    "blog_snippet",
    "story",
    "pin",
    "video_first",
]

# Canonical pillar descriptions — shared across voice coach, video creator,
# and video repurpose agent.  Each agent may extend with format-specific
# guidance (camera direction, clip selection criteria) but the core
# definition should stay consistent.
PILLAR_DESCRIPTIONS = {
    "education": (
        "Teach a specific technique, framework, or actionable insight. "
        "Show the process in action — the viewer should learn something."
    ),
    "inspiration": (
        "Transformation stories and emotional arcs. Open with struggle "
        "or challenge, close with breakthrough or insight. Process "
        "authority and professional philosophy also fit here."
    ),
    "promotion": (
        "The product or service in a real scenario. Open with the "
        "problem, end with the solution. Focus on benefit, not features."
    ),
    "behind_the_scenes": (
        "Real process — tools, workspace, decision moments, team "
        "dynamics. Authenticity over polish. Show what's normally hidden."
    ),
    "user_generated": (
        "Real people interacting with the product/service, authentic "
        "reactions, or community highlights. UGC-style authenticity "
        "over produced content."
    ),
}

# Pillar-aware video narrative arcs — used by video_creator for Veo prompts.
PILLAR_NARRATIVES = {
    "education": (
        "NARRATIVE: Show a technique or process IN ACTION. The viewer should learn "
        "something by watching — hands working through steps, a before/after transformation, "
        "or a tool being used with visible results."
    ),
    "promotion": (
        "NARRATIVE: Show the product/service in a real customer scenario. Not a glamour shot — "
        "a real person benefiting in a real context. Open with the problem, end with the solution."
    ),
    "inspiration": (
        "NARRATIVE: Show a transformation journey. Open with struggle or challenge, "
        "close with breakthrough or insight. Emotional arc matters more than technical detail."
    ),
    "behind_the_scenes": (
        "NARRATIVE: Show the real process — tools, workspace, decision moments. "
        "Authenticity over polish. The viewer should feel they're seeing something normally hidden."
    ),
    "user_generated": (
        "NARRATIVE: Tell a customer's story concisely. Open with them in their context, "
        "show their challenge, close with their outcome or satisfaction."
    ),
}

# Pillar-aware clip selection criteria — used by video_repurpose_agent.
PILLAR_CLIP_CRITERIA = {
    "education": (
        "Prioritize moments where a technique, process, or framework is being "
        "explained or demonstrated. The viewer should learn something by watching."
    ),
    "promotion": (
        "Prioritize moments showing the product/service in action, results, "
        "or customer benefit. Open with the problem, end with the solution."
    ),
    "inspiration": (
        "Prioritize transformation moments, emotional peaks, or breakthrough "
        "insights. Emotional arc matters more than technical detail."
    ),
    "behind_the_scenes": (
        "Prioritize candid process reveals, workspace moments, or unpolished "
        "authenticity. The viewer should feel they're seeing something normally hidden."
    ),
    "user_generated": (
        "Prioritize customer reactions, real-world usage, or community highlights. "
        "Authentic moments over produced content."
    ),
}

PLATFORM_STRENGTHS = {
    "instagram": (
        "Instagram: Reels get 2x reach; carousels are top for education; "
        "saves and DM shares are the algorithm signals."
    ),
    "linkedin": (
        "LinkedIn: Video gets 5x engagement; never put external links "
        "in posts (reach penalty)."
    ),
    "x": (
        "X: Video gets 10x engagement; threads for education; "
        "tweets under 200 chars spark replies."
    ),
    "facebook": (
        "Facebook: Shares worth 50x likes; best for community questions; "
        "no external links."
    ),
    "tiktok": (
        "TikTok: Video first for most content; carousels for educational "
        "lists; raw/authentic outperforms polished."
    ),
    "threads": (
        "Threads: Image posts get 60% more engagement; algorithm suppresses "
        "promotional content; end with a question."
    ),
    "youtube_shorts": (
        "YouTube Shorts: Always video; first 125 chars appear in search — "
        "include primary keyword."
    ),
    "pinterest": (
        "Pinterest: It's a search engine — keyword-rich titles and "
        "descriptions; Idea Pins get 4x engagement."
    ),
}


def get_proof_tier(years_in_business, client_count) -> str:
    """Classify a brand's social-proof tier.

    Returns one of: "data_rich", "partial_data", "thin_profile".
    Uses ``is not None`` so that explicit 0 values count as "data provided".
    """
    _has_years = years_in_business is not None
    _has_clients = client_count is not None
    if _has_years and _has_clients:
        return "data_rich"
    if _has_years or _has_clients:
        return "partial_data"
    return "thin_profile"
