"""One-time migration: create users/{uid} docs for all existing brand owners.

Run from project root:
    python scripts/migrate_active_users.py [--dry-run]

Sets role='user' for all existing brand owners. Sets role='admin' for
dimitri.derose@gmail.com (look up UID manually from Firebase Auth console
and set ADMIN_EMAIL env var or hardcode before running).
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv("backend/.env")

ADMIN_EMAIL = "dimitri.derose@gmail.com"
_BATCH_SIZE = 499


async def run(dry_run: bool):
    from datetime import UTC, datetime
    from google.cloud.firestore_v1.base_query import FieldFilter
    from backend.services.firestore_client import get_client
    import firebase_admin
    from firebase_admin import auth as firebase_auth

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()

    db = get_client()

    docs = await db.collection("brands").where(
        filter=FieldFilter("owner_uid", "!=", None)
    ).get()

    uid_set: set[str] = set()
    for doc in docs:
        data = doc.to_dict() or {}
        uid = data.get("owner_uid")
        if uid and isinstance(uid, str) and uid not in ("", "null"):
            uid_set.add(uid)

    print(f"Found {len(uid_set)} distinct brand owner UIDs")

    admin_uid: str | None = None
    try:
        admin_user = firebase_auth.get_user_by_email(ADMIN_EMAIL)
        admin_uid = admin_user.uid
        print(f"Admin UID for {ADMIN_EMAIL}: {admin_uid}")
    except Exception as e:
        print(f"Warning: could not resolve admin UID for {ADMIN_EMAIL}: {e}")

    now = datetime.now(UTC)
    written = 0
    skipped = 0
    uids = list(uid_set)

    for i in range(0, len(uids), _BATCH_SIZE):
        batch = db.batch()
        chunk = uids[i:i + _BATCH_SIZE]
        for uid in chunk:
            ref = db.collection("users").document(uid)
            snap = await ref.get()
            if snap.exists:
                skipped += 1
                continue
            role = "admin" if uid == admin_uid else "user"
            data = {
                "role": role,
                "email": None,
                "created_at": now,
                "updated_at": now,
                "beta_expires_at": None,
                "quick_posts_this_month": 0,
                "calendars_this_month": 0,
                "counters_reset_at": now,
            }
            if dry_run:
                print(f"  [DRY RUN] Would write users/{uid} role={role}")
                written += 1
            else:
                batch.set(ref, data, merge=True)
                written += 1
        if not dry_run:
            await batch.commit()

    print(f"Done. Written={written} Skipped={skipped}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run(dry_run))
