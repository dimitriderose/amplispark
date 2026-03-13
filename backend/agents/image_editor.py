"""Image editor agent — conversational image editing via Gemini + Imagen 3 fallback."""
import asyncio
import logging
import uuid

from google.cloud import storage
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


async def edit_image(
    image_gcs_uri: str,
    edit_prompt: str,
    brand_profile: dict,
    edit_history: list[str],
    gcs_bucket: str,
    gemini_client,
) -> str:
    """Edit an image using Gemini 2.0 Flash image generation.
    Returns new GCS URI of the edited image.
    Falls back to Imagen 3 if primary fails.
    """
    # Download current image from GCS
    storage_client = storage.Client()
    bucket_name = image_gcs_uri.replace("gs://", "").split("/")[0]
    blob_path = "/".join(image_gcs_uri.replace("gs://", "").split("/")[1:])
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    image_bytes = blob.download_as_bytes()
    mime_type = blob.content_type or "image/png"

    # Build edit context from brand profile
    brand_name = brand_profile.get("business_name") or brand_profile.get("name") or "the brand"
    tone = brand_profile.get("tone", "professional")
    visual_style = brand_profile.get("visual_style", "")

    edited_bytes = None
    edited_mime = "image/png"

    try:
        # Primary path — Gemini 2.0 Flash image generation
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.0-flash-preview-image-generation",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                f"Edit this image: {edit_prompt}. Maintain brand tone ({tone}) and visual style ({visual_style}). Keep brand identity consistent. Return only the edited image."
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=0.4,
            ),
        )

        # Extract image from response
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                edited_bytes = part.inline_data.data
                edited_mime = part.inline_data.mime_type or "image/png"
                break

        if not edited_bytes:
            raise ValueError("Gemini returned no image data")

    except Exception as e:
        logger.warning("image_editor: primary edit failed, trying fallback: %s", e)

        # Fallback: Imagen 3 regeneration with edit hint
        style_hint = f"{brand_profile.get('image_style_directive', visual_style)} Edit applied: {edit_prompt}"
        if edit_history:
            style_hint = (
                f"Previous edits: {'; '.join(edit_history[-3:])}. "
                f"New edit: {edit_prompt}. "
                f"{brand_profile.get('image_style_directive', '')}"
            )

        img_response = await asyncio.to_thread(
            gemini_client.models.generate_images,
            model="imagen-3.0-generate-002",
            prompt=style_hint[:1000],
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter_level="block_only_high",
            ),
        )
        if not img_response.generated_images:
            raise ValueError("Imagen 3 fallback also failed to generate an image")
        edited_bytes = img_response.generated_images[0].image.image_bytes
        edited_mime = "image/png"
        logger.info("image_editor: used Imagen 3 fallback for edit: %s", edit_prompt)

    # Save to GCS and return URI
    ext = "jpg" if "jpeg" in edited_mime else "png"
    new_blob_name = f"posts/edited_{uuid.uuid4().hex[:12]}.{ext}"
    new_bucket = storage_client.bucket(gcs_bucket)
    new_blob = new_bucket.blob(new_blob_name)
    new_blob.upload_from_string(edited_bytes, content_type=edited_mime)
    new_uri = f"gs://{gcs_bucket}/{new_blob_name}"
    logger.info("image_editor: saved edited image to %s", new_uri)
    return new_uri
