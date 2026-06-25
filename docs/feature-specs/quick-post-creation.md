# Plan: Ad-Hoc Post Creation + Composer-First Rearchitecture (Issue #13)

## Branch

`feature/quick-post-creation-issue-13` (branch off `main`)

---

## Context

Issue #13 asks for ad-hoc post creation outside the weekly calendar. PM + Designer review and industry research revealed a deeper problem: Amplispark's calendar-first IA actively penalises users who want one reactive post — they must traverse a full planning surface to reach the generation engine. No major competing tool (Buffer, Later, Hootsuite, Sprout Social) gates users behind a planning flow. They all expose a persistent quick-compose entry point alongside a calendar view.

This plan scopes Issue #13 as a **composer-first rearchitecture**: flip the primary surface to post generation (AI-first), demote the calendar to an opt-in view, and unify all posts (calendar + ad-hoc) in a single "Library" list. The calendar is preserved as a power-user feature, not the entry point.

---

## Target Information Architecture

### Current IA
```
/dashboard/:brandId
  ├── Calendar tab (PRIMARY — entry point, plan required to generate)
  ├── Posts tab
  │   ├── Weekly sub-tab (PostLibrary, planId-filtered)
  │   └── All History sub-tab (PostHistory, all posts)
  ├── Connections tab
  └── Video tab
```

### New IA
```
/dashboard/:brandId
  ├── Create tab (MdOutlineEdit — NEW PRIMARY, default landing tab)
  │   ├── [Quick Post] card → opens QuickPostModal
  │   └── [Weekly Plan] card → switches to Calendar tab
  ├── Library tab (MdGridView — REPLACES Posts tab)
  │   ├── All posts (calendar + ad-hoc) unified, newest first
  │   ├── Search, filter by platform / pillar / status
  │   └── Week grouping + export menu
  ├── Calendar tab (DEMOTED — opt-in planning surface)
  │   └── Unchanged — ContentCalendar, EventsInput, plan generation
  ├── Connections tab (unchanged)
  └── Video tab (unchanged)

Persistent in BrandSummaryBar (all tabs):
  └── [+ Quick Post] button — zero-friction entry from any tab
```

---

## What Changes

### 1. BrandSummaryBar — Add Persistent `+ Quick Post` Button
**File:** `frontend/src/components/BrandSummaryBar.tsx`

Add a primary-styled `+ Quick Post` button to the right side of the bar, alongside the existing Edit Brand / + New Brand buttons. Visible on every tab, always. On click: opens `QuickPostModal`.

This is the single most important change — it gives every user a one-click path to ad-hoc generation regardless of which tab they are on, matching the Buffer/Later/Hootsuite pattern.

---

### 2. Dashboard Tab Reorder + Rename
**File:** `frontend/src/pages/DashboardPage.tsx`

```
Before:  calendar | posts | connections | video
After:   create | content | calendar | connections | video
```

- **Create** (`MdOutlineEdit`) — new primary tab, default on load
- **Library** (`MdGridView`) — replaces "Posts", unified view of all posts
- **Calendar** (`MdOutlineCalendarMonth`) — unchanged, demoted to third
- **Connections** (`MdOutlineElectricPlug`) — unchanged
- **Video** (`MdOutlinePlayCircle`) — unchanged

All icons from `react-icons/md` (Material Design) — consistent weight/style, inherit active/inactive color tokens. Replace the current emoji text characters in the `TABS` array.

---

### 3. New "Create" Tab
**File:** `frontend/src/components/CreateTab.tsx` (extracted, not inline)

Two cards side by side (stacked on mobile):

```
┌─────────────────────────────────────────────────────────────┐
│  What would you like to create?                             │
│                                                             │
│  ┌──────────────────────────┐  ┌──────────────────────────┐ │
│  │  MdOutlineBolt           │  │  MdOutlineCalendarMonth  │ │
│  │  Quick Post              │  │  Weekly Plan             │ │
│  │                          │  │                          │ │
│  │  Generate one post now   │  │  Plan 7 days of content  │ │
│  │  for any topic or idea   │  │  with an AI calendar     │ │
│  │                          │  │                          │ │
│  │  [Create Post]           │  │  [Plan My Week]          │ │
│  └──────────────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

- **[Create Post]** → opens `QuickPostModal`
- **[Plan My Week]** → `setActiveTab('calendar')`

---

### 4. QuickPostModal — New Component
**File:** `frontend/src/components/QuickPostModal.tsx`

A modal with two render phases controlled by generation state.

#### Phase 1 — Composer (default view, `status === 'idle'`)

```
┌──────────────────────────────────────────────────────┐
│  New Post                                        [×] │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Platform                                            │
│  [SiInstagram] [SiLinkedin] [SiX]  ← brand's selected only  │
│   (horizontal scroll on mobile, + more if needed)    │
│                                                      │
│  What do you want to post about?                     │
│  ┌──────────────────────────────────────────────┐    │
│  │  e.g. our new product launch, a behind-the-  │    │
│  │  scenes moment, a client win...              │    │
│  └──────────────────────────────────────────────┘    │
│  The more context you give, the better the result.   │
│                                                      │
│  ▸ Advanced options                                  │
│                                                      │
│  [              Generate Post              ]         │
└──────────────────────────────────────────────────────┘
```

**Advanced options expanded:**

```
│  ▾ Advanced options                                  │
│                                                      │
│  Format  (filtered by selected platform)             │
│  [MdOutlineImage Photo] [MdOutlineViewCarousel Carousel] [MdOutlinePlayCircle Video]  ... │
│   only formats valid for the chosen platform shown   │
│                                                      │
│  [✦ Visual Style: [brand default]           ▾]      │
│   same button + dropdown as ContentCalendar.tsx      │
│                                                      │
│  [ ] Upload your own image                           │
│      ┌────────────────────────────────────────────┐  │
│      │  drag & drop or click to upload            │  │
│      └────────────────────────────────────────────┘  │
```

#### Platform selector behaviour
- Reads `brand.selected_platforms` (set during onboarding / Edit Brand)
- Shows **only the brand's selected platforms**, each rendered with its actual `react-icons/si` icon and brand color from `PLATFORMS[key]` in `platformRegistry.ts`
- First platform pre-selected by default
- Horizontal scroll row on mobile; wraps to two rows on desktop if >5 platforms
- `+ Add platform` link at end opens full platform list for one-off selection

#### Format selector behaviour — `PLATFORM_FORMATS` constant (new)
Format chips appear **only in Advanced options** and are filtered dynamically by whichever platform is selected. Derived from the strategy agent's existing platform guidance:

```typescript
// frontend/src/constants/platformFormats.ts  (new file)
export const PLATFORM_FORMATS: Record<string, string[]> = {
  instagram:      ['original', 'carousel', 'video_first', 'story'],
  linkedin:       ['original', 'carousel', 'video_first', 'blog_snippet'],
  x:              ['original', 'thread_hook', 'video_first'],
  tiktok:         ['video_first', 'carousel'],
  facebook:       ['original', 'carousel', 'video_first', 'story'],
  threads:        ['original', 'thread_hook'],
  pinterest:      ['pin', 'video_first'],
  youtube_shorts: ['video_first'],   // pre-selected, no other option
  mastodon:       ['original'],      // pre-selected, no other option
  bluesky:        ['original', 'thread_hook'],
}

// Icons from react-icons/md — same library as tab bar icons
export const FORMAT_LABELS: Record<string, { label: string; icon: string }> = {
  original:     { label: 'Photo',        icon: 'MdOutlineImage' },              // simple image frame
  carousel:     { label: 'Carousel',     icon: 'MdOutlineViewCarousel' },       // side-scrolling panels
  video_first:  { label: 'Video',        icon: 'MdOutlinePlayCircle' },         // play = permanent video (Reel/Short/TikTok)
  story:        { label: 'Story',        icon: 'MdOutlineTimer' },              // timer = 24h ephemeral
  thread_hook:  { label: 'Thread',       icon: 'MdOutlineFormatListNumbered' }, // numbered list = threaded posts
  blog_snippet: { label: 'Blog Clip',    icon: 'MdOutlineArticle' },            // document = long-form
  pin:          { label: 'Pin',          icon: 'MdOutlinePushPin' },            // literal pushpin
}
```

Special cases:
- **YouTube Shorts** and **Mastodon**: single valid format, auto-selected, chips not shown (no choice to make)
- **Pinterest**: `pin` pre-selected
- Switching platform resets format to the first valid option for that platform

#### Visual Style selector behaviour
- Reuses `IMAGE_STYLE_GROUPS` and `styleLabel()` from `imageStyleOptions.ts` — same imports as `ContentCalendar.tsx`
- Pre-fills from `brand.default_image_style` (same field the Calendar already uses via `defaultImageStyle` prop)
- Identical `✦ Visual Style: Auto ▾` button appearance and dropdown — zero new design

#### Phase 2 — Generation view (`status !== 'idle'`)
Modal transitions to full-screen. Renders existing `PostGenerator`, `ReviewPanel`, and `EditMediaSection` unchanged. Header subtitle: `New Post · Instagram · Photo` (no "Ad-hoc" label).

On approve: modal closes, toast: "Post saved to Library." User stays on current tab.

**Unsaved changes guard:** Closing modal during `status === 'generating'` shows confirm dialog.

---

### 5. `PLATFORM_FORMATS` constant
**File:** `frontend/src/constants/platformFormats.ts` (new)

Single source of truth for which formats are valid per platform on the frontend. Mirrors the backend strategy agent's platform guidance in `backend/agents/strategy_agent.py`. Both must be kept in sync if platforms or formats change.

---

### 6. "Library" Tab — Replaces "Posts" Tab
**File:** `frontend/src/components/PostHistory.tsx` → extend and rename to `frontend/src/components/Library.tsx`

Extend `PostHistory` (260 lines) rather than `PostLibrary` (494 lines, plan-scoped). Add the export dropdown from `PostLibrary`. Remove `postsSubTab` state from `DashboardPage` entirely.

**Unified view:**
- All posts regardless of plan (calendar + ad-hoc), newest first, week-grouped
- Filters: status / platform / pillar / search (all already in PostHistory)
- Export menu: ZIP, .ics, Notion (ported from PostLibrary)
- Ad-hoc posts: small ⚡ icon overlaid bottom-left of PostCard image (neutral `A.textMuted`, not amber)

---

### 7. Ad-Hoc Post — Backend Changes

**`backend/models/post.py`**
- `plan_id: str` → `plan_id: str | None = None`
- `day_index: int` → `day_index: int | None = None`
- Add `is_quick_post: bool = False`

**`backend/routers/generation.py`**

New SSE endpoint — declared **before** `/generate/{plan_id}/{day_index}`:
```
GET /api/generate/adhoc/{brand_id}
Query: platform (required), content_type (optional), brief (optional),
       image_style (optional), instructions (optional)
```

Builds a synthetic `day_brief` from query params using `PLATFORM_FORMATS` defaults for format. Calls `save_post(brand_id, "adhoc", {..., "is_quick_post": True, "day_index": None})`. Runs identical SSE pipeline as calendar path via extracted `_run_generation_task(...)` helper (shared with existing endpoint).

**`backend/routers/posts.py`**
Patch `regenerate_post`: if `post.get("is_quick_post")`, return URL pointing to ad-hoc endpoint instead of calendar endpoint.

**`backend/services/firestore_client.py`** — no changes. Sentinel `"adhoc"` is a plain string, existing `save_post` signature unchanged.

---

### 8. Frontend Hook — `usePostGeneration.ts`
**File:** `frontend/src/hooks/usePostGeneration.ts`

Extract EventSource setup into shared `setupEventSource(url)` helper. Add:
```typescript
generateAdhoc(brandId, platform, contentType?, brief?, imageStyle?): void
// → GET /api/generate/adhoc/${brandId}?platform=...&content_type=...&brief=...&image_style=...
```

---

### 9. PostCard — Ad-Hoc Visual Treatment
**File:** `frontend/src/components/PostCard.tsx`

- `post.is_quick_post`: render ⚡ overlaid bottom-left of image, `A.textMuted` color
- Remove "Day N" label for ad-hoc posts; show platform label only
- Retry on failed ad-hoc post: open `QuickPostModal` pre-filled via URL param `?quickpost=1&platform=instagram&content_type=original`

---

### 10. Type Updates
**File:** `frontend/src/types/index.ts`
- `plan_id: string` → `plan_id: string | null`
- `day_index: number` → `day_index: number | null`
- Add `is_quick_post?: boolean`

---

### 11. No New Route
The ad-hoc flow lives entirely in `QuickPostModal`. Deep-link / retry re-opens the modal via dashboard URL params: `/dashboard/:brandId?quickpost=1&platform=instagram`.

---

## Implementation Order

1. `backend/models/post.py` — optional fields + `is_quick_post`
2. `backend/routers/generation.py` — extract `_run_generation_task`, add ad-hoc SSE endpoint
3. `backend/routers/posts.py` — patch regenerate for ad-hoc posts
4. `frontend/src/types/index.ts` — Post interface updates
5. `frontend/src/constants/platformFormats.ts` — new `PLATFORM_FORMATS` + `FORMAT_LABELS`
6. `frontend/src/hooks/usePostGeneration.ts` — add `generateAdhoc()`
7. `frontend/src/components/QuickPostModal.tsx` — new modal (Phase 1 + Phase 2)
8. `frontend/src/components/BrandSummaryBar.tsx` — `+ Quick Post` button
9. `frontend/src/components/Library.tsx` — extend PostHistory + add export menu
10. `frontend/src/components/CreateTab.tsx` — new Create tab component
11. `frontend/src/pages/DashboardPage.tsx` — reorder tabs, wire CreateTab, MyContent, QuickPostModal, URL param handler
12. `frontend/src/components/PostCard.tsx` — ⚡ overlay + ad-hoc retry

---

## QuickPostModal → Backend: Data Flow

```
QuickPostModal (Phase 1 form)
        │  user clicks Generate
        ▼
usePostGeneration.generateAdhoc()
        │  opens EventSource (same mechanism as calendar generation)
        ▼
GET /api/generate/adhoc/{brandId}
    ?platform=instagram&content_type=carousel&brief=...&image_style=...
        │
        ├── fetch brand from Firestore (30s cache)
        ├── build synthetic day_brief from query params
        ├── save post (status=generating, plan_id="adhoc", is_quick_post=True)
        └── run generate_post() agent (shared with calendar path)
                │
                ├── SSE: status → caption chunks → image → complete
                ▼
QuickPostModal (Phase 2 generation view)
        │  PostGenerator renders streaming events (zero new component work)
        │  ReviewPanel shows AI score
        │  user clicks Approve
        ▼
POST /api/brands/{brandId}/posts/{postId}/approve
        │
        ▼
modal closes → toast "Post saved to Library" → post appears in Library tab
```

**Key insight:** No new plumbing. The modal reuses the SSE hook, `PostGenerator`, `ReviewPanel`, and the approve endpoint. The only net-new piece is `/api/generate/adhoc/` which constructs a `day_brief` from query params instead of a plan day.

---

## Out of Scope
- Scheduling / publishing to social platforms
- Tone/voice override per post
- Date picker ("when is this for?") — post-MVP
- Bulk ad-hoc generation
- URL persistence for sub-tab state — pre-existing gap, separate ticket

---

## Verification

1. **Backend tests:** `.\backend\.venv\Scripts\python -m pytest backend/tests/ -v --tb=short` — no regressions
2. **Ad-hoc SSE smoke test:** `GET /api/generate/adhoc/{brand_id}?platform=instagram&brief=hello` via Swagger — stream opens, post created in Firestore with `is_quick_post=true`, `plan_id="adhoc"`
3. **Platform pre-fill:** Open modal → verify only brand's `selected_platforms` appear, first one pre-selected with correct `react-icons/si` icon and brand color
4. **Format filtering:** Select Pinterest → only `Pin` and `Video` shown in Advanced options. Select YouTube Shorts → `Video` auto-selected, no chips shown. Select Instagram → Photo, Carousel, Video, Story available
5. **Visual Style pre-fill:** Verify picker pre-fills from `brand.default_image_style`, dropdown matches Calendar's exactly
6. **Generation flow:** Enter brief → Generate → caption streams → image loads → ReviewPanel → Approve → toast "Post saved to Library" → modal closes
7. **Library tab:** Calendar posts + new ad-hoc post appear together, newest first, week-grouped. ⚡ on ad-hoc cards only
8. **Calendar tab unchanged:** Plan generation, day Generate buttons, existing posts all work
9. **Persistent button:** `+ Quick Post` visible on all tabs (Create, Library, Calendar, Connections, Video)
10. **Mobile:** Platform chips scroll horizontally, modal full-screen, Create tab cards stack vertically, format chips wrap
11. **Retry failed ad-hoc:** Failed ad-hoc PostCard retry → modal opens with platform pre-filled
