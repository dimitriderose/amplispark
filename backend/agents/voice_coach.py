import logging
from collections import defaultdict

from backend.constants import PILLAR_DESCRIPTIONS, PLATFORM_STRENGTHS, get_proof_tier

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
    pillar_lines = "\n".join(
        f"- {p.replace('_', ' ').title()}: {PILLAR_DESCRIPTIONS[p]}"
        for p in PILLAR_DESCRIPTIONS
    )
    header = f"CONTENT PILLARS (the 5 types used in the calendar):\n{pillar_lines}\n\n"
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


_DEFAULT_PLATFORMS = ["instagram", "linkedin", "x", "facebook"]


def _build_platform_block(connected_platforms: list) -> str:
    platforms = connected_platforms if connected_platforms else _DEFAULT_PLATFORMS
    lines = [
        PLATFORM_STRENGTHS[p]
        for p in platforms
        if p in PLATFORM_STRENGTHS
    ]
    if not lines:
        lines = [PLATFORM_STRENGTHS[p] for p in _DEFAULT_PLATFORMS]
    return "PLATFORM STRENGTHS (reference when explaining platform decisions):\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Calendar context builder
# ---------------------------------------------------------------------------

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _build_calendar_block(plan: dict | None, posts: list | None) -> str:
    """Summarise the current content plan + post statuses for the voice coach.

    Returns a compact text block (~30-60 lines) suitable for a Gemini Live
    system prompt.  Returns an empty string if no plan exists.
    """
    if not plan:
        return (
            "CONTENT CALENDAR:\n"
            "No content calendar has been generated yet. The owner can create "
            "one from the dashboard."
        )

    days = plan.get("days", [])
    if not days:
        return (
            "CONTENT CALENDAR:\n"
            "A content plan exists but has no scheduled days yet. "
            "The owner may still be configuring their week."
        )

    # Index posts by (day_index, platform) for fast lookup
    post_map: dict[tuple[int, str], dict] = {}
    for p in (posts or []):
        key = (p.get("day_index"), p.get("platform", ""))
        if key not in post_map or p.get("status") == "complete":
            post_map[key] = p

    # Group day briefs by day_index
    day_groups: dict[int, list[dict]] = defaultdict(list)
    for d in days:
        day_groups[(d.get("day_index") or 0)].append(d)

    # Detect repurposing groups (pillar_id shared across >1 entry)
    pillar_id_counts: dict[str, list[int]] = defaultdict(list)
    for d in days:
        pid = d.get("pillar_id")
        if pid:
            pillar_id_counts[pid].append((d.get("day_index") or 0))
    repurpose_ids = {pid for pid, idxs in pillar_id_counts.items() if len(set(idxs)) > 1 or len(idxs) > 1}

    lines = ["YOUR CONTENT CALENDAR THIS WEEK:"]
    total_entries = 0
    generated = 0
    approved = 0
    scores = []

    for di in sorted(day_groups.keys()):
        entries = day_groups[di]
        day_name = _DAY_NAMES[di % 7]
        lines.append(f"\nDay {di} ({day_name}):")

        # Track if this day has a repurposing group
        day_pids = {e.get("pillar_id") for e in entries if e.get("pillar_id")}
        is_repurpose = bool(day_pids & repurpose_ids)

        for entry in entries:
            total_entries += 1
            platform = entry.get("platform", "?")
            deriv = entry.get("derivative_type", "original")
            pillar = entry.get("pillar", "?")
            theme = entry.get("content_theme", "")
            hook = entry.get("caption_hook", "")
            cta = entry.get("cta_type", "?")
            event = entry.get("event_anchor")

            # Post status
            post = post_map.get((di, platform))
            if post and post.get("status") in ("complete", "approved"):
                generated += 1
                review = post.get("review", {})
                score = review.get("score")
                is_approved = review.get("approved", False)
                if is_approved:
                    approved += 1
                if isinstance(score, (int, float)):
                    scores.append(score)

                status_str = f"GENERATED (score: {score}"
                if is_approved:
                    status_str += ", approved"
                status_str += ")"

                # Top improvement for context
                improvements = review.get("improvements", [])
                review_note = f'\n    Review: "{improvements[0][:80]}"' if improvements else ""
            elif post and post.get("status") == "generating":
                status_str = "GENERATING..."
                review_note = ""
            else:
                status_str = "NOT YET GENERATED"
                review_note = ""

            lines.append(f"  {platform.title()} | {deriv.replace('_', ' ').title()} | {pillar.replace('_', ' ').title()} | \"{theme}\"")
            if hook:
                lines.append(f"    Hook: \"{hook}\"")
            event_note = f" | Event: {event}" if event else ""
            lines.append(f"    CTA: {cta}{event_note} | Status: {status_str}{review_note}")

        if is_repurpose and len(entries) > 1:
            lines.append("  ↳ Repurposing group: same theme adapted per platform")

    # Trend insights
    trend_summary = plan.get("trend_summary", {})
    platform_trends = trend_summary.get("platform_trends", {})
    if platform_trends:
        lines.append("\nTREND INSIGHTS (what informed this calendar):")
        for plat, trend_data in list(platform_trends.items())[:4]:
            if isinstance(trend_data, str):
                lines.append(f"- {plat.title()}: {trend_data[:120]}")
            elif isinstance(trend_data, dict):
                hooks = trend_data.get("trending_hooks", "")
                if hooks:
                    lines.append(f"- {plat.title()}: {str(hooks)[:120]}")

    visual_trends = trend_summary.get("visual_trends")
    if visual_trends:
        lines.append(f"- Visual trends: {str(visual_trends)[:120]}")
    video_trends = trend_summary.get("video_trends")
    if video_trends:
        lines.append(f"- Video trends: {str(video_trends)[:120]}")

    # Progress summary
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    lines.append(f"\nPROGRESS: {generated}/{total_entries} generated, {approved} approved"
                 + (f", avg score {avg_score}" if avg_score else ""))

    result = "\n".join(lines)
    # Cap calendar block to prevent prompt bloat (Gemini Live has limited context)
    if len(result) > 3000:
        result = result[:2900] + "\n... (calendar truncated for brevity)"
    return result


# ---------------------------------------------------------------------------
# Main prompt builder
# ---------------------------------------------------------------------------

def build_coaching_prompt(brand_profile: dict, plan: dict = None,
                          posts: list = None) -> str:
    """Build the Gemini Live API system prompt for voice brand coaching.

    The prompt injects the full brand profile and content calendar so the
    coach speaks with specific, brand-aware intelligence.
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

    # Social proof tier — shared logic from constants.py
    proof_tier = get_proof_tier(years_in_business, client_count)

    # Build brand context lines (only include populated fields)
    brand_lines = [
        f"- Industry: {industry}" if industry else "",
        f"- Target audience: {target_audience}" if target_audience else "",
        f"- Visual style: {visual_style}" if visual_style else "",
        f"- Writing style: {caption_style}" if caption_style else "",
        f"- Key content themes: {', '.join(content_themes)}" if content_themes else "",
        f"- Key competitors: {', '.join(competitors[:3])}" if competitors else "",
        f"- Business description: {description}" if description else "",
        f"- In business: {years_in_business} years" if years_in_business else "",
        f"- Clients served: {client_count}+" if client_count else "",
        f"- Location: {location}" if location else "",
        f"- Differentiators: {unique_selling_points}" if unique_selling_points else "",
        f"- Active platforms: {', '.join(connected_platforms)}" if connected_platforms else "",
    ]
    brand_context = "\n".join(line for line in brand_lines if line)

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

    # Calendar context (plan + post statuses)
    calendar_block = _build_calendar_block(plan, posts)

    return f"""You are Amplispark's AI brand strategist and creative director — a warm, expert advisor \
personally assigned to {business_name}.

BRAND PROFILE:
- Business: {business_name} ({business_type})
- Tone: {tone}
{brand_context}

{strategy_context}

{calendar_block}

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
7. Answer questions about the content calendar — from weekly strategy to specific days, themes, and format choices
9. Advise on not-yet-generated days — what to focus on, what photo or video to prepare
10. Explain repurposing groups — how one idea becomes multiple platform-adapted posts
11. Discuss review feedback on generated posts and how to improve scores

COMMUNICATION STYLE:
- Conversational and warm — like a trusted advisor, not a formal presentation
- For simple questions, keep to 20-40 seconds (50-100 words). For calendar walkthroughs or multi-day explanations, up to 60 seconds (150 words) is fine — pause naturally so the user can interject
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
