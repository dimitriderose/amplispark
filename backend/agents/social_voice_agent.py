import asyncio
import json
import logging

import httpx
from google.genai import types
from backend.clients import get_genai_client
from backend.config import GEMINI_MODEL

logger = logging.getLogger(__name__)


# ── Platform post fetchers ─────────────────────────────────────────────────────

async def _fetch_linkedin_posts(oauth_token: str, limit: int = 50) -> list[dict]:
    """Fetch recent posts from LinkedIn using a user OAuth 2.0 access token.

    Requires scopes: r_liteprofile, r_member_social (or w_member_social on newer apps).
    """
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        # Step 1: resolve the authenticated person's URN
        me = await client.get("https://api.linkedin.com/v2/me", headers=headers)
        me.raise_for_status()
        person_id = me.json().get("id", "")
        if not person_id:
            raise ValueError("Could not retrieve LinkedIn person ID from token")

        author_urn = f"urn:li:person:{person_id}"

        # Step 2: fetch UGC posts authored by this person
        posts_resp = await client.get(
            "https://api.linkedin.com/v2/ugcPosts",
            params={
                "q": "authors",
                "authors": f"List({author_urn})",
                "count": limit,
                "sortBy": "LAST_MODIFIED",
            },
            headers=headers,
        )
        posts_resp.raise_for_status()
        elements = posts_resp.json().get("elements", [])

    texts = []
    for el in elements:
        text = (
            el.get("specificContent", {})
            .get("com.linkedin.ugc.ShareContent", {})
            .get("shareCommentary", {})
            .get("text", "")
        )
        if text:
            texts.append({"text": text})
    return texts


async def _fetch_instagram_posts(oauth_token: str, limit: int = 50) -> list[dict]:
    """Fetch recent posts from Instagram using a user access token (Basic Display API
    or Meta Graph API with instagram_basic + pages_show_list scopes).
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # Step 1: get the authenticated user's ID
        me = await client.get(
            "https://graph.instagram.com/me",
            params={"fields": "id,username", "access_token": oauth_token},
        )
        me.raise_for_status()
        user_id = me.json().get("id", "")
        if not user_id:
            raise ValueError("Could not retrieve Instagram user ID from token")

        # Step 2: fetch recent media with captions
        media = await client.get(
            f"https://graph.instagram.com/{user_id}/media",
            params={
                "fields": "id,caption,media_type,timestamp",
                "limit": limit,
                "access_token": oauth_token,
            },
        )
        media.raise_for_status()
        items = media.json().get("data", [])

    return [{"text": item["caption"]} for item in items if item.get("caption")]


async def _fetch_x_posts(oauth_token: str, limit: int = 100) -> list[dict]:
    """Fetch recent tweets using an X (Twitter) OAuth 2.0 user access token.

    Requires scopes: tweet.read, users.read.
    The token must be a user-context OAuth 2.0 Bearer token (not app-only).
    """
    headers = {"Authorization": f"Bearer {oauth_token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        # Step 1: get the authenticated user's numeric ID
        me = await client.get(
            "https://api.twitter.com/2/users/me",
            params={"user.fields": "id"},
            headers=headers,
        )
        me.raise_for_status()
        user_id = me.json().get("data", {}).get("id", "")
        if not user_id:
            raise ValueError("Could not retrieve X user ID from token")

        # Step 2: fetch recent tweets, excluding retweets and replies
        tweets = await client.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            params={
                "max_results": min(limit, 100),
                "tweet.fields": "text,created_at",
                "exclude": "retweets,replies",
            },
            headers=headers,
        )
        tweets.raise_for_status()
        items = tweets.json().get("data", [])

    return [{"text": t["text"]} for t in items if t.get("text")]


# Single source of truth — validation and dispatch both use this dict
_FETCH_FNS: dict[str, object] = {
    "linkedin": _fetch_linkedin_posts,
    "instagram": _fetch_instagram_posts,
    "x": _fetch_x_posts,
}


# ── Gemini voice analysis ──────────────────────────────────────────────────────

async def _analyze_social_voice(posts: list[dict]) -> dict:
    """Use Gemini to extract writing voice patterns from a list of posts."""
    post_texts = "\n---\n".join(p["text"] for p in posts[:30])

    prompt = f"""Analyze these social media posts and extract the author's authentic writing voice.

POSTS:
{post_texts}

Return ONLY a valid JSON object with these exact keys:
{{
  "voice_characteristics": ["list of 3-6 specific traits about writing style and structure"],
  "common_phrases": ["list of 2-5 frequently used phrases or sentence starters"],
  "emoji_usage": "heavy|moderate|minimal|none",
  "average_post_length": "short|medium|long",
  "successful_patterns": ["list of 2-4 structural or stylistic patterns that likely drive engagement"],
  "tone_adjectives": ["list of 3-5 adjectives like warm, authoritative, playful, direct"]
}}"""

    client = get_genai_client()
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    try:
        raw = response.text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("Voice analysis JSON parse failed: %s | raw: %.200s", e, response.text)
        raise ValueError("Voice analysis returned an unexpected response. Please try again.") from e


# ── Public API ─────────────────────────────────────────────────────────────────

async def connect_platform(platform: str, oauth_token: str) -> dict:
    """Fetch posts from a social platform and return a Gemini-generated voice analysis.

    Args:
        platform: One of "linkedin", "instagram", "x".
        oauth_token: A valid OAuth 2.0 user access token for that platform.

    Returns:
        Voice analysis dict with keys: voice_characteristics, common_phrases,
        emoji_usage, average_post_length, successful_patterns, tone_adjectives.

    Raises:
        ValueError: Unsupported platform, bad/expired token, insufficient permissions,
                    rate-limited, timeout, no posts found, or unparseable AI response.
        httpx.HTTPStatusError: Unexpected upstream API error (status not handled above).
    """
    platform = platform.lower()
    if platform not in _FETCH_FNS:
        raise ValueError(
            f"Unsupported platform '{platform}'. Supported: {', '.join(sorted(_FETCH_FNS))}"
        )

    fetch_fn = _FETCH_FNS[platform]
    try:
        posts = await fetch_fn(oauth_token)  # type: ignore[operator]
    except httpx.TimeoutException:
        raise ValueError(
            f"Request to {platform} timed out. The platform API may be slow — please try again."
        )
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            raise ValueError(
                f"Invalid or expired {platform} access token. Please reconnect."
            ) from e
        if status == 403:
            raise ValueError(
                f"Insufficient permissions for {platform}. "
                "Make sure you granted read access to your posts."
            ) from e
        if status == 429:
            raise ValueError(
                f"{platform} rate limit reached. Please wait a few minutes and try again."
            ) from e
        raise

    if not posts:
        raise ValueError(
            f"No posts found on {platform}. Make sure your account has public posts."
        )

    logger.info("Analyzing voice from %d %s posts", len(posts), platform)
    return await _analyze_social_voice(posts)
