# QA Test Plan — Issue #12: Storage Strategy + URL Expiry + Rate Limiting

## Scope

Three behavioural changes to test:
1. **BYOP URL refresh-on-read** — `custom_photo_url` is never stored in Firestore; freshly generated on every plan read
2. **`custom_photo_url` write-protection** — `PUT /plans/{id}/days/{idx}` and `POST .../photo` cannot persist a signed URL to Firestore
3. **Global concurrency semaphores** — `gemini_image_limit` (4) and `veo_limit` (2) throttle concurrent API calls

Existing file: `backend/tests/test_plans.py` (45 tests, all passing).
New tests go in `backend/tests/test_plans.py` and `backend/tests/test_rate_limiter.py`.

---

## Fixtures needed

All tests use fixtures from `conftest.py`:
- `client` — FastAPI TestClient with mocked auth + Firestore
- `auth_headers` — `{"Authorization": "Bearer fake-valid-token"}`
- `sample_brand`, `sample_plan` — standard brand/plan dicts
- `mock_gcs_bucket` — mocks `storage_client.get_bucket`; `mock_blob.generate_signed_url` returns `"https://signed.example.com/image.png"`

Additional helper: patch `backend.routers.plans.get_signed_url` (module-level import) to avoid real GCS calls in plan read tests.

---

## 1. Happy Path Tests

### 1.1 `GET /brands/{id}/plans/{plan_id}` — BYOP photo URL refreshed on read

**Input:** Plan has a day with `custom_photo_gcs_uri = "gs://bucket/byop/brand/photo.jpg"` and no `custom_photo_url` stored.
**Mock:** `get_signed_url` returns `"https://fresh.signed/photo.jpg"`
**Expected:** Response `plan_profile.days[N].custom_photo_url == "https://fresh.signed/photo.jpg"`
**Assertion:** `get_signed_url` was called with `"gs://bucket/byop/brand/photo.jpg"`

### 1.2 `GET /brands/{id}/plans` — all plans have BYOP URLs refreshed

**Input:** Two plans; plan A has one BYOP day, plan B has no BYOP days.
**Mock:** `get_signed_url` returns distinct URLs
**Expected:** Plan A's day has fresh `custom_photo_url`; plan B's days are unchanged.
**Assertion:** `get_signed_url` called exactly once (for plan A's BYOP day only).

### 1.3 `GET /brands/{id}/plans/{plan_id}` — day without BYOP photo untouched

**Input:** Plan with a day that has no `custom_photo_gcs_uri`.
**Mock:** `get_signed_url` not called.
**Expected:** `custom_photo_url` absent from that day in the response.

### 1.4 `POST .../days/{idx}/photo` — upload stores GCS URI only, returns fresh URL

**Input:** Valid JPEG upload.
**Mock:** `upload_byop_photo` returns `("https://upload-signed/p.jpg", "gs://b/byop/p.jpg")`
**Expected:**
- `update_plan_day` called with dict containing `custom_photo_gcs_uri` but NOT `custom_photo_url`
- Response body `custom_photo_url == "https://upload-signed/p.jpg"`

### 1.5 `PUT .../days/{idx}` — `custom_photo_url` in request body is silently dropped

**Input:** Body `{"custom_photo_url": "https://attacker.com/evil.jpg", "platform": "instagram"}`
**Expected:** `update_plan_day` called without `custom_photo_url` in the data dict; `platform` is persisted normally.

### 1.6 Multiple BYOP days — all refreshed concurrently

**Input:** Plan with 3 days all having `custom_photo_gcs_uri`.
**Mock:** `get_signed_url` returns unique URL per call.
**Expected:** All 3 days have distinct `custom_photo_url` values. `get_signed_url` called 3 times.

---

## 2. Edge Cases

### 2.1 Plan with `days` missing entirely

**Input:** Firestore returns plan dict with no `"days"` key.
**Expected:** `GET /plans/{id}` returns 200 with plan data; no error raised; `get_signed_url` not called.

### 2.2 Plan with `days: null` (corrupted document)

**Input:** `plan["days"] = None`
**Expected:** Endpoint returns 200; `_refresh_plan_photo_urls` skips refresh gracefully.

### 2.3 GCS re-sign fails for one day — other days unaffected

**Input:** Plan with 2 BYOP days. `get_signed_url` raises `Exception("GCS error")` for day 0, succeeds for day 1.
**Expected:** Day 0 has no `custom_photo_url` in response (or retains old value). Day 1 has fresh URL. No 500 error — endpoint returns 200.
**Assertion:** Warning logged for day 0.

### 2.4 Upload — file exactly at 20 MB limit

**Input:** File body of exactly `20 * 1024 * 1024` bytes.
**Expected:** 200 OK (boundary is inclusive of max_size check).

### 2.5 Upload — file one byte over 20 MB

**Input:** File body of `20 * 1024 * 1024 + 1` bytes.
**Expected:** 400 with `"Image must be smaller than 20 MB"`.

### 2.6 `PUT .../days/{idx}` — `custom_photo_gcs_uri` accepted normally

**Input:** Body `{"custom_photo_gcs_uri": "gs://bucket/byop/new.jpg"}` (valid field, not blocked).
**Expected:** `update_plan_day` called with `custom_photo_gcs_uri` in the data dict.

### 2.7 Rate limiter — semaphore releases even when wrapped call raises

**Input:** `gemini_image_limit` acquired; wrapped coroutine raises `RuntimeError`.
**Expected:** Semaphore value returns to original after exception. Subsequent acquisition succeeds immediately.

### 2.8 Rate limiter — semaphore blocks 5th concurrent attempt

**Input:** 4 coroutines hold `gemini_image_limit` slots simultaneously; 5th tries to acquire.
**Expected:** 5th waits until one slot is released, then proceeds.

---

## 3. Error Cases

### 3.1 `GET /plans/{id}` — plan not found

**Input:** `firestore_client.get_plan` returns `None`.
**Expected:** 404 `"Plan not found"`. `get_signed_url` not called.

### 3.2 `POST .../photo` — plan not found

**Input:** `firestore_client.get_plan` returns `None`.
**Expected:** 404.

### 3.3 `POST .../photo` — day_index out of range

**Input:** Plan has 7 days; `day_index=7`.
**Expected:** 400 `"day_index 7 out of range"`.

### 3.4 `POST .../photo` — unsupported MIME type

**Input:** `content_type = "image/gif"`.
**Expected:** 400 `"Only JPEG, PNG, or WebP images are accepted"`.

### 3.5 `POST .../photo` — GCS upload fails

**Input:** `upload_byop_photo` raises `Exception("GCS unavailable")`.
**Expected:** 500. `update_plan_day` not called.

### 3.6 `GET /plans/{id}` — no auth token

**Input:** Request with no `Authorization` header.
**Expected:** 401/403.

### 3.7 `PUT .../days/{idx}` — Firestore update fails

**Input:** `update_plan_day` raises `Exception("Firestore error")`.
**Expected:** 500 `"Internal server error"`. Error logged.

---

## 4. Integration Points

| Component | Mock target | Fixture |
|---|---|---|
| Firestore plan reads | `backend.routers.plans.firestore_client` | `patch(_PLANS_FC)` (existing pattern) |
| GCS signed URL | `backend.routers.plans.get_signed_url` | `AsyncMock(return_value=...)` |
| GCS upload | `backend.routers.plans.upload_byop_photo` | `AsyncMock(return_value=(url, gcs_uri))` |
| Auth | `backend.middleware.firebase_auth` | `mock_verify_token` fixture |
| Rate limiter semaphore | `asyncio.Semaphore` directly | No mock needed — test the real semaphore |

---

## 5. Rate Limiter Unit Tests (`test_rate_limiter.py`)

### 5.1 `gemini_image_limit` — acquired and released cleanly

Use the real `gemini_image_limit` from `rate_limiter.py`. Enter and exit the async context manager. Assert semaphore value returns to 4.

### 5.2 `veo_limit` — acquired and released cleanly

Same as above for `veo_limit`, assert value returns to 2.

### 5.3 Wait-time logging — logged when wait exceeds threshold

Mock `time.monotonic` to simulate 200ms wait. Assert `logger.info` called with `"rate_limiter: gemini_image waited"`.

### 5.4 Wait-time logging — not logged when wait is fast

Mock `time.monotonic` to simulate 50ms wait. Assert `logger.info` not called.

### 5.5 Semaphore releases on exception inside `async with`

Enter `gemini_image_limit`, raise inside the block. Assert semaphore value is restored after exception.

---

## 6. Regression Risk

| Existing test | Risk |
|---|---|
| `TestUploadDayPhoto::test_saves_gcs_uri_to_firestore_not_signed_url` | Already updated in Phase 2 |
| `TestGetPlan` | Must continue to pass; now calls `get_signed_url` — ensure it's patched to avoid real GCS |
| `TestListPlans` | Same — `get_signed_url` must be patched in any test that calls `list_plans` |
| `TestUpdatePlanDay` | Must verify `custom_photo_url` is still blocked via `_BLOCKED_FIELDS` |
| `TestStreamGenerateVideoFirst` | Already fixed in Phase 2 (patch target corrected) |

**Gap exposed:** Existing `TestGetPlan` and `TestListPlans` tests do not patch `get_signed_url`. If the plan fixture has days with `custom_photo_gcs_uri`, these tests will attempt real GCS calls. Either the fixture must not include BYOP fields (current `sample_plan` does not), or the tests must patch `get_signed_url`.

Current `sample_plan` fixture has no `custom_photo_gcs_uri` fields, so existing tests are safe. New tests that add BYOP days must patch `get_signed_url`.
