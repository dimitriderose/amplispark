"""Notion REST API wrapper for OAuth + content calendar export."""

import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def exchange_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange an OAuth authorization code for access + refresh tokens."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{NOTION_API}/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def search_databases(access_token: str) -> list[dict]:
    """List databases the integration can access."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{NOTION_API}/search",
            headers=_headers(access_token),
            json={"filter": {"value": "database", "property": "object"}},
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [
            {
                "id": db["id"],
                "title": _extract_title(db),
            }
            for db in results
        ]


def _extract_title(db: dict) -> str:
    """Extract plain-text title from a Notion database object."""
    title_parts = db.get("title", [])
    if isinstance(title_parts, list):
        return "".join(t.get("plain_text", "") for t in title_parts)
    return "Untitled"


def _build_post_properties(post: dict, day_index: int, platform: str) -> dict:
    """Build Notion database page properties from an Amplispark post."""
    theme = post.get("theme", "")
    caption = post.get("caption", "")
    hashtags = post.get("hashtags", [])
    posting_time = post.get("posting_time", "")
    status = post.get("status", "draft")
    content_type = post.get("content_type", "photo")

    # Title: "Day {n} - {Platform} - {Theme}"
    title_text = f"Day {day_index + 1} - {platform.capitalize()}"
    if theme:
        title_text += f" - {theme}"

    # Hashtags as string
    hashtag_str = " ".join(f"#{h.lstrip('#')}" for h in hashtags) if hashtags else ""

    # Image URL (first one)
    image_urls = post.get("image_urls", [])
    image_url = image_urls[0] if image_urls else ""

    properties: dict = {
        "Name": {"title": [{"text": {"content": title_text[:2000]}}]},
        "Platform": {"select": {"name": platform.capitalize()}},
        "Day": {"number": day_index + 1},
        "Status": {"select": {"name": status}},
        "Caption": {"rich_text": [{"text": {"content": caption[:2000]}}]},
        "Posting Time": {"rich_text": [{"text": {"content": posting_time}}]},
        "Content Type": {"select": {"name": content_type}},
    }

    if hashtag_str:
        properties["Hashtags"] = {"rich_text": [{"text": {"content": hashtag_str[:2000]}}]}

    if image_url:
        properties["Image URL"] = {"url": image_url}

    return properties


def _build_page_body(caption: str, hashtags: list[str]) -> list[dict]:
    """Build Notion page body blocks (full caption as paragraphs)."""
    blocks = []

    # Split caption into paragraphs
    paragraphs = caption.split("\n\n") if caption else []
    for para in paragraphs:
        if para.strip():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": para.strip()[:2000]}}],
                },
            })

    # Hashtags as a separate paragraph
    if hashtags:
        tag_str = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": tag_str[:2000]}}],
            },
        })

    return blocks


async def create_page(
    access_token: str,
    database_id: str,
    post: dict,
    day_index: int,
    platform: str,
) -> dict:
    """Create a single page (row) in a Notion database for a post."""
    properties = _build_post_properties(post, day_index, platform)
    body = _build_page_body(post.get("caption", ""), post.get("hashtags", []))

    payload: dict = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }
    if body:
        payload["children"] = body

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{NOTION_API}/pages",
            headers=_headers(access_token),
            json=payload,
        )
        if resp.status_code == 401:
            raise PermissionError("Notion token expired. Please reconnect.")
        resp.raise_for_status()
        return resp.json()


async def ensure_database_schema(access_token: str, database_id: str) -> None:
    """Add missing properties to the target database so exports don't fail.

    Notion ignores properties in create_page that don't exist in the schema,
    so we pre-create them. Existing properties are left untouched.
    """
    desired: dict = {
        "Platform": {"select": {"options": []}},
        "Day": {"number": {}},
        "Status": {"select": {"options": []}},
        "Caption": {"rich_text": {}},
        "Hashtags": {"rich_text": {}},
        "Image URL": {"url": {}},
        "Posting Time": {"rich_text": {}},
        "Content Type": {"select": {"options": []}},
    }

    # Fetch current schema
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{NOTION_API}/databases/{database_id}",
            headers=_headers(access_token),
        )
        resp.raise_for_status()
        existing_props = resp.json().get("properties", {})

    # Only add properties that are missing
    to_add = {k: v for k, v in desired.items() if k not in existing_props}
    if not to_add:
        return

    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{NOTION_API}/databases/{database_id}",
            headers=_headers(access_token),
            json={"properties": to_add},
        )
        resp.raise_for_status()
        logger.info("Added %d properties to Notion database %s", len(to_add), database_id)
