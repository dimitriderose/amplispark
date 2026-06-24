# Storage Strategy Decision — Issue #12

## Decision

**Keep the current hybrid architecture: GCS for binary assets + Firestore for metadata.**

No migration. Each store is doing what it's good at.

| Store | What goes there |
|---|---|
| GCS (private bucket) | Binary assets: images, videos, brand logos, BYOP photos |
| Firestore | Post metadata, captions, hashtags, status, `gs://` URIs (permanent pointers to GCS) |

---

## Answers to Research Questions

**1. Expected volume of images and videos per brand per month?**
Current target: < 100 brands, ~50 assets/brand/month. GCS and Firestore handle this trivially.

**2. Do assets need to be publicly accessible?**
No — auth-gated only. Signed URLs or backend proxy, never public bucket.

**3. Retention policy — do we delete old assets?**
No deletion today. Assets are permanent. Revisit if storage costs become significant.

**4. Are signed URL expirations causing issues?**
Yes — BYOP calendar photos were stored as signed URLs in Firestore (7-day TTL), breaking the calendar view for photos older than a week. **Fixed in this PR** (see below).

**5. Is Firestore the right choice for post metadata at scale?**
Yes at current scale. Firestore handles filtering by platform, status, and date range via compound queries. Revisit Cloud SQL / AlloyDB if query complexity grows significantly beyond the current read patterns.

**6. Should videos be transcoded before storage?**
Not now. Veo 3.1 outputs MP4 compatible with all target platforms. Revisit if we add browser-based playback that needs HLS/DASH, or if storage costs from large MP4s become significant.

---

## URL Expiry: Refresh-on-Read

Signed URLs are generated fresh on every API read — never stored in Firestore.

| Area | Status |
|---|---|
| Post images | `_refresh_signed_urls()` in `backend/routers/posts.py` — no expiry |
| Video clips | Re-signed at query time in `backend/routers/media.py` — no expiry |
| Brand assets | Stored as `gs://` only, re-signed on read — no expiry |
| BYOP calendar photos | **Fixed in this PR** — now refresh-on-read via `_refresh_plan_photo_urls()` |

**Signed URL TTL:** 7 days (unchanged). Frontend uses a custom `useFetch` hook with no client-side URL caching — signed URLs are never stored in localStorage/sessionStorage and are fetched fresh from the API on every page load. The 7-day TTL provides ample buffer.

**Migration:** `scripts/migrate_byop_urls.py` removes stale `custom_photo_url` fields from existing Firestore plan documents. Run once after deploying this PR.

---

## CDN: Not Now

Private GCS + Cloud CDN is the right architecture for scale but is not needed yet.

When to revisit: **1,000+ brands** or when GCS egress costs become visible in billing.

When you do implement it, the correct pattern is:
- Keep the GCS bucket **private**
- Add a Cloud Load Balancer + backend bucket in front of it
- Enable Cloud CDN on the backend bucket — CDN fetches from GCS using the Cloud Run service account IAM permissions, not public access
- Users receive **CDN-signed URLs** (not GCS-signed URLs) with configurable long TTLs
- Required Terraform: `google_compute_backend_bucket`, `google_compute_url_map`, `google_compute_global_forwarding_rule`

Do NOT make the bucket public — this removes auth gating without any access control benefit.

---

## Concurrency Rate Limiting

Without guards, carousel posts (up to 7 Gemini image calls each) with 10+ concurrent users exceed Gemini's ~360 RPM limit, causing 429 errors and silent carousel failures. Veo has even lower tolerance (~2–3 concurrent jobs per API key).

**Fix shipped in this PR:**

| Limit | Semaphore | File |
|---|---|---|
| Gemini image API | `Semaphore(4)` global | `backend/services/rate_limiter.py` |
| Veo video API | `Semaphore(2)` global | `backend/services/rate_limiter.py` |

These are **in-process semaphores** — they cap concurrent API calls across all users on a single Cloud Run instance. Safe up to ~20 concurrent users.

**Important constraint:** Keep `max_instance_count = 1` in `terraform/main.tf` while these semaphores are in place. In-process semaphores break under horizontal scaling (each instance gets its own semaphore, doubling or tripling the effective concurrency limit).

**Monitoring:** Semaphore wait times > 100ms are logged at INFO level (`rate_limiter: gemini_image waited X ms`). Watch for sustained high wait times as a signal that the Cloud Tasks migration is needed.

---

## When to Migrate to Cloud Tasks

Open a new issue when **any** of these conditions are met:

1. You enable horizontal scaling (`max_instance_count > 1`) on Cloud Run
2. You consistently see semaphore wait times > 500ms p99
3. Concurrent user count regularly exceeds 20

**Cloud Tasks migration scope:**
- Replace in-process semaphores with a Cloud Tasks queue (4 tasks/second globally = ~240 RPM, enforced across all instances)
- Generation endpoints return HTTP 202 + job ID; frontend polls `GET /generation-jobs/{id}`
- Loses live SSE streaming UX — evaluate whether background generation is acceptable at that scale
- Estimated effort: 26–32 hours
