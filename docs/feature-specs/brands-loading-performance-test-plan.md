# QA Test Plan — Brands Loading Performance (Issue #11)

## Scope

Three changes are in scope:
1. `backend/services/firestore_client.py` — `list_brands_by_owner()` now uses server-side `order_by("created_at", "DESCENDING")` instead of a Python-side sort; `FailedPrecondition` degrades gracefully to `[]`; other exceptions propagate as 500s; safety-net Python sort handles `None` `created_at` values
2. `frontend/src/pages/BrandsPage.tsx` — `brandsLoading` state drives a 3-row skeleton; `brandsError` state surfaces fetch failures; stale fetch cancelled on unmount/uid change
3. `terraform/main.tf` — composite Firestore index `(owner_uid ASC, created_at DESC, __name__ DESC)`

Existing test file: `backend/tests/test_firestore_client.py` (class `TestBrandOperations`)
Existing API test file: `backend/tests/test_brands.py`

---

## Happy Path Tests

### HP-1: `list_brands_by_owner` returns brands sorted newest-first
**File:** `backend/tests/test_firestore_client.py` → `TestBrandOperations`
**Setup:** Mock `.where().order_by().get()` returning two docs with distinct `created_at` values
**Input:** `owner_uid="uid-1"`, doc1 `created_at=2024-01-02`, doc2 `created_at=2024-01-01`
**Expected:** Returns list of 2 dicts; `brands[0]["brand_id"] == "b1"` (newer first)
**Already covered:** Yes — `test_list_brands_by_owner_returns_brands`

### HP-2: `list_brands_by_owner` uses the correct Firestore query chain
**File:** `backend/tests/test_firestore_client.py`
**Setup:** Mock db and assert call chain
**Expected:** `db.collection("brands").where(...).order_by("created_at", direction="DESCENDING").get()` is called — not the old `.where().get()` chain
**Already covered:** Yes — mock chain in `test_list_brands_by_owner_returns_brands` validates this

### HP-3: GET `/brands` API endpoint returns 200 with brand list
**File:** `backend/tests/test_brands.py`
**Setup:** `client` fixture (mocked auth + firestore); `mock_firestore.list_brands_by_owner` returns `[sample_brand]`
**Input:** `GET /brands?owner_uid=test-user-uid-123` with `auth_headers`
**Expected:** 200, `response.json()["brands"]` has 1 item, `brand_id == TEST_BRAND_ID`
**Already covered:** Check existing test — add if missing

### HP-4: Safety-net sort handles `None` `created_at`
**File:** `backend/tests/test_firestore_client.py`
**Setup:** Mock returns docs where one has `created_at=None` and another has a real datetime
**Input:** `owner_uid="uid-1"`
**Expected:** Returns 2 brands; the one with real `created_at` sorts first; no exception raised

### HP-5: `FailedPrecondition` degrades gracefully to empty list
**File:** `backend/tests/test_firestore_client.py`
**Already covered:** Yes — `test_list_brands_by_owner_returns_empty_on_missing_index`

---

## Edge Cases

### EC-1: All brands have `None` `created_at`
**File:** `backend/tests/test_firestore_client.py`
**Setup:** Mock returns 3 docs all with `created_at=None`
**Expected:** Returns list of 3, no exception, order stable (all use `datetime.min` sentinel)

### EC-2: Single brand returned
**File:** `backend/tests/test_firestore_client.py`
**Setup:** Mock returns 1 doc
**Expected:** Returns list of length 1; sort does not crash on single-element list

### EC-3: Empty brand list (user has no brands)
**File:** `backend/tests/test_firestore_client.py`
**Setup:** Mock returns `[]`
**Expected:** Returns `[]`, no exception

### EC-4: Doc with `to_dict()` returning `None` is filtered out
**File:** `backend/tests/test_firestore_client.py`
**Setup:** Mock returns [doc_with_data, doc_returning_none]
**Expected:** Only the valid doc appears in result; no `AttributeError` or `TypeError`

### EC-5: Large number of brands (pagination boundary)
**File:** `backend/tests/test_brands.py`
**Setup:** `mock_firestore.list_brands_by_owner` returns 11 brands
**Input:** `GET /brands?owner_uid=...&limit=5&offset=5`
**Expected:** 200, returns brands 5–9 (slice of full list)

---

## Error Cases

### ER-1: Unexpected Firestore exception propagates (not swallowed)
**File:** `backend/tests/test_firestore_client.py`
**Already covered:** Yes — `test_list_brands_by_owner_raises_on_unexpected_exception`

### ER-2: GET `/brands` returns 500 when Firestore raises unexpected exception
**File:** `backend/tests/test_brands.py`
**Setup:** `mock_firestore.list_brands_by_owner = AsyncMock(side_effect=Exception("Firestore down"))`
**Input:** `GET /brands?owner_uid=...` with `auth_headers`
**Expected:** 500 response (not 200 with empty list)

### ER-3: Missing `owner_uid` query param
**File:** `backend/tests/test_brands.py`
**Input:** `GET /brands` with no query params, `auth_headers`
**Expected:** 422 Unprocessable Entity (FastAPI validation)

### ER-4: Missing auth token
**File:** `backend/tests/test_brands.py`
**Input:** `GET /brands?owner_uid=uid-1` with no Authorization header
**Expected:** 401 Unauthorized

### ER-5: Expired auth token
**File:** `backend/tests/test_brands.py`
**Setup:** `mock_verify_token` raises `ExpiredIdTokenError`
**Expected:** 401 Unauthorized

### ER-6: `FailedPrecondition` on missing index logs a warning and returns empty list (not 500)
**File:** `backend/tests/test_firestore_client.py`
**Already covered:** Yes — `test_list_brands_by_owner_returns_empty_on_missing_index`
**Add:** Assert that `logger.warning` was called (use `caplog` fixture)

---

## Integration Points

| Concern | Fixture to use |
|---|---|
| Firestore `list_brands_by_owner` | `mock_firestore` (patches `backend.services.firestore_client`) |
| Firebase token verification | `mock_verify_token` |
| Full API test | `client` fixture (combines both) |
| Direct unit test of `list_brands_by_owner` | `patch("backend.services.firestore_client.get_client")` |

No Gemini API, GCS, WebSocket, or SSE involvement in this change.

---

## Regression Risk

| Existing test | Risk |
|---|---|
| `test_list_brands_by_owner_returns_brands` | Mock chain changed from `.where().get()` to `.where().order_by().get()` — already updated |
| `test_list_brands_by_owner_swallows_exception_and_returns_empty` | Removed — replaced with propagation + FailedPrecondition tests |
| Any `test_brands.py` test calling `GET /brands` | Low — router unchanged; mock_firestore return value unchanged |

**Gap exposed:** No existing test validates that the API returns 500 (not 200+empty) when `list_brands_by_owner` raises. Add ER-2.

---

## Out of Scope

- Frontend skeleton rendering (no pytest coverage; verify manually in browser)
- Terraform index resource (no automated test; verify via `terraform plan` output)
- `created_at` backfill migration for legacy brand documents
