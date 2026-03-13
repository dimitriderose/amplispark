"""Image editor agent — conversational image editing via Gemini Flash Image."""
import asyncio
import base64
import io
import logging
import uuid

from PIL import Image
from google.cloud import storage
from google.genai import types

logger = logging.getLogger(__name__)


async def edit_image(
    image_gcs_uri: str,
    edit_prompt: str,
    brand_profile: dict,
    edit_history: list[str],
    gcs_bucket: str,
    gemini_client,
    aspect_ratio: str = "1:1",
    platform: str = "instagram",
) -> str:
    """Edit an image using Gemini Flash Image generation.
    Returns new GCS URI of the edited image.
    """
    # Download current image from GCS
    storage_client = storage.Client()
    bucket_name = image_gcs_uri.replace("gs://", "").split("/")[0]
    blob_path = "/".join(image_gcs_uri.replace("gs://", "").split("/")[1:])
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    image_bytes = blob.download_as_bytes()

    # Open image with PIL (SDK accepts PIL.Image directly)
    pil_image = Image.open(io.BytesIO(image_bytes))

    # Build edit instruction from brand profile
    tone = brand_profile.get("tone", "professional")
    visual_style = brand_profile.get("visual_style", "")

    aspect_hint = f"Generate a {aspect_ratio} aspect ratio image.\n" if aspect_ratio != "1:1" else ""
    edit_instruction = (
        f"Edit this {platform}-optimized social media image.\n"
        f"{aspect_hint}"
        f"Edit instruction: {edit_prompt}.\n"
        f"Maintain brand tone ({tone}) and visual style ({visual_style}). "
        f"Keep brand identity consistent. Return only the edited image."
    )

    # Gemini Flash Image: contents is a list of [prompt_string, PIL.Image]
    response = await asyncio.to_thread(
        gemini_client.models.generate_content,
        model="gemini-3.1-flash-image-preview",
        contents=[edit_instruction, pil_image],
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    # Extract image from response.parts (not response.candidates[0].content.parts)
    edited_bytes = None
    edited_mime = "image/png"
    for part in response.parts:
        if part.inline_data is not None:
            edited_mime = part.inline_data.mime_type or "image/png"
            edited_bytes = part.inline_data.data
            break

    if not edited_bytes:
        text_parts = [p.text for p in response.parts if p.text]
        raise ValueError(
            f"Gemini returned no image data. "
            f"Response text: {' '.join(text_parts) or 'N/A'}"
        )

    # Decode base64 if returned as string
    if isinstance(edited_bytes, str):
        edited_bytes = base64.b64decode(edited_bytes)

    # Save to GCS and return URI
    ext = "jpg" if "jpeg" in edited_mime else "png"
    new_blob_name = f"posts/edited_{uuid.uuid4().hex[:12]}.{ext}"
    new_bucket = storage_client.bucket(gcs_bucket)
    new_blob = new_bucket.blob(new_blob_name)
    new_blob.upload_from_string(edited_bytes, content_type=edited_mime)
    new_uri = f"gs://{gcs_bucket}/{new_blob_name}"
    logger.info("image_editor: saved edited image to %s", new_uri)
    return new_uri
