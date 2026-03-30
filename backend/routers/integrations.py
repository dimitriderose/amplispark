import hmac
import logging
import base64
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import Response

from backend.services import firestore_client

logger = logging.getLogger(__name__)

# ── Token obfuscation helpers ────────────────────────────────
# Fernet symmetric encryption for Notion OAuth tokens
_TOKEN_KEY = os.environ.get("TOKEN_ENCRYPT_KEY", "")
_fernet = None
if _TOKEN_KEY:
    from cryptography.fernet import Fernet
    # Fernet requires a 32-byte URL-safe base64-encoded key
    # Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    try:
        _fernet = Fernet(_TOKEN_KEY.encode() if isinstance(_TOKEN_KEY, str) else _TOKEN_KEY)
    except Exception as e:
        logger.warning("Invalid TOKEN_ENCRYPT_KEY — tokens will be stored as plaintext: %s", e)


def _encrypt_token(token: str) -> str:
    """Encrypt a token using Fernet. Raises if no key configured."""
    if not _fernet:
        raise RuntimeError("TOKEN_ENCRYPT_KEY is required for storing OAuth tokens")
    return "enc:" + _fernet.encrypt(token.encode("utf-8")).decode("ascii")


def _decrypt_token(stored: str) -> str:
    """Decrypt a Fernet-encrypted token. Handles legacy plaintext and XOR-obfuscated tokens."""
    if stored.startswith("enc:") and _fernet:
        from cryptography.fernet import InvalidToken
        try:
            return _fernet.decrypt(stored[4:].encode("ascii")).decode("utf-8")
        except InvalidToken:
            logger.error("Failed to decrypt token — key may have changed")
            return ""
    if stored.startswith("obf:"):
        # Legacy XOR obfuscation — decode and re-encrypt on next write
        return stored  # return as-is; caller should re-encrypt
    logger.warning("Legacy plaintext token found — should be re-encrypted")
    return stored  # legacy plaintext

router = APIRouter()


# ── Social Voice Analysis ────────────────────────────────────

@router.post("/brands/{brand_id}/connect-social")
async def connect_social_account(
    brand_id: str,
    platform: str = Body(...),
    oauth_token: str = Body(...),
):
    """Connect a social account, analyze the user's writing voice, and persist it."""
    from backend.agents.social_voice_agent import connect_platform

    if not oauth_token or not oauth_token.strip():
        raise HTTPException(status_code=400, detail="oauth_token must not be empty")

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    try:
        voice_analysis = await connect_platform(platform, oauth_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Social voice analysis failed for brand %s platform %s: %s",
            brand_id, platform, e,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch posts from {platform}. Check your token and try again.",
        )

    # Merge into brand profile -- store per-platform dict + latest shortcut
    connected = list(brand.get("connected_platforms", []))
    if platform not in connected:
        connected.append(platform)

    existing_analyses = dict(brand.get("social_voice_analyses", {}))
    existing_analyses[platform] = voice_analysis

    await firestore_client.update_brand(brand_id, {
        "social_voice_analyses": existing_analyses,   # all platforms
        "social_voice_analysis": voice_analysis,       # latest (used by content creator)
        "social_voice_platform": platform,
        "connected_platforms": connected,
    })

    return {"platform": platform, "voice_analysis": voice_analysis}


# ── Notion Integration ───────────────────────────────────────

@router.get("/brands/{brand_id}/integrations/notion/auth-url")
async def notion_auth_url(brand_id: str):
    """Return the Notion OAuth authorize URL for the user to visit."""
    from backend.config import NOTION_CLIENT_ID, NOTION_REDIRECT_URI

    if not NOTION_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Notion integration not configured")

    hmac_sig = hmac.new(
        _TOKEN_KEY.encode() if _TOKEN_KEY else b"fallback",
        brand_id.encode(),
        "sha256",
    ).hexdigest()[:16]
    state = f"{brand_id}:{hmac_sig}"

    url = (
        f"https://api.notion.com/v1/oauth/authorize"
        f"?client_id={NOTION_CLIENT_ID}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={NOTION_REDIRECT_URI}"
        f"&state={state}"
    )
    return {"auth_url": url}


@router.post("/brands/{brand_id}/integrations/notion/disconnect")
async def notion_disconnect(brand_id: str):
    """Remove Notion integration from brand."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    integrations = brand.get("integrations", {})
    integrations.pop("notion", None)
    await firestore_client.update_brand(brand_id, {"integrations": integrations})
    return {"status": "disconnected"}


@router.get("/brands/{brand_id}/integrations/notion/databases")
async def notion_databases(brand_id: str):
    """List databases the Notion integration can access."""
    from backend.services.notion_client import search_databases

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    notion = brand.get("integrations", {}).get("notion")
    if not notion or not notion.get("access_token"):
        raise HTTPException(status_code=400, detail="Notion not connected")

    try:
        databases = await search_databases(_decrypt_token(notion["access_token"]))
    except Exception as e:
        logger.error("Failed to list Notion databases: %s", e)
        raise HTTPException(status_code=502, detail=f"Could not fetch databases: {e}")

    return {"databases": databases}


@router.post("/brands/{brand_id}/integrations/notion/select-database")
async def notion_select_database(
    brand_id: str,
    database_id: str = Body(..., embed=True),
    database_name: str = Body("", embed=True),
):
    """Set the target Notion database for exports."""
    from backend.services.notion_client import ensure_database_schema

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    notion = brand.get("integrations", {}).get("notion")
    if not notion or not notion.get("access_token"):
        raise HTTPException(status_code=400, detail="Notion not connected")

    # Ensure database has the right columns
    try:
        await ensure_database_schema(_decrypt_token(notion["access_token"]), database_id)
    except Exception as e:
        logger.warning("Could not update Notion database schema: %s", e)

    integrations = brand.get("integrations", {})
    integrations["notion"]["database_id"] = database_id
    integrations["notion"]["database_name"] = database_name
    await firestore_client.update_brand(brand_id, {"integrations": integrations})

    return {"status": "selected", "database_id": database_id}


@router.post("/brands/{brand_id}/plans/{plan_id}/export/notion")
async def export_plan_to_notion(brand_id: str, plan_id: str):
    """Export all posts from a plan to the connected Notion database."""
    from backend.services.notion_client import create_page

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    notion = brand.get("integrations", {}).get("notion")
    if not notion or not notion.get("access_token"):
        raise HTTPException(status_code=400, detail="Notion not connected")
    if not notion.get("database_id"):
        raise HTTPException(status_code=400, detail="No Notion database selected")

    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    posts = await firestore_client.list_posts(brand_id, plan_id)
    if not posts:
        raise HTTPException(status_code=404, detail="No posts found for this plan")

    # Get day briefs for theme info
    days = plan.get("days", [])
    day_lookup = {d.get("day_index", i): d for i, d in enumerate(days)}

    results = []
    access_token = _decrypt_token(notion["access_token"])
    database_id = notion["database_id"]

    for post in posts:
        post_id = post.get("post_id", "")
        day_index = post.get("day_index", 0)
        platform = post.get("platform", "instagram")

        # Merge theme from day brief into post for property building
        day_brief = day_lookup.get(day_index, {})
        post_with_theme = {**post, "theme": day_brief.get("theme", "")}
        if not post.get("content_type"):
            post_with_theme["content_type"] = day_brief.get("content_type", "photo")

        try:
            page = await create_page(access_token, database_id, post_with_theme, day_index, platform)
            notion_page_id = page.get("id", "")
            results.append({"post_id": post_id, "status": "exported", "notion_page_id": notion_page_id})

            # Update post's publish_status
            publish_status = post.get("publish_status", {}) or {}
            publish_status["notion"] = {
                "status": "exported",
                "notion_page_id": notion_page_id,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
            await firestore_client.update_post(brand_id, post_id, {"publish_status": publish_status})

        except Exception as e:
            logger.error("Failed to export post %s to Notion: %s", post_id, e)
            results.append({"post_id": post_id, "status": "failed", "error": str(e)})

    exported = sum(1 for r in results if r["status"] == "exported")
    return {
        "exported": exported,
        "total": len(posts),
        "results": results,
    }


# ── Notion OAuth callback (non-prefixed, under /api/integrations/) ───

@router.get("/integrations/notion/callback")
async def notion_callback(code: str = Query(...), state: str = Query(...)):
    """OAuth callback -- exchange code for tokens, store on brand profile."""
    from backend.config import NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI
    from backend.services.notion_client import exchange_code

    # Validate CSRF state parameter
    if ":" not in state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    brand_id, sig = state.split(":", 1)
    expected_sig = hmac.new(
        _TOKEN_KEY.encode() if _TOKEN_KEY else b"fallback",
        brand_id.encode(),
        "sha256",
    ).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    try:
        token_data = await exchange_code(code, NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI)
    except Exception as e:
        logger.error("Notion OAuth token exchange failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Notion authorization failed: {e}")

    # Store integration data on brand (token is obfuscated before persistence)
    raw_token = token_data.get("access_token", "")
    integrations = brand.get("integrations", {})
    integrations["notion"] = {
        "access_token": _encrypt_token(raw_token) if raw_token else "",
        "bot_id": token_data.get("bot_id"),
        "workspace_id": token_data.get("workspace_id"),
        "workspace_name": token_data.get("workspace_name", ""),
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    await firestore_client.update_brand(brand_id, {"integrations": integrations})

    # Redirect to dashboard with success param
    return Response(
        status_code=302,
        headers={
            "Location": f"/dashboard/{brand_id}?notion=connected",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
