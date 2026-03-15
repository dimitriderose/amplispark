"""Firebase Auth + brand ownership verification for FastAPI routes.

Verifies the Firebase ID token from the Authorization header, extracts the
authenticated UID, and checks that the user owns the brand being accessed.

Usage::

    @router.get("/brands/{brand_id}/plans")
    async def list_plans(brand_id: str, _owner=Depends(verify_brand_owner)):
        ...
"""

import logging

import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import Depends, HTTPException, Request

from backend.services import firestore_client

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK (uses ADC or GOOGLE_APPLICATION_CREDENTIALS)
if not firebase_admin._apps:
    firebase_admin.initialize_app()


async def get_authenticated_uid(request: Request) -> str | None:
    """Extract and verify the Firebase ID token from the Authorization header.

    Returns the verified UID, or None if no token is provided.
    Raises 401 if the token is present but invalid/expired.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # Fallback: check X-User-UID for backward compat during migration
        return request.headers.get("X-User-UID") or None

    token = auth_header[len("Bearer "):]
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired — please sign in again")
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logger.warning("Firebase token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Authentication failed")


async def verify_brand_owner(
    request: Request,
    user_uid: str | None = Depends(get_authenticated_uid),
) -> str | None:
    """Verify that the requesting user owns the brand being accessed.

    Extracts ``brand_id`` from the path parameters. If the brand has an
    ``owner_uid`` set, it must match the authenticated user's UID.

    Returns the verified user UID (or None if the brand has no owner yet).
    Raises 403 if the UIDs don't match, 401 if not authenticated but
    the brand has an owner.
    """
    brand_id = request.path_params.get("brand_id")
    if not brand_id:
        # Route doesn't have a brand_id param — skip check
        return user_uid

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    owner = brand.get("owner_uid")
    if not owner:
        # Brand is unclaimed — allow access
        return user_uid

    if not user_uid:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    if user_uid != owner:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this brand",
        )

    return user_uid
