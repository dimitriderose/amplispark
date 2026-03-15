"""Shared GCS URI parsing utility.

Centralises the gs://<bucket>/<path> → blob-path extraction that was
previously duplicated in server.py and storage_client.py.
"""

from backend.config import GCS_BUCKET_NAME


def parse_gcs_uri(gcs_uri: str) -> str:
    """Extract blob path from gs:// URI. Raises ValueError if invalid."""
    prefix = f"gs://{GCS_BUCKET_NAME}/"
    if not gcs_uri.startswith(prefix):
        raise ValueError(f"Invalid GCS URI (expected bucket {GCS_BUCKET_NAME}): {gcs_uri}")
    blob_path = gcs_uri[len(prefix):]
    if not blob_path:
        raise ValueError(f"GCS URI has no blob path: {gcs_uri}")
    return blob_path
