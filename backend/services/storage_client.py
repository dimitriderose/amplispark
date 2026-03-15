import logging
import re
import uuid
import asyncio
from datetime import timedelta
from typing import Optional
from google.cloud import storage
from backend.config import GCS_BUCKET_NAME, GCP_PROJECT_ID
from backend.gcs_utils import parse_gcs_uri

logger = logging.getLogger(__name__)


def _safe_filename(filename: str, max_len: int = 80) -> str:
    """Strip path components and reduce to safe GCS-object-name characters."""
    import os
    base = os.path.basename(filename)
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', base)
    return safe[:max_len] or "video"

_storage_client: Optional[storage.Client] = None

def get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=GCP_PROJECT_ID)
    return _storage_client

def get_bucket() -> storage.Bucket:
    return get_storage_client().bucket(GCS_BUCKET_NAME)


async def _get_serving_url(blob: storage.Blob, blob_path: str,
                            expiration: timedelta = timedelta(days=7)) -> str:
    """Try to generate a signed URL; fall back to a backend proxy URL.

    ADC credentials from ``gcloud auth application-default login`` lack a
    private key, so ``generate_signed_url`` raises.  When that happens we
    return ``/api/storage/serve/<blob_path>`` so the frontend can fetch the
    object through a backend proxy endpoint instead.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: blob.generate_signed_url(expiration=expiration, method="GET"),
        )
    except Exception:
        logger.debug("Signed URL unavailable — using backend proxy for %s", blob_path)
        return f"/api/storage/serve/{blob_path}"


async def upload_image_to_gcs(image_bytes: bytes, mime_type: str,
                               post_id: Optional[str] = None) -> tuple[str, str]:
    """Upload generated image bytes to GCS.

    Returns:
        (url, gcs_uri) — A serving URL (signed or backend-proxy) and the gs:// URI.
    """
    if not post_id:
        post_id = str(uuid.uuid4())

    ext = "png" if "png" in mime_type else "jpg"
    blob_path = f"generated/{post_id}/image_{uuid.uuid4().hex[:8]}.{ext}"
    bucket = get_bucket()
    blob = bucket.blob(blob_path)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(image_bytes, content_type=mime_type)
    )

    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_path}"
    url = await _get_serving_url(blob, blob_path)
    return url, gcs_uri

async def upload_brand_asset(brand_id: str, file_bytes: bytes,
                              filename: str, mime_type: str) -> str:
    """Upload user brand asset (logo, product photo, PDF). Returns GCS URI."""
    blob_path = f"brands/{brand_id}/{_safe_filename(filename)}"
    bucket = get_bucket()
    blob = bucket.blob(blob_path)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(file_bytes, content_type=mime_type)
    )
    return f"gs://{GCS_BUCKET_NAME}/{blob_path}"

async def get_signed_url(gcs_uri: str) -> str:
    """Convert a gs:// URI to a serving URL (signed or backend-proxy)."""
    blob_path = parse_gcs_uri(gcs_uri)
    bucket = get_bucket()
    blob = bucket.blob(blob_path)
    return await _get_serving_url(blob, blob_path, expiration=timedelta(hours=1))

async def download_from_gcs(url: str) -> bytes:
    """Download bytes from a GCS signed URL or backend proxy URL.

    Accepts:
      - ``https://storage.googleapis.com/...`` (signed URLs)
      - ``/api/storage/serve/...`` (backend proxy URLs — resolved via GCS client directly)
    """
    _PROXY_PREFIX = "/api/storage/serve/"
    if url.startswith(_PROXY_PREFIX):
        blob_path = url[len(_PROXY_PREFIX):]
        if ".." in blob_path:
            raise ValueError(f"Invalid blob path (path traversal): {blob_path}")
        bucket = get_bucket()
        blob = bucket.blob(blob_path)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, blob.download_as_bytes)

    import httpx
    if not url.startswith("https://storage.googleapis.com/"):
        raise ValueError(f"Refusing to fetch non-GCS URL: {url!r}")
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=False)
        response.raise_for_status()
        return response.content

async def upload_byop_photo(
    brand_id: str,
    plan_id: str,
    day_index: int,
    file_bytes: bytes,
    mime_type: str,
) -> tuple[str, str]:
    """Upload a user-provided photo (BYOP) for a calendar day.

    Returns:
        (signed_url, gcs_uri) — 7-day signed URL and the gs:// URI.
    """
    ext = "png" if "png" in mime_type else ("webp" if "webp" in mime_type else "jpg")
    blob_path = f"byop/{brand_id}/{plan_id}/day_{day_index}_{uuid.uuid4().hex[:8]}.{ext}"
    bucket = get_bucket()
    blob = bucket.blob(blob_path)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(file_bytes, content_type=mime_type),
    )

    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_path}"
    url = await _get_serving_url(blob, blob_path)
    return url, gcs_uri


async def upload_video_to_gcs(video_bytes: bytes, post_id: str) -> tuple[str, str]:
    """Upload generated MP4 video bytes to GCS.

    Returns:
        (signed_url, gcs_uri) — 7-day signed URL and the gs:// URI.
    """
    blob_path = f"generated/{post_id}/video_{uuid.uuid4().hex[:8]}.mp4"
    bucket = get_bucket()
    blob = bucket.blob(blob_path)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(video_bytes, content_type="video/mp4"),
    )

    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_path}"
    url = await _get_serving_url(blob, blob_path)
    return url, gcs_uri


async def upload_raw_video_source(
    brand_id: str,
    job_id: str,
    video_bytes: bytes,
    filename: str,
) -> str:
    """Upload a user-supplied raw video to GCS for processing.

    Returns:
        gcs_uri — gs:// path for downstream processing.
    """
    safe_name = _safe_filename(filename)
    blob_path = f"repurpose/{brand_id}/{job_id}/source_{safe_name}"
    bucket = get_bucket()
    blob = bucket.blob(blob_path)

    # Preserve correct MIME type for MOV vs MP4
    mime = "video/quicktime" if filename.lower().endswith(".mov") else "video/mp4"

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(video_bytes, content_type=mime),
    )

    return f"gs://{GCS_BUCKET_NAME}/{blob_path}"


async def upload_repurposed_clip(
    brand_id: str,
    job_id: str,
    clip_bytes: bytes,
    clip_filename: str,
) -> str:
    """Upload a processed short-form clip to GCS.

    Returns:
        gcs_uri — gs:// path. Generate signed URLs at query time via get_signed_url()
        to avoid embedding expiring URLs in durable Firestore documents.
    """
    blob_path = f"repurpose/{brand_id}/{job_id}/clips/{clip_filename}"
    bucket = get_bucket()
    blob = bucket.blob(blob_path)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(clip_bytes, content_type="video/mp4"),
    )

    return f"gs://{GCS_BUCKET_NAME}/{blob_path}"


async def download_gcs_uri(gcs_uri: str) -> bytes:
    """Download bytes from a gs:// URI directly via the GCS client."""
    blob_path = parse_gcs_uri(gcs_uri)
    bucket = get_bucket()
    blob = bucket.blob(blob_path)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, blob.download_as_bytes)
