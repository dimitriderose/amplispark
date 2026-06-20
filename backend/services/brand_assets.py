"""Shared helper to fetch brand reference images (logo, product photos, style ref).

Used by both content_creator and video_creator to pass visual references
to Gemini and Veo for brand-consistent generation.
"""

import logging

from backend.services.storage_client import download_gcs_uri

logger = logging.getLogger(__name__)

# Simple in-memory cache: brand_id -> list of (bytes, mime_type)
_cache: dict[str, list[tuple[bytes, str]]] = {}


def _guess_mime(uri: str) -> str:
    lower = uri.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


async def _download_safe(uri: str) -> tuple[bytes, str] | None:
    """Download a GCS URI, returning (bytes, mime) or None on failure."""
    try:
        data = await download_gcs_uri(uri)
        if data and len(data) > 100:  # sanity check — skip empty/tiny files
            return (data, _guess_mime(uri))
    except Exception as e:
        logger.warning("Failed to download brand asset %s: %s", uri, e)
    return None


async def get_brand_reference_images(
    brand_profile: dict,
    max_images: int = 3,
) -> list[tuple[bytes, str]]:
    """Collect available brand reference images for generation.

    Priority order:
    1. Logo (logo_url or first image in uploaded_assets)
    2. Product photos (product_photos list)
    3. Style reference (style_reference_gcs_uri from brand analyst)

    Returns list of (image_bytes, mime_type) tuples, up to max_images.
    Results are cached per brand_id for the process lifetime.
    """
    brand_id = brand_profile.get("brand_id", "")
    if brand_id in _cache:
        return _cache[brand_id][:max_images]

    results: list[tuple[bytes, str]] = []
    seen_uris: set[str] = set()

    # 1. Logo
    logo_uri = brand_profile.get("logo_url")
    if not logo_uri:
        # Fallback: first image-type entry in uploaded_assets
        for asset in brand_profile.get("uploaded_assets", []):
            if isinstance(asset, dict) and asset.get("type") == "image":
                logo_uri = asset.get("url")
                break
    if logo_uri and logo_uri not in seen_uris:
        seen_uris.add(logo_uri)
        result = await _download_safe(logo_uri)
        if result:
            results.append(result)

    # 2. Product photos
    for photo_uri in brand_profile.get("product_photos", []):
        if len(results) >= max_images:
            break
        if photo_uri and photo_uri not in seen_uris:
            seen_uris.add(photo_uri)
            result = await _download_safe(photo_uri)
            if result:
                results.append(result)

    # 3. Style reference from brand analyst
    style_uri = brand_profile.get("style_reference_gcs_uri")
    if style_uri and style_uri not in seen_uris and len(results) < max_images:
        seen_uris.add(style_uri)
        result = await _download_safe(style_uri)
        if result:
            results.append(result)

    # 4. Remaining uploaded image assets
    for asset in brand_profile.get("uploaded_assets", []):
        if len(results) >= max_images:
            break
        if isinstance(asset, dict) and asset.get("type") == "image":
            uri = asset.get("url")
            if uri and uri not in seen_uris:
                seen_uris.add(uri)
                result = await _download_safe(uri)
                if result:
                    results.append(result)

    _cache[brand_id] = results
    logger.info("Loaded %d brand reference images for %s", len(results), brand_id)
    return results[:max_images]
