# QA Test Plan — Notifications Bell (Issue #22)

**Feature branch:** `feat/notifications-bell-issue-22`  
**Test file to create:** `backend/tests/test_notifications.py`

---

## Fixtures & Setup

All tests use the existing `conftest.py` patterns:
- `client` fixture: `TestClient(app)` with mocked auth + Firestore
- `auth_headers`: `{"Authorization": "Bearer fake-valid-token"}`
- `mock_verify_token`: patches `firebase_auth.verify_id_token` → `{"uid": TEST_UID}`
- `mock_firestore`: patches `backend.services.firestore_client`

Patch targets:
```python
_NOTIF_FC = "backend.routers.notifications.firestore_client"
_GEN_FC   = "backend.routers.generation.firestore_client"
TEST_UID  = "test-user-uid-123"
TEST_NOTIF_ID = "notif-id-abc123"
```

Sample notification fixture:
```python
SAMPLE_NOTIF = {
    "notification_id": TEST_NOTIF_ID,
    "uid": TEST_UID,
    "type": "complete",
    "title": "Post ready",
    "body": "Your Instagram post is ready to review.",
    "brand_id": "test-brand-id-456",
    "post_id": "test-post-id-789",
    "plan_id": "test-plan-id",
    "day_index": 2,
    "read": False,
    "created_at": datetime.now(UTC).isoformat(),
}
```

---

## 1. Happy Path Tests

### `TestGetUnreadCount`

| # | Test | Input | Expected |
|---|---|---|---|
| 1.1 | Returns unread count for authenticated user | Valid token, `get_unread_count` returns `3` | `200 {"unread_count": 3}` |
| 1.2 | Returns zero when no unread notifications | Valid token, `get_unread_count` returns `0` | `200 {"unread_count": 0}` |

### `TestListNotifications`

| # | Test | Input | Expected |
|---|---|---|---|
| 2.1 | Returns notification list | Valid token, `list_notifications` returns `[SAMPLE_NOTIF]` | `200`, list has 1 item with correct fields |
| 2.2 | Returns empty list when no notifications | Valid token, `list_notifications` returns `[]` | `200 {"notifications": [], "unread_count": 0}` |
| 2.3 | Default limit is 10 | No `limit` param | `list_notifications` called with `limit=10` |
| 2.4 | Custom limit respected up to 50 | `?limit=5` | `list_notifications` called with `limit=5` |
| 2.5 | `unread_count` counts only unread items in list | 3 notifications, 1 read | `unread_count == 2` |

### `TestMarkRead`

| # | Test | Input | Expected |
|---|---|---|---|
| 3.1 | Marks single notification read | Valid token, valid `notification_id` | `200 {"status": "ok", "notification_id": TEST_NOTIF_ID}` |
| 3.2 | Calls firestore with correct uid and id | Valid token | `mark_notification_read` called with `(TEST_UID, TEST_NOTIF_ID)` |

### `TestMarkAllRead`

| # | Test | Input | Expected |
|---|---|---|---|
| 4.1 | Marks all unread as read | Valid token, `mark_all_notifications_read` returns `5` | `200 {"status": "ok", "updated": 5}` |
| 4.2 | Returns zero when nothing to mark | Valid token, returns `0` | `200 {"updated": 0}` |

---

## 2. Edge Cases

### Limit clamping

| # | Test | Input | Expected |
|---|---|---|---|
| 5.1 | Limit clamped to max 50 | `?limit=999` | `list_notifications` called with `limit=50` |
| 5.2 | Negative limit rejected | `?limit=-1` | `list_notifications` called with `limit=1` (clamped to `[1, 50]`) |
| 5.3 | Zero limit rejected | `?limit=0` | `list_notifications` called with `limit=1` |

### Notification fields

| # | Test | Input | Expected |
|---|---|---|---|
| 6.1 | Notification with missing optional fields parsed safely | Doc missing `day_index` and `created_at` | Pydantic uses defaults: `day_index=None`, `created_at=None` |
| 6.2 | `processing` type notification returned correctly | `type="processing"` | Accepted, returned in list |
| 6.3 | `failed` type notification returned correctly | `type="failed"` | Accepted, returned in list |

### Mark-all with no unread

| # | Test | Input | Expected |
|---|---|---|---|
| 7.1 | Empty batch guard: no Firestore batch committed when 0 unread | `mark_all_notifications_read` with empty collection | Returns `0`, no batch committed |

---

## 3. Error Cases

### Auth failures

| # | Test | Input | Expected |
|---|---|---|---|
| 8.1 | No token on unread-count | No `Authorization` header | `401 "Authentication required"` |
| 8.2 | No token on list | No `Authorization` header | `401 "Authentication required"` |
| 8.3 | No token on mark-read | No `Authorization` header | `401 "Authentication required"` |
| 8.4 | No token on mark-all-read | No `Authorization` header | `401 "Authentication required"` |

### Not-found

| # | Test | Input | Expected |
|---|---|---|---|
| 9.1 | Mark non-existent notification | `mark_notification_read` raises `google.api_core.exceptions.NotFound` | `404 "Notification not found"` |
| 9.2 | Other Firestore error on mark-read | `mark_notification_read` raises generic `Exception` | `500` (not 404) |

### Route ordering (no path conflict)

| # | Test | Input | Expected |
|---|---|---|---|
| 10.1 | `unread-count` not matched as `{notification_id}` | `GET /api/notifications/unread-count` with valid token | `200 {"unread_count": N}` — not a 404 or path-param hit |
| 10.2 | `read-all` not matched as `{notification_id}/read` | `POST /api/notifications/read-all` | `200` — correct endpoint invoked |

---

## 4. Firestore Client Unit Tests

### `TestCreateNotification`

| # | Test | Expected |
|---|---|---|
| 11.1 | Returns a UUID string | `isinstance(result, str)` and `len(result) == 36` |
| 11.2 | Written doc includes `read=False` and `created_at` | Verify `set()` called with correct payload |
| 11.3 | Written doc path is `users/{uid}/notifications/{id}` | Verify collection chain |

### `TestGetUnreadCountFirestore`

| # | Test | Expected |
|---|---|---|
| 12.1 | Returns 0 when no unread docs | Empty query result → `0` |
| 12.2 | Returns correct count | 3 docs returned → `3` |

### `TestMarkAllNotificationsRead`

| # | Test | Expected |
|---|---|---|
| 13.1 | Returns 0 and skips batch when no unread | Early return, `batch.commit` not called |
| 13.2 | Commits batch for each unread doc | 3 unread → `batch.update` called 3 times, `batch.commit` called once |

---

## 5. Generation Hook Tests

### `TestNotificationHookOnComplete`

| # | Test | Setup | Expected |
|---|---|---|---|
| 14.1 | Notification created when post completes | Mock `create_notification`, trigger complete event | `create_notification` called with `type="complete"`, correct `brand_id`, `post_id`, `plan_id`, `day_index` |
| 14.2 | No notification for unclaimed brand | `brand.owner_uid = None` | `create_notification` NOT called |
| 14.3 | Notification failure doesn't break SSE | `create_notification` raises `Exception` | SSE stream completes normally, warning logged |

### `TestNotificationHookOnError`

| # | Test | Setup | Expected |
|---|---|---|---|
| 15.1 | Notification created when post fails | Mock `create_notification`, trigger error event | Called with `type="failed"`, correct fields |
| 15.2 | Notification failure on error event doesn't break SSE | `create_notification` raises `Exception` | SSE stream completes, warning logged |

---

## 6. Integration Points

| Dependency | Mock approach |
|---|---|
| `backend.routers.notifications.firestore_client` | `patch(_NOTIF_FC)` with `AsyncMock` per function |
| `backend.middleware.firebase_auth` | `mock_verify_token` fixture from `conftest.py` |
| `google.api_core.exceptions.NotFound` | Import and raise in `mark_notification_read` side_effect |
| Generation hooks | Patch `backend.routers.generation.firestore_client.create_notification` as `AsyncMock` |

---

## 7. Regression Risk

### Existing tests likely affected

| File | Risk | Why |
|---|---|---|
| `test_generation.py` | Low | `mock_firestore` fixture doesn't include `create_notification` — tests that exercise the complete/error event path in `_run_generation_task` may fail if the mock doesn't stub `create_notification` |
| `test_firestore_client.py` | Low | New functions added to module; existing tests unaffected but coverage gap if new functions not tested |
| `test_middleware.py` | None | Auth middleware unchanged |

### Action required
- Add `create_notification = AsyncMock()` to the `mock_firestore` fixture in `conftest.py` so existing generation tests don't fail when the hook fires.

### Coverage gaps exposed
- `backend/routers/notifications.py` — 0% coverage until `test_notifications.py` is created (flagged by architect review)
- The 30-day TTL and Firestore composite index are infrastructure-level — not testable in unit tests; verify manually post-deploy via GCP console
