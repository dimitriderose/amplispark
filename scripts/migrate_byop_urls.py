"""One-time migration: remove stale custom_photo_url fields from Firestore plan days.

custom_photo_url (a 7-day signed URL) was previously persisted to Firestore alongside
custom_photo_gcs_uri. It is now generated fresh on every read, so the stored value is
obsolete and misleading. This script drops it from all existing documents.

Run from project root:
    python scripts/migrate_byop_urls.py

Safe to re-run; the DELETE_FIELD sentinel is a no-op if the field is already absent.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from google.cloud import firestore
from google.cloud.firestore_v1 import DELETE_FIELD


async def migrate() -> None:
    db = firestore.AsyncClient(project=os.environ.get("GCP_PROJECT_ID"))
    brands_ref = db.collection("brands")
    brands = [doc async for doc in brands_ref.stream()]
    print(f"Found {len(brands)} brands")

    total_days_updated = 0
    for brand_doc in brands:
        brand_id = brand_doc.id
        plans_ref = brands_ref.document(brand_id).collection("content_plans")
        plans = [doc async for doc in plans_ref.stream()]
        for plan_doc in plans:
            plan_data = plan_doc.to_dict() or {}
            days = plan_data.get("days", [])
            days_with_stale_url = sum(1 for day in days if day.get("custom_photo_url"))
            if not days_with_stale_url:
                continue
            for day in days:
                day.pop("custom_photo_url", None)
            await plan_doc.reference.update({"days": days})
            total_days_updated += days_with_stale_url
            print(f"  Cleaned plan {plan_doc.id} (brand {brand_id})")

    print(f"Done. {total_days_updated} BYOP day(s) now use refresh-on-read.")


if __name__ == "__main__":
    asyncio.run(migrate())
