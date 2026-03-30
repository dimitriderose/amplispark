# Amplispark — Buffer + Notion Integrations

## Implementation Status

| Integration | Status | Notes |
|---|---|---|
| **Notion OAuth + Export** | **Shipped (v1.4)** | Full OAuth 2.0 flow, database selection, bulk export. See `backend/services/notion_client.py`, endpoints in `server.py`. |
| **.ics Calendar Download** | **Shipped (v1.4)** | `GET /api/brands/{id}/plans/{pid}/calendar.ics` — download iCalendar file with all posts as events. |
| **.ics Calendar Email** | **Shipped (v1.4)** | `POST /api/brands/{id}/plans/{pid}/calendar/email` — sends .ics via Resend with inline "Add to Calendar" prompt. |
| **Buffer** | **Pending** | Buffer's new API is in closed beta — not accepting new developer applications. Design is ready below; will wire up once API access is granted. |

---

## Context

After generating and approving posts, users currently can only export via ZIP or clipboard copy. There's no way to push content to a scheduling tool or content calendar. Adding **Buffer** (for scheduling/publishing to social platforms) and **Notion** (for exporting a structured content calendar) gives users a seamless path from AI-generated content to actual publishing.

**Buffer** = "Publish" path. Approved posts get sent to Buffer, which handles actual social media scheduling.
**Notion** = "Content Calendar" path. The full plan exports as a structured database with platform, day, caption, hashtags, image URL, status.

---

## PM Assessment

### Buffer
- **New GraphQL API** at `https://api.buffer.com` with Bearer token auth
- Supports 10 platforms: Instagram, LinkedIn, X, Facebook, TikTok, Threads, YouTube, Pinterest, Mastodon, Bluesky
- Post creation with media (image URLs), scheduling, channel selection
- Rate limit: 60 req/user/min (fine for our 7-day plans)
- **Risk:** API is in early access, docs are thin. GraphQL mutation schema is inferred — may need adjustment once we have real API access. Design it now, wire up later.

### Notion
- **REST API** at `https://api.notion.com/v1`
- **OAuth 2.0 public integration** — real "Connect with Notion" button, user picks which databases to share via Notion's page picker. No token pasting.
  - Authorize URL: `https://api.notion.com/v1/oauth/authorize`
  - Token exchange: `https://api.notion.com/v1/oauth/token` (Basic auth with client_id:client_secret)
  - Returns `access_token` + `refresh_token` + workspace metadata
  - Requires registering a **public integration** at notion.so/my-integrations with a redirect URI
- Rich property types: title, rich_text, select, date, url, files, checkbox, number
- Well-documented, stable

### Auth Approach
- **Buffer:** Token-paste only. Buffer no longer accepts new OAuth app registrations. New GraphQL API uses Bearer tokens. User gets token from Buffer Developer Portal and pastes it.
- **Notion:** OAuth 2.0 redirect flow. User clicks "Connect with Notion" → authorizes in Notion → redirected back. Database access granted through Notion's built-in page picker.
- Backend proxies all calls (tokens never exposed to frontend)
- Optional — don't break existing export flow

Sources:
- [Buffer Developer API](https://buffer.com/developer-api)
- [Buffer API Rebuild Blog](https://buffer.com/resources/rebuilding-buffers-api/)
- [Buffer Getting Started](https://developers.buffer.com/guides/getting-started.html)
- [Buffer OAuth (legacy — no new apps)](https://buffer.com/developers/api/oauth)
- [Notion Authorization (OAuth 2.0)](https://developers.notion.com/docs/authorization)
- [Notion Authentication Reference](https://developers.notion.com/reference/authentication)
- [Notion Create Page API](https://developers.notion.com/reference/post-page)
- [Notion Working with Databases](https://developers.notion.com/docs/working-with-databases)

---

## Data Model Changes

### BrandProfile — new `integrations` field (Firestore `brands/{brand_id}`)

```python
integrations: {
    "buffer": {
        "access_token": "...",
        "connected_at": "...",
        "channels": [
            { "id": "...", "service": "instagram", "name": "My Instagram" }
        ]
    },
    "notion": {
        "access_token": "...",
        "refresh_token": "...",
        "bot_id": "...",
        "workspace_id": "...",
        "workspace_name": "...",
        "connected_at": "...",
        "database_id": "...",
        "database_name": "..."
    }
}
```

### Post — new `publish_status` field (Firestore `brands/{brand_id}/posts/{post_id}`)

```python
publish_status: {
    "buffer": { "status": "published", "buffer_post_id": "...", "published_at": "..." },
    "notion": { "status": "exported", "notion_page_id": "...", "published_at": "..." }
}
```

---

## New Files (4)

| File | Purpose |
|---|---|
| `backend/services/buffer_client.py` | Buffer GraphQL API wrapper — `get_channels()`, `create_post()`, `validate_token()` |
| `backend/services/notion_client.py` | Notion REST API wrapper — `search_databases()`, `create_page()`, `build_post_properties()` |
| `backend/services/email_client.py` | Resend email wrapper — `send_calendar_email()` for .ics delivery |
| `frontend/src/components/IntegrationConnect.tsx` | Buffer + Notion connection cards (mirrors SocialConnect pattern) |

## Modified Files (8)

| File | Changes |
|---|---|
| `backend/models/brand.py` | Add `integrations: dict = {}` to BrandProfile, `integrations: Optional[dict] = None` to BrandProfileUpdate |
| `backend/models/post.py` | Add `publish_status: Optional[dict] = None` to Post |
| `backend/server.py` | Add 12 new endpoints (connect/disconnect/publish/export + Notion OAuth + .ics download + email) |
| `frontend/src/api/client.ts` | Add ~10 new API methods |
| `frontend/src/hooks/useBrandProfile.ts` | Add `integrations` to BrandProfile interface |
| `frontend/src/components/PostCard.tsx` | Add "Send to Buffer" / "Export to Notion" buttons on approved posts |
| `frontend/src/components/PostLibrary.tsx` | Add `integrations` prop, bulk action buttons |
| `frontend/src/pages/DashboardPage.tsx` | Render IntegrationConnect in left column, pass integrations to PostLibrary |

---

## Backend Endpoints (12 new)

### Connection
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/brands/{id}/integrations/buffer/connect` | Validate token, fetch channels, store |
| POST | `/api/brands/{id}/integrations/buffer/disconnect` | Remove buffer integration |
| GET | `/api/brands/{id}/integrations/buffer/channels` | Refresh channel list |
| GET | `/api/brands/{id}/integrations/notion/auth-url` | Return Notion OAuth authorize URL (with state=brand_id) |
| GET | `/api/integrations/notion/callback` | OAuth callback — exchange code for tokens, store on brand |
| POST | `/api/brands/{id}/integrations/notion/disconnect` | Remove notion integration |
| POST | `/api/brands/{id}/integrations/notion/select-database` | Set target database from accessible databases |
| GET | `/api/brands/{id}/integrations/notion/databases` | List databases the integration can access |

### Publish / Export
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/brands/{id}/posts/{pid}/publish/buffer` | Send single post to Buffer (with channel_ids, optional scheduled_at) |
| POST | `/api/brands/{id}/plans/{pid}/export/notion` | Export plan's posts to Notion database |

---

## Notion Database Schema (Content Calendar)

User creates a Notion database with these properties. During OAuth, they share this database with our integration. We provide a template link + schema instructions in the UI.

| Property | Notion Type | Source |
|---|---|---|
| Name | Title | `Day {n} - {Platform} - {Theme}` |
| Platform | Select | `post.platform` |
| Day | Number | `post.day_index + 1` |
| Status | Select | draft / approved / posted |
| Caption | Rich Text | `post.caption` (2000 char limit) |
| Hashtags | Rich Text | Joined with # prefix |
| Image URL | URL | Signed GCS URL |
| Posting Time | Rich Text | `post.posting_time` |
| Content Type | Select | photo / carousel / story / reel |

Full caption is also included as page body (paragraph blocks) for readability inside Notion.

---

## User Flows

### Buffer: Connect -> Publish
1. Dashboard left column -> "Publish & Export Integrations" -> click Connect on Buffer card
2. Paste Buffer API token -> "Connect Buffer"
3. Backend validates, fetches channels -> card shows connected channels as tags
4. On approved posts, "Send to Buffer" button appears
5. Click -> pick channels -> send. Backend generates signed image URL, creates Buffer post via GraphQL
6. Post card shows "Sent to Buffer" badge

### Notion: Connect (OAuth) -> Export
1. Dashboard left column -> "Publish & Export Integrations" -> click "Connect with Notion"
2. Browser redirects to Notion's OAuth page -> user logs in, picks pages/databases to share
3. Notion redirects back to `/api/integrations/notion/callback?code=...&state=brand_id`
4. Backend exchanges code for access_token + refresh_token, stores on brand profile
5. Card shows "Connected to {workspace_name}" with database dropdown
6. User selects target database -> "Export to Notion" button appears on approved posts
7. Bulk "Export All to Notion" in PostLibrary header sends all approved posts
8. Each post becomes a database row with structured properties + full caption body

---

## Error Handling
- **Buffer invalid token:** HTTP 400 with clear message, inline error in card
- **Notion OAuth denied:** User clicks "Cancel" on Notion's auth page → redirect back with `error=access_denied` → show "Connection cancelled" message
- **Notion token refresh:** If access_token expires (401), auto-refresh using stored refresh_token. If refresh fails, show "Please reconnect Notion."
- **Rate limit (429):** "Rate limited by {service}. Try again in a minute."
- **Token expired (401/403):** Buffer: "Token expired. Please reconnect." Notion: auto-refresh first, reconnect prompt only if refresh fails.
- **Bulk failures:** Return per-post results `[{post_id, status, error}]`, UI shows summary: "Published 5 of 7"
- **Image URLs:** Use short-lived signed GCS URLs. If signing fails (local dev), skip image with warning.

---

## Implementation Sequence

### Phase 1: .ics Calendar — Download + Email ✅ SHIPPED
1. ~~.ics generation helper in `server.py` (build VCALENDAR string from plan + posts)~~
2. ~~`GET .../calendar.ics` download endpoint + `downloadCalendar()` in `client.ts`~~
3. ~~Email client service (`email_client.py` — Resend) + `POST .../calendar/email` endpoint + `emailCalendar()` in `client.ts`~~
4. ~~"Download Calendar" + "Email Calendar" buttons in PostLibrary~~

### Phase 2: Notion Integration (OAuth) ✅ SHIPPED
5. ~~`backend/services/notion_client.py` — validate, search databases, create page~~
6. ~~Data model updates (`brand.py` — integrations field, `post.py` — publish_status)~~
7. ~~Notion OAuth endpoints: auth-url, callback, disconnect, databases, select-database~~
8. ~~Notion export endpoint: `POST .../export/notion`~~
9. ~~Frontend: Notion card in `IntegrationConnect.tsx`, render in DashboardPage~~
10. ~~Frontend: "Export to Notion" buttons on PostCard + bulk export in PostLibrary~~

### Phase 3: Buffer Integration (pending API access)
11. `backend/services/buffer_client.py` — validate token, get channels, create post
12. Buffer endpoints: connect, disconnect, channels, publish
13. Frontend: Buffer card in `IntegrationConnect.tsx` (token-paste)
14. Frontend: "Send to Buffer" button on PostCard

Phase 1 + Phase 2 = shipped in v1.4. Phase 3 = Buffer API is in closed beta — design is ready, will wire up once API access is granted.

---

## .ics Calendar — Download + Email

### Context
Users want to import their content plan into Google Calendar, Apple Calendar, or Outlook. An `.ics` (iCalendar) file is the universal format all calendar apps support. Each post becomes a calendar event with the caption as the description.

Two delivery methods:
- **Download** — browser downloads `.ics` file, user opens it manually
- **Email** — send `.ics` as a `text/calendar` attachment via Resend. Gmail/Apple Mail show an inline "Add to Calendar" prompt — zero friction.

### Backend

#### New file: `backend/services/email_client.py`
Thin wrapper around the Resend Python SDK for sending calendar invite emails.

```python
import resend
import os

resend.api_key = os.environ.get("RESEND_API_KEY", "")

async def send_calendar_email(to_email: str, brand_name: str, ics_content: str):
    """Send a content plan .ics file as a calendar invite email."""
    resend.Emails.send({
        "from": "Amplispark <onboarding@resend.dev>",
        "to": to_email,
        "subject": f"Your {brand_name} Content Calendar — Amplispark",
        "html": (
            f"<p>Hi! Your 7-day content plan for <strong>{brand_name}</strong> "
            "is attached as a calendar file.</p>"
            "<p>Open the attachment or click 'Add to Calendar' to import all "
            "your posting events.</p>"
            "<p>— Amplispark</p>"
        ),
        "attachments": [{
            "filename": "amplifi_content_plan.ics",
            "content_type": "text/calendar; method=REQUEST; charset=utf-8",
            "content": ics_content,
        }],
    })
```

#### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/brands/{id}/plans/{pid}/calendar.ics` | Download content plan as .ics file |
| POST | `/api/brands/{id}/plans/{pid}/calendar/email` | Email .ics to user as calendar invite |

**File:** `backend/server.py` — two new endpoints

**Download endpoint behavior:**
1. Fetch plan days + all posts for the plan
2. For each post, create a VEVENT with:
   - `SUMMARY`: `{Platform} - {Theme/Pillar}` (e.g. "Instagram - Educate")
   - `DESCRIPTION`: Full caption + hashtags
   - `DTSTART`/`DTEND`: Parse `posting_time` from day brief (e.g. "9:00 AM") combined with the plan's date. If no date, use day_index offset from plan creation date. 30-min duration.
   - `CATEGORIES`: Platform name
   - `URL`: Image URL (if available)
3. Return as `text/calendar` with `Content-Disposition: attachment; filename=amplifi_content_plan.ics`

**Email endpoint behavior:**
1. Build the same `.ics` content as download
2. Accept `{ "email": "user@example.com" }` in request body
3. Send via Resend with `text/calendar; method=REQUEST` content type so email clients show inline "Add to Calendar"
4. Return `{ "status": "sent", "to": email }`

### .ics Format (RFC 5545)

```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Amplispark//Content Plan//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:post_{post_id}@amplifi
DTSTART:20260301T090000
DTEND:20260301T093000
SUMMARY:Instagram - Educate
DESCRIPTION:Your full caption text here\n\n#hashtag1 #hashtag2
CATEGORIES:instagram
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
```

No external Python packages needed for .ics generation — it's plain text built with string formatting. `resend` package needed only for the email endpoint.

### Frontend

**File:** `frontend/src/components/PostLibrary.tsx` — add "Download Calendar" and "Email Calendar" buttons next to "Export All"

```
api.downloadCalendar(brandId, planId)                    // triggers .ics file download
api.emailCalendar(brandId, planId, 'user@example.com')   // emails .ics to user
```

**File:** `frontend/src/api/client.ts` — two new methods:
```typescript
downloadCalendar: (brandId: string, planId: string) =>
  fetch(`/api/brands/${brandId}/plans/${planId}/calendar.ics`)
    .then(async r => {
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'amplifi_content_plan.ics'
      a.click()
      URL.revokeObjectURL(url)
    }),

emailCalendar: (brandId: string, planId: string, email: string) =>
  request(`/api/brands/${brandId}/plans/${planId}/calendar/email`, {
    method: 'POST',
    body: JSON.stringify({ email }),
  }),
```

**UI:** "Email Calendar" button opens a small inline input for the email address + send button. On success, show "Sent to user@example.com" confirmation.

### User Flows

**Download:**
1. User has a generated plan with posts
2. In the Export tab, clicks "Download Calendar"
3. Browser downloads `amplifi_content_plan.ics`
4. User opens file -> calendar app imports all posting events

**Email:**
1. User clicks "Email Calendar" -> enters email address -> clicks Send
2. Backend builds .ics, sends via Resend with `text/calendar` content type
3. User receives email -> Gmail/Apple Mail shows "Add to Calendar" inline -> one click to import

---

## Verification
1. Connect Buffer with test token -> channels appear
2. Click "Connect with Notion" -> redirected to Notion -> authorize -> redirected back -> databases listed, select one
3. Approve a post -> "Send to Buffer" and "Export to Notion" buttons visible
4. Send to Buffer -> post appears in Buffer queue with image
5. Export to Notion -> row appears in database with all properties populated
6. Bulk export plan -> all approved posts appear in Notion
7. Download .ics -> opens in Google Calendar / Apple Calendar with correct dates, times, and captions
8. Email .ics -> arrives in inbox with inline "Add to Calendar" prompt (Gmail), calendar attachment (Outlook/Apple Mail)

---

## Environment Variables (new)
- `NOTION_CLIENT_ID` — from Notion public integration settings
- `NOTION_CLIENT_SECRET` — from Notion public integration settings
- `NOTION_REDIRECT_URI` — e.g. `http://localhost:5173/auth/notion/callback` (dev) or production URL
- `RESEND_API_KEY` — from [resend.com](https://resend.com) dashboard → API Keys

## Dependencies
- **New Python package:** `resend` (for email calendar delivery)
- `httpx` already in requirements.txt
- No new npm packages needed
- **Notion setup required:** Register a public integration at [notion.so/my-integrations](https://notion.so/my-integrations)
- **Resend setup required:** Create free account at [resend.com](https://resend.com), copy API key (free tier: 3,000 emails/mo)
