"""Firebase Auth + brand ownership verification for FastAPI routes.

Verifies the Firebase ID token from the Authorization header, extracts the
authenticated UID, and checks that the user owns the brand being accessed.

Usage::

    @router.get("/brands/{brand_id}/plans")
    async def list_plans(brand_id: str, _owner=Depends(verify_brand_owner)):
        ...
"""

import asyncio
import logging

import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import Depends, HTTPException, Request, WebSocket, WebSocketException, status

from backend.middleware_logging import user_uid_var
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
        uid = request.headers.get("X-User-UID") or None
        if uid:
            user_uid_var.set(uid)
        return uid

    token = auth_header[len("Bearer "):]
    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]
        user_uid_var.set(uid)
        return uid
    except firebase_auth.ExpiredIdTokenError:
        logger.info("metric", extra={
            "metric_name": "auth_failure",
            "reason": "expired_token",
            "path": str(request.url.path),
        })
        raise HTTPException(status_code=401, detail="Token expired — please sign in again")
    except firebase_auth.InvalidIdTokenError:
        logger.info("metric", extra={
            "metric_name": "auth_failure",
            "reason": "invalid_token",
            "path": str(request.url.path),
        })
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logger.warning("Firebase token verification failed: %s", e)
        logger.info("metric", extra={
            "metric_name": "auth_failure",
            "reason": "unknown",
            "path": str(request.url.path),
        })
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


# ── WebSocket authentication via Sec-WebSocket-Protocol header ──────────


async def get_ws_authenticated_uid(websocket: WebSocket) -> str:
    """Extract and verify a Firebase ID token from the Sec-WebSocket-Protocol header.

    The browser WebSocket API cannot set custom headers, so the token is sent
    as a subprotocol in the format ``auth.<firebase_id_token>``.  Validation
    runs *before* ``websocket.accept()`` so unauthenticated connections never
    consume server resources.

    Raises WebSocketException (1008 Policy Violation) on failure.
    """
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    token: str | None = None
    for proto in protocols.split(","):
        proto = proto.strip()
        if proto.startswith("auth."):
            token = proto[5:]  # strip "auth." prefix
            break

    if not token:
        logger.debug("WS auth: no auth token in Sec-WebSocket-Protocol")
        logger.info("metric", extra={
            "metric_name": "auth_failure",
            "reason": "missing_token",
            "path": str(websocket.url.path),
        })
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing auth token")

    try:
        loop = asyncio.get_running_loop()
        decoded = await loop.run_in_executor(None, firebase_auth.verify_id_token, token)
        return decoded["uid"]
    except firebase_auth.ExpiredIdTokenError:
        logger.debug("WS auth: token expired")
        logger.info("metric", extra={
            "metric_name": "auth_failure",
            "reason": "expired_token",
            "path": str(websocket.url.path),
        })
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token expired")
    except firebase_auth.InvalidIdTokenError:
        logger.debug("WS auth: invalid token")
        logger.info("metric", extra={
            "metric_name": "auth_failure",
            "reason": "invalid_token",
            "path": str(websocket.url.path),
        })
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
    except Exception as e:
        logger.warning("WebSocket Firebase token verification failed: %s", e)
        logger.info("metric", extra={
            "metric_name": "auth_failure",
            "reason": "unknown",
            "path": str(websocket.url.path),
        })
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Auth failed")


async def verify_ws_brand_owner(
    websocket: WebSocket,
    user_uid: str = Depends(get_ws_authenticated_uid),
) -> dict:
    """Verify authenticated user owns the brand in the WebSocket path.

    Returns the brand document (avoids a second Firestore read in the handler).
    Raises WebSocketException (1008) on failure.
    """
    brand_id = websocket.path_params.get("brand_id")
    if not brand_id:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing brand_id")

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Brand not found")

    owner = brand.get("owner_uid")
    if owner and user_uid != owner:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied")

    # Attach UID to brand dict so handler has both
    brand["_authenticated_uid"] = user_uid
    return brand
