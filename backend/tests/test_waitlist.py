"""Tests for waitlist endpoints and beta-limit middleware dependencies."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.tests.conftest import TEST_BRAND_ID, TEST_UID

FUTURE = datetime.now(UTC) + timedelta(days=30)
PAST = datetime.now(UTC) - timedelta(days=1)


@pytest.fixture
def beta_user_doc():
    return {
        "role": "beta",
        "beta_expires_at": FUTURE,
        "quick_posts_this_month": 0,
        "calendars_this_month": 0,
        "counters_reset_at": datetime.now(UTC),
    }


@pytest.fixture
def expired_beta_user_doc():
    return {
        "role": "beta",
        "beta_expires_at": PAST,
        "quick_posts_this_month": 0,
        "calendars_this_month": 0,
        "counters_reset_at": datetime.now(UTC),
    }


@pytest.fixture
def paid_user_doc():
    return {"role": "user"}


@pytest.fixture
def admin_user_doc():
    return {"role": "admin"}


@pytest.fixture(autouse=True)
def patch_all_router_firestore(mock_firestore):
    from backend.routers.waitlist import limiter

    limiter._storage.reset()
    with (
        patch("backend.routers.waitlist.firestore_client", mock_firestore),
        patch("backend.routers.brands.firestore_client", mock_firestore),
        patch("backend.routers.plans.firestore_client", mock_firestore),
        patch("backend.routers.generation.firestore_client", mock_firestore),
    ):
        yield
    limiter._storage.reset()


class TestJoinWaitlist:
    def test_join_waitlist_returns_joined_for_new_email(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=True)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock()
            resp = client.post("/api/waitlist", json={"email": "new@example.com"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "joined"}

    def test_join_waitlist_returns_already_registered_for_duplicate(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=False)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock()
            resp = client.post("/api/waitlist", json={"email": "existing@example.com"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "already_registered"}

    def test_join_waitlist_normalizes_email(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=True)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock()
            client.post("/api/waitlist", json={"email": "  User@Example.COM  "})
        mock_firestore.join_waitlist.assert_awaited_once_with("user@example.com")

    def test_join_waitlist_rejects_invalid_email(self, client):
        resp = client.post("/api/waitlist", json={"email": "not-an-email"})
        assert resp.status_code == 422

    def test_join_waitlist_rejects_empty_email(self, client):
        resp = client.post("/api/waitlist", json={"email": ""})
        assert resp.status_code == 422

    def test_join_waitlist_rejects_missing_email_field(self, client):
        resp = client.post("/api/waitlist", json={})
        assert resp.status_code == 422

    def test_join_waitlist_sends_confirmation_email_on_new_signup(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=True)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock()
            client.post("/api/waitlist", json={"email": "new@example.com"})
        mock_email.send_waitlist_confirmation.assert_awaited_once_with("new@example.com")

    def test_join_waitlist_skips_email_on_duplicate(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=False)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock()
            client.post("/api/waitlist", json={"email": "existing@example.com"})
        mock_email.send_waitlist_confirmation.assert_not_awaited()

    def test_join_waitlist_returns_200_when_email_send_fails(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=True)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock(side_effect=Exception("SMTP error"))
            resp = client.post("/api/waitlist", json={"email": "new@example.com"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "joined"}

    def test_join_waitlist_no_auth_required(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=True)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock()
            resp = client.post("/api/waitlist", json={"email": "public@example.com"})
        assert resp.status_code == 200

    def test_join_waitlist_accepts_plus_alias_email(self, client, mock_firestore):
        mock_firestore.join_waitlist = AsyncMock(return_value=True)
        with patch("backend.routers.waitlist.email_client") as mock_email:
            mock_email.send_waitlist_confirmation = AsyncMock()
            resp = client.post("/api/waitlist", json={"email": "user+alias@example.com"})
        assert resp.status_code == 200


class TestGetUserMe:
    def test_get_user_me_returns_401_without_auth(self, client):
        resp = client.get("/api/users/me")
        assert resp.status_code == 401

    def test_get_user_me_returns_404_when_no_user_doc(self, client, auth_headers, mock_firestore):
        mock_firestore.get_user = AsyncMock(return_value=None)
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    def test_get_user_me_returns_role_for_beta_user(self, client, auth_headers, mock_firestore):
        expires = datetime.now(UTC) + timedelta(days=10, hours=1)
        mock_firestore.get_user = AsyncMock(
            return_value={
                "role": "beta",
                "beta_expires_at": expires,
                "quick_posts_this_month": 0,
                "calendars_this_month": 0,
            }
        )
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "beta"
        assert data["days_remaining"] == 10

    def test_get_user_me_returns_role_for_paid_user(
        self, client, auth_headers, mock_firestore, paid_user_doc
    ):
        mock_firestore.get_user = AsyncMock(return_value=paid_user_doc)
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"
        assert data["days_remaining"] is None
        assert data["quick_posts_limit"] is None

    def test_get_user_me_returns_role_for_admin(
        self, client, auth_headers, mock_firestore, admin_user_doc
    ):
        mock_firestore.get_user = AsyncMock(return_value=admin_user_doc)
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["days_remaining"] is None

    def test_get_user_me_beta_with_no_expires_at_has_no_days_remaining(
        self, client, auth_headers, mock_firestore
    ):
        mock_firestore.get_user = AsyncMock(
            return_value={
                "role": "beta",
                "beta_expires_at": None,
                "quick_posts_this_month": 0,
                "calendars_this_month": 0,
            }
        )
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["days_remaining"] is None

    def test_get_user_me_beta_with_expired_token_shows_zero_days(
        self, client, auth_headers, mock_firestore
    ):
        expires = datetime.now(UTC) - timedelta(seconds=1)
        mock_firestore.get_user = AsyncMock(
            return_value={
                "role": "beta",
                "beta_expires_at": expires,
                "quick_posts_this_month": 0,
                "calendars_this_month": 0,
            }
        )
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["days_remaining"] == 0

    def test_get_user_me_returns_usage_counters(self, client, auth_headers, mock_firestore):
        mock_firestore.get_user = AsyncMock(
            return_value={
                "role": "beta",
                "beta_expires_at": FUTURE,
                "quick_posts_this_month": 3,
                "calendars_this_month": 2,
            }
        )
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["quick_posts_this_month"] == 3
        assert data["calendars_this_month"] == 2

    def test_get_user_me_returns_limits_only_for_beta(
        self, client, auth_headers, mock_firestore, beta_user_doc
    ):
        mock_firestore.get_user = AsyncMock(return_value=beta_user_doc)
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["quick_posts_limit"] == 8
        assert data["calendars_limit"] == 4

    def test_get_user_me_returns_null_limits_for_user(
        self, client, auth_headers, mock_firestore, paid_user_doc
    ):
        mock_firestore.get_user = AsyncMock(return_value=paid_user_doc)
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["quick_posts_limit"] is None
        assert data["calendars_limit"] is None

    def test_get_user_me_handles_naive_datetime_beta_expires_at(
        self, client, auth_headers, mock_firestore
    ):
        naive_dt = datetime.now()  # no tzinfo
        mock_firestore.get_user = AsyncMock(
            return_value={
                "role": "beta",
                "beta_expires_at": naive_dt,
                "quick_posts_this_month": 0,
                "calendars_this_month": 0,
            }
        )
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_user_me_missing_counter_fields_default_to_zero(
        self, client, auth_headers, mock_firestore
    ):
        mock_firestore.get_user = AsyncMock(
            return_value={"role": "beta", "beta_expires_at": FUTURE}
        )
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["quick_posts_this_month"] == 0
        assert data["calendars_this_month"] == 0


class TestVerifyBetaNotExpired:
    async def test_beta_not_expired_passes_for_active_beta(self, mock_firestore):
        from backend.middleware import verify_beta_not_expired

        mock_firestore.get_user = AsyncMock(
            return_value={
                "role": "beta",
                "beta_expires_at": datetime.now(UTC) + timedelta(days=15),
            }
        )
        result = await verify_beta_not_expired(uid=TEST_UID)
        assert result == TEST_UID

    async def test_beta_not_expired_blocks_expired_beta(
        self, mock_firestore, expired_beta_user_doc
    ):
        from fastapi import HTTPException

        from backend.middleware import verify_beta_not_expired

        mock_firestore.get_user = AsyncMock(return_value=expired_beta_user_doc)
        with pytest.raises(HTTPException) as exc_info:
            await verify_beta_not_expired(uid=TEST_UID)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "beta_expired"

    async def test_beta_not_expired_passes_for_paid_user(self, mock_firestore, paid_user_doc):
        from backend.middleware import verify_beta_not_expired

        mock_firestore.get_user = AsyncMock(return_value=paid_user_doc)
        result = await verify_beta_not_expired(uid=TEST_UID)
        assert result == TEST_UID

    async def test_beta_not_expired_passes_for_admin(self, mock_firestore, admin_user_doc):
        from backend.middleware import verify_beta_not_expired

        mock_firestore.get_user = AsyncMock(return_value=admin_user_doc)
        result = await verify_beta_not_expired(uid=TEST_UID)
        assert result == TEST_UID

    async def test_beta_not_expired_passes_when_no_user_doc(self, mock_firestore):
        from backend.middleware import verify_beta_not_expired

        mock_firestore.get_user = AsyncMock(return_value=None)
        result = await verify_beta_not_expired(uid=TEST_UID)
        assert result == TEST_UID

    async def test_beta_not_expired_passes_when_no_uid(self, mock_firestore):
        from backend.middleware import verify_beta_not_expired

        result = await verify_beta_not_expired(uid=None)
        assert result is None

    async def test_beta_expires_exactly_now_treated_as_expired(self, mock_firestore):
        from fastapi import HTTPException

        from backend.middleware import verify_beta_not_expired

        mock_firestore.get_user = AsyncMock(
            return_value={
                "role": "beta",
                "beta_expires_at": datetime.now(UTC) - timedelta(seconds=1),
            }
        )
        with pytest.raises(HTTPException) as exc_info:
            await verify_beta_not_expired(uid=TEST_UID)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "beta_expired"

    async def test_beta_not_expired_handles_naive_datetime(self, mock_firestore):
        from backend.middleware import verify_beta_not_expired

        naive_future = datetime.now() + timedelta(days=10)  # no tzinfo
        mock_firestore.get_user = AsyncMock(
            return_value={"role": "beta", "beta_expires_at": naive_future}
        )
        result = await verify_beta_not_expired(uid=TEST_UID)
        assert result == TEST_UID


class TestCheckBetaBrandLimit:
    def test_brand_limit_allows_first_brand_for_beta(
        self, client, auth_headers, mock_firestore, beta_user_doc
    ):
        mock_firestore.get_user = AsyncMock(return_value=beta_user_doc)
        mock_firestore.list_brands_by_owner = AsyncMock(return_value=[])
        resp = client.post(
            "/api/brands",
            json={
                "website_url": "https://example.com",
                "description": "A test brand for unit testing",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_brand_limit_blocks_second_brand_for_beta(
        self, client, auth_headers, mock_firestore, beta_user_doc, sample_brand
    ):
        mock_firestore.get_user = AsyncMock(return_value=beta_user_doc)
        mock_firestore.list_brands_by_owner = AsyncMock(return_value=[sample_brand])
        resp = client.post(
            "/api/brands",
            json={
                "website_url": "https://example.com",
                "description": "A test brand for unit testing",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "beta_limit_brands"

    def test_brand_limit_not_applied_for_paid_user(
        self, client, auth_headers, mock_firestore, paid_user_doc, sample_brand
    ):
        mock_firestore.get_user = AsyncMock(return_value=paid_user_doc)
        mock_firestore.list_brands_by_owner = AsyncMock(return_value=[sample_brand] * 5)
        resp = client.post(
            "/api/brands",
            json={
                "website_url": "https://example.com",
                "description": "A test brand for unit testing",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_brand_limit_not_applied_for_admin(
        self, client, auth_headers, mock_firestore, admin_user_doc
    ):
        mock_firestore.get_user = AsyncMock(return_value=admin_user_doc)
        resp = client.post(
            "/api/brands",
            json={
                "website_url": "https://example.com",
                "description": "A test brand for unit testing",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_brand_limit_not_applied_when_no_uid(self, mock_firestore):
        from backend.middleware import check_beta_brand_limit

        result = await check_beta_brand_limit(uid=None)
        assert result is None


class TestCheckBetaQuickPostLimit:
    async def test_quick_post_limit_allows_within_limit(self, mock_firestore, beta_user_doc):
        from backend.middleware import check_beta_quick_post_limit

        beta_user_doc["quick_posts_this_month"] = 7
        mock_firestore.get_user = AsyncMock(return_value=beta_user_doc)
        result = await check_beta_quick_post_limit(uid=TEST_UID)
        assert result == TEST_UID

    def test_quick_post_limit_blocks_at_limit(
        self, client, auth_headers, mock_firestore, beta_user_doc
    ):
        beta_user_doc["quick_posts_this_month"] = 8
        mock_firestore.get_user = AsyncMock(return_value=beta_user_doc)
        resp = client.get(
            f"/api/generate/quickpost/{TEST_BRAND_ID}?platform=instagram",
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "beta_limit_quick_posts"

    async def test_quick_post_limit_not_applied_for_paid_user(self, mock_firestore, paid_user_doc):
        from backend.middleware import check_beta_quick_post_limit

        mock_firestore.get_user = AsyncMock(return_value=paid_user_doc)
        result = await check_beta_quick_post_limit(uid=TEST_UID)
        assert result == TEST_UID

    async def test_quick_post_limit_not_applied_when_no_uid(self, mock_firestore):
        from backend.middleware import check_beta_quick_post_limit

        result = await check_beta_quick_post_limit(uid=None)
        assert result is None


class TestCheckBetaCalendarLimit:
    def test_calendar_limit_allows_within_limit(
        self, client, auth_headers, mock_firestore, beta_user_doc, sample_brand, sample_plan
    ):
        beta_user_doc["calendars_this_month"] = 3
        mock_firestore.get_user = AsyncMock(return_value=beta_user_doc)
        mock_firestore.get_brand = AsyncMock(return_value=sample_brand)
        mock_firestore.create_plan = AsyncMock(return_value="new-plan-id")
        with patch(
            "backend.routers.plans.run_strategy",
            new=AsyncMock(return_value=(sample_plan["days"], {"highlights": ["trend1"]})),
        ):
            resp = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans",
                json={"num_days": 7},
                headers=auth_headers,
            )
        assert resp.status_code != 403

    def test_calendar_limit_blocks_at_limit(
        self, client, auth_headers, mock_firestore, beta_user_doc
    ):
        beta_user_doc["calendars_this_month"] = 4
        mock_firestore.get_user = AsyncMock(return_value=beta_user_doc)
        resp = client.post(
            f"/api/brands/{TEST_BRAND_ID}/plans",
            json={"num_days": 7},
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "beta_limit_calendars"

    def test_calendar_limit_not_applied_for_paid_user(
        self, client, auth_headers, mock_firestore, paid_user_doc, sample_brand, sample_plan
    ):
        mock_firestore.get_user = AsyncMock(return_value=paid_user_doc)
        mock_firestore.get_brand = AsyncMock(return_value=sample_brand)
        mock_firestore.create_plan = AsyncMock(return_value="new-plan-id")
        with patch(
            "backend.routers.plans.run_strategy",
            new=AsyncMock(return_value=(sample_plan["days"], {"highlights": ["trend1"]})),
        ):
            resp = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans",
                json={"num_days": 7},
                headers=auth_headers,
            )
        assert resp.status_code != 403

    async def test_calendar_limit_not_applied_when_no_uid(self, mock_firestore):
        from backend.middleware import check_beta_calendar_limit

        result = await check_beta_calendar_limit(uid=None)
        assert result is None
