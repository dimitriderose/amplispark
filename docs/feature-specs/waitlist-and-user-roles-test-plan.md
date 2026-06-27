# QA Test Plan: Waitlist + Role-Based User Gating

**Feature branch:** `feat/waitlist-and-user-roles`
**Test file:** `backend/tests/test_waitlist.py`

---

## Scope

New endpoints and middleware introduced by the waitlist + user-roles feature:

- `POST /api/waitlist` — public, rate-limited
- `GET /api/users/me` — auth required
- `verify_beta_not_expired` middleware dependency
- `check_beta_brand_limit` dependency on `POST /api/brands`
- `check_beta_quick_post_limit` dependency on quick-post endpoint
- `check_beta_calendar_limit` dependency on `POST /api/brands/{brand_id}/plans`

---

## Fixtures

Re-use from `conftest.py`:
- `mock_verify_token` — patches `backend.middleware.firebase_auth`
- `mock_firestore` — patches `backend.services.firestore_client` + `backend.middleware.firestore_client`
- `client` — `TestClient(app)` with both mocks active
- `auth_headers` — `{"Authorization": "Bearer fake-valid-token"}`

Additional fixtures to define in `test_waitlist.py`:
- `beta_user_doc` — `{"role": "beta", "beta_expires_at": <future>, "quick_posts_this_month": 0, "calendars_this_month": 0}`
- `expired_beta_user_doc` — same but `beta_expires_at` in the past
- `paid_user_doc` — `{"role": "user"}`
- `admin_user_doc` — `{"role": "admin"}`

---

## Test Cases

### `TestJoinWaitlist` — `POST /api/waitlist`

| # | Test name | Inputs | Expected |
|---|---|---|---|
| 1 | `test_join_waitlist_returns_joined_for_new_email` | `{"email": "new@example.com"}`, `join_waitlist` returns `True` | 200, `{"status": "joined"}` |
| 2 | `test_join_waitlist_returns_already_registered_for_duplicate` | `join_waitlist` returns `False` | 200, `{"status": "already_registered"}` |
| 3 | `test_join_waitlist_normalizes_email` | `{"email": "  User@Example.COM  "}` | `join_waitlist` called with `"user@example.com"` |
| 4 | `test_join_waitlist_rejects_invalid_email` | `{"email": "not-an-email"}` | 422 |
| 5 | `test_join_waitlist_rejects_empty_email` | `{"email": ""}` | 422 |
| 6 | `test_join_waitlist_rejects_missing_email_field` | `{}` | 422 |
| 7 | `test_join_waitlist_sends_confirmation_email_on_new_signup` | `join_waitlist` returns `True` | `email_client.send_waitlist_confirmation` called once with the email |
| 8 | `test_join_waitlist_skips_email_on_duplicate` | `join_waitlist` returns `False` | `email_client.send_waitlist_confirmation` not called |
| 9 | `test_join_waitlist_returns_200_when_email_send_fails` | `join_waitlist` returns `True`, email raises exception | 200, `{"status": "joined"}` (email failure is silent) |
| 10 | `test_join_waitlist_no_auth_required` | No `Authorization` header | 200 (public endpoint) |

### `TestGetUserMe` — `GET /api/users/me`

| # | Test name | Setup | Expected |
|---|---|---|---|
| 11 | `test_get_user_me_returns_401_without_auth` | No auth header | 401 |
| 12 | `test_get_user_me_returns_404_when_no_user_doc` | `get_user` returns `None` | 404, `{"detail": "User not found"}` |
| 13 | `test_get_user_me_returns_role_for_beta_user` | `get_user` returns beta doc with `beta_expires_at` 10 days out | 200, `role == "beta"`, `days_remaining == 10` |
| 14 | `test_get_user_me_returns_role_for_paid_user` | `get_user` returns `{"role": "user"}` | 200, `role == "user"`, `days_remaining == None`, `quick_posts_limit == None` |
| 15 | `test_get_user_me_returns_role_for_admin` | `get_user` returns `{"role": "admin"}` | 200, `role == "admin"`, `days_remaining == None` |
| 16 | `test_get_user_me_beta_with_no_expires_at_has_no_days_remaining` | beta doc, `beta_expires_at: None` | 200, `days_remaining == None` |
| 17 | `test_get_user_me_beta_with_expired_token_shows_zero_days` | `beta_expires_at` 1 second in the past | 200, `days_remaining == 0` |
| 18 | `test_get_user_me_returns_usage_counters` | beta doc with `quick_posts_this_month: 3, calendars_this_month: 2` | 200, counters match |
| 19 | `test_get_user_me_returns_limits_only_for_beta` | beta user | `quick_posts_limit == 8`, `calendars_limit == 4` |
| 20 | `test_get_user_me_returns_null_limits_for_user` | paid user | `quick_posts_limit == None`, `calendars_limit == None` |
| 21 | `test_get_user_me_handles_naive_datetime_beta_expires_at` | `beta_expires_at` is timezone-naive datetime | 200, no `TypeError` |

### `TestVerifyBetaNotExpired` — middleware dependency

Test via any protected route that wires `verify_beta_not_expired`. Use `POST /api/brands` (which has this dependency via its auth chain) or test the dependency function directly.

| # | Test name | Setup | Expected |
|---|---|---|---|
| 22 | `test_beta_not_expired_passes_for_active_beta` | beta user, `beta_expires_at` 15 days from now | Request succeeds (200) |
| 23 | `test_beta_not_expired_blocks_expired_beta` | beta user, `beta_expires_at` 1 day in the past | 403, `{"code": "beta_expired"}` |
| 24 | `test_beta_not_expired_passes_for_paid_user` | `{"role": "user"}`, no `beta_expires_at` | Request succeeds |
| 25 | `test_beta_not_expired_passes_for_admin` | `{"role": "admin"}` | Request succeeds |
| 26 | `test_beta_not_expired_passes_when_no_user_doc` | `get_user` returns `None` | Request succeeds (gating only for known beta users) |

### `TestCheckBetaBrandLimit` — `POST /api/brands`

| # | Test name | Setup | Expected |
|---|---|---|---|
| 27 | `test_brand_limit_allows_first_brand_for_beta` | beta user, `list_brands_by_owner` returns `[]` | 200/201 (brand creation proceeds) |
| 28 | `test_brand_limit_blocks_second_brand_for_beta` | beta user, `list_brands_by_owner` returns 1 brand | 403, `{"code": "beta_limit_brands"}` |
| 29 | `test_brand_limit_not_applied_for_paid_user` | `{"role": "user"}`, `list_brands_by_owner` returns 5 brands | 200 |
| 30 | `test_brand_limit_not_applied_for_admin` | `{"role": "admin"}` | 200 |

### `TestCheckBetaQuickPostLimit` — quick post endpoint

| # | Test name | Setup | Expected |
|---|---|---|---|
| 31 | `test_quick_post_limit_allows_within_limit` | beta user, `quick_posts_this_month: 7` (limit is 8) | 200 |
| 32 | `test_quick_post_limit_blocks_at_limit` | beta user, `quick_posts_this_month: 8` | 403, `{"code": "beta_limit_quick_posts"}` |
| 33 | `test_quick_post_limit_not_applied_for_paid_user` | `{"role": "user"}`, any counter value | 200 |

### `TestCheckBetaCalendarLimit` — `POST /api/brands/{brand_id}/plans`

| # | Test name | Setup | Expected |
|---|---|---|---|
| 34 | `test_calendar_limit_allows_within_limit` | beta user, `calendars_this_month: 3` (limit is 4) | 200 |
| 35 | `test_calendar_limit_blocks_at_limit` | beta user, `calendars_this_month: 4` | 403, `{"code": "beta_limit_calendars"}` |
| 36 | `test_calendar_limit_not_applied_for_paid_user` | `{"role": "user"}` | 200 |

---

## Edge Cases

| # | Test name | Notes |
|---|---|---|
| 37 | `test_join_waitlist_accepts_plus_alias_email` | `user+alias@example.com` → 200 |
| 38 | `test_get_user_me_missing_counter_fields_default_to_zero` | user doc has no `quick_posts_this_month` field → response defaults to 0 |
| 39 | `test_beta_expires_exactly_now_treated_as_expired` | `beta_expires_at == datetime.now(UTC)` → `days_remaining == 0`, but expiry check should block |

---

## Regression Risk

The following existing test classes are affected by the new middleware dependencies:

- **`TestCreatePlan`** in `test_plans.py` — already fixed (autouse `mock_get_user` fixture)
- **`TestCreateBrand`** in `test_brands.py` — `check_beta_brand_limit` is now a dependency; tests must ensure `get_user` is mocked to return a non-beta user or the limit check short-circuits
- **Quick-post tests** in `test_generation.py` — `check_beta_quick_post_limit` dependency; same fix required

Verify these pass without modification after adding `test_waitlist.py`.

---

## Patterns

```python
# Beta user fixture
@pytest.fixture
def beta_user_doc():
    return {
        "role": "beta",
        "beta_expires_at": datetime.now(UTC) + timedelta(days=30),
        "quick_posts_this_month": 0,
        "calendars_this_month": 0,
        "counters_reset_at": datetime.now(UTC),
    }

# Patch both module references (same as conftest mock_firestore)
with patch("backend.services.firestore_client") as fc, \
     patch("backend.middleware.firestore_client", fc):
    fc.join_waitlist = AsyncMock(return_value=True)
    ...

# Patch email_client to avoid real Resend calls
with patch("backend.routers.waitlist.email_client") as mock_email:
    mock_email.send_waitlist_confirmation = AsyncMock()
    ...
```
