# QA Test Plan — Dependency Upgrades (Issue #7)

## Scope

Changes on branch `chore/dependency-upgrades-issue-7`:
- Removed `google-adk==1.25.0` (unused)
- `google-genai` 1.64 → ~1.74
- `google-cloud-storage` 2.18 → 3.12
- `firebase-admin` 6.5 → 7.4
- `middleware.py`: `_apps` check → `get_app()/ValueError`, `verify_id_token` moved to executor, exception logging uses `type(e).__name__`
- New unclaimed-brand write guard in `verify_brand_owner`

---

## Happy Path Tests

All already covered in `test_middleware.py` — confirm they still pass:

| # | Test | Expected |
|---|---|---|
| HP-1 | Valid Bearer token → `get_authenticated_uid` returns UID | `TEST_UID` returned, `verify_id_token` called once |
| HP-2 | Owner UID matches brand `owner_uid` → `verify_brand_owner` returns UID | `TEST_UID` returned, no exception |
| HP-3 | Unclaimed brand + GET + no auth → `verify_brand_owner` returns `None` | Passes; read allowed without auth |
| HP-4 | Route without `brand_id` path param → check skipped | UID passed through unchanged |
| HP-5 | Firebase SDK not yet initialised at import time → `get_app()` raises `ValueError`, `initialize_app()` called | App initialises once; no crash on subsequent requests |

---

## Edge Cases

| # | Test | Input | Expected |
|---|---|---|---|
| EC-1 | `verify_id_token` runs in executor (non-blocking) | Valid token via `run_in_executor` mock | Awaited correctly; event loop not blocked |
| EC-2 | Unclaimed brand + PUT → write blocked | `method="PUT"`, `user_uid=None` | 401 |
| EC-3 | Unclaimed brand + DELETE → write blocked | `method="DELETE"`, `user_uid=None` | 401 |
| EC-4 | Unclaimed brand + OPTIONS → read allowed | `method="OPTIONS"`, `user_uid=None` | `None` returned (no exception) |
| EC-5 | Unclaimed brand + POST + authenticated user → allowed | `method="POST"`, `user_uid=TEST_UID` | `TEST_UID` returned |
| EC-6 | `Authorization: Bearer ` (empty token after prefix) | Malformed header | `None` returned (treated as no token) |
| EC-7 | `firebase_admin.get_app()` called twice (module imported twice) | Re-import scenario | `initialize_app()` called exactly once |

---

## Error Cases

| # | Test | Trigger | Expected |
|---|---|---|---|
| ER-1 | Expired token → `ExpiredIdTokenError` | `verify_id_token` raises `ExpiredIdTokenError` | 401, detail contains "expired" |
| ER-2 | Invalid token → `InvalidIdTokenError` | `verify_id_token` raises `InvalidIdTokenError` | 401, detail contains "invalid" |
| ER-3 | Generic exception (network error) → fallback 401 | `verify_id_token` raises `RuntimeError` | 401, NO token content in log message |
| ER-4 | Generic exception does NOT leak token in logs | `RuntimeError("token=abc123")` | Log message contains only `RuntimeError`, not the exception message |
| ER-5 | Brand not found → 404 | `firestore_client.get_brand` returns `None` | 404 |
| ER-6 | Wrong owner → 403 | `user_uid != brand.owner_uid` | 403 |
| ER-7 | No auth on claimed brand → 401 | `user_uid=None`, brand has `owner_uid` set | 401 |
| ER-8 | WS: missing `auth.` subprotocol → 1008 | No auth token in `Sec-WebSocket-Protocol` | `WebSocketException` code 1008 |
| ER-9 | WS: expired token → 1008 | `verify_id_token` raises `ExpiredIdTokenError` | `WebSocketException` code 1008, reason "Token expired" |
| ER-10 | WS: generic exception does NOT leak token in logs | `RuntimeError("token=abc123")` in WS path | Log message contains only `RuntimeError` |

---

## Integration Points

| Area | Mock needed | Fixture |
|---|---|---|
| Firebase token verification | `patch("backend.middleware.firebase_auth")` | `mock_verify_token` (conftest.py) |
| Firestore brand lookup | `patch("backend.middleware.firestore_client")` + `AsyncMock(return_value=...)` | inline per test |
| Firebase Admin init guard | `MagicMock(get_app=MagicMock(...), _apps={...})` patched into `sys.modules` | `conftest.py` module-level patch |
| `run_in_executor` | Use `mock_verify_token` — the executor calls the mock synchronously in tests | `mock_verify_token` fixture |

No GCS, Gemini, or SSE mocks are needed — this change does not touch agent or streaming paths.

---

## Regression Risk

### Existing tests to re-verify

- `test_middleware.py` — primary suite; all 12+ cases must pass
- `test_brands.py` — exercises routes behind `verify_brand_owner`; any auth regression surfaces here
- `test_plans.py` — same as above
- `test_posts.py` — same as above

### Coverage gaps exposed by this change

| Gap | Recommended new test |
|---|---|
| `run_in_executor` is actually awaited (not called sync) | EC-1: assert `loop.run_in_executor` is called, not `verify_id_token` directly |
| Exception log message does not contain raw exception string | ER-4, ER-10: capture log output, assert token string absent |
| Unclaimed brand + non-safe methods (PUT, DELETE) | EC-2, EC-3 |
| Unclaimed brand + authenticated write | EC-5 |

---

## Out of Scope

- GCS API surface changes (`upload_from_string`, `generate_signed_url`) — mocked in all tests; manual smoke test required
- Gemini API response shape changes — mocked in all agent tests; manual smoke test required
- `firebase-admin` transitive dep conflicts — verified via `pip install` resolution; no test needed

---

## Manual Smoke Tests (post-merge, requires `.env`)

1. **Auth round-trip**: authenticated `GET /api/brands` → 200 (exercises `verify_id_token` via real Firebase)
2. **GCS upload**: upload brand asset → verify blob in GCS bucket (`upload_from_string` + `generate_signed_url`)
3. **Genai call**: trigger strategy agent → verify SSE stream starts (`types.Tool(google_search=...)`)
4. **Image generation**: trigger content creator with image → verify `response.candidates[0]` access works
