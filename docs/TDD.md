# Technical Design Document
## Amplispark

**Category:** ✍️ Creative Storyteller
**Author:** Software Architecture Team
**Companion Document:** PRD — Amplispark v1.5
**Version:** 1.9 | March 31, 2026 (updated from v1.8 — structured JSON logging, security hardening, Firestore-backed budget tracker, carousel optimization, test infrastructure, soft deletes, auth improvements)

---

# 1. Overview

This Technical Design Document specifies the implementation architecture for Amplispark, an AI-powered creative director that produces complete social media content packages using Gemini's interleaved text and image output. It translates the PRD's product requirements into concrete engineering decisions, API contracts, data models, code structure, and deployment specifications.

**Scope:** All P0 and P1 features from the PRD, plus shipped P2 features: brand analysis from URL (with deterministic analysis at temperature 0.15), content calendar generation with event integration and social proof tier system, interleaved post generation with carousel support, image fallback, video_first pipeline, and brand reference image injection, multiplicative two-step review scoring with platform-specific weights (15 profiles: 11 platforms + 4 derivative overrides), React dashboard with tab-based navigation and Edit Brand page, image/video storage, streaming UI, Firebase Google Sign-In with account dropdown and Firebase ID token verification middleware, dedicated Brands page with pagination (5 per page), tier-aware Gemini Live voice coaching with content calendar context, Veo 3.1 video generation, full ZIP export with media, Platform Registry (11 platforms), Notion integration (OAuth + Fernet-encrypted tokens + database export), calendar .ics export with email delivery, platform-specific caption/hashtag enforcement, Cloud Build CI/CD pipeline with `deploy.sh`, SPA catch-all routing for deep links on Cloud Run with path traversal prevention, AI-researched posting frequency with Google Search grounding, multi-platform calendar generation with brief_index/day_index separation, modular backend architecture (7 FastAPI routers, 5 content creator sub-modules, shared constants/clients/middleware), centralized frontend type system with generic hooks, 3-step onboarding wizard with deferred brand creation and sessionStorage persistence, 11-step SVG-based guided tour with per-brand completion tracking, structured JSON logging with request context propagation, global exception handler, HMAC-signed OAuth state, Firestore-persisted budget tracker, 7-slide concurrent carousel generation, bounded SSE queues, soft deletes for posts, ProtectedRoute auth wrapper, pytest test infrastructure (35 tests) with CI integration, and double-click protection across generation flows.

**Out of scope (unspecified):** Post analytics dashboard (P3). Remaining P2 features are specified in §14.1. P3 features are additive and do not affect core architecture.

---

# 2. System Architecture

## 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       USER BROWSER                              │
│                                                                 │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │          React 19 Dashboard + Firebase Anon Auth          │ │
│   │                                                           │ │
│   │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐  │ │
│   │  │  Brand    │  │  Dashboard │  │   Post Generator     │  │ │
│   │  │  Wizard   │  │  Tabs:     │  │   (SSE streaming)    │  │ │
│   │  │          │  │ Calendar   │  │                      │  │ │
│   │  │ URL input │  │ Posts      │  │ Caption ──────────── │  │ │
│   │  │ Upload    │  │ Export     │  │ Image / Carousel     │  │ │
│   │  │ Describe  │  │            │  │ Hashtags ──────────  │  │ │
│   │  └──────────┘  └────────────┘  └──────────────────────┘  │ │
│   └────────────────────────┬──────────────────────────────────┘ │
│                            │ REST + SSE                         │
└────────────────────────────┼────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUD RUN (us-central1)                       │
│                    Container: amplifi-backend                    │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                 FastAPI Application Server                 │  │
│  │                                                           │  │
│  │  POST   /api/brands             → Create brand (+ owner_uid) │  │
│  │  GET    /api/brands?owner_uid= → List user's brands        │  │
│  │  PATCH  /api/brands/{id}/claim → Grandfather brand to UID  │  │
│  │  POST   /api/brands/{id}/analyze → Brand analysis (t=0.15)│  │
│  │  POST   /api/plans             → Generate content calendar │  │
│  │  GET    /api/generate/{planId}/{day} → SSE: generate post  │  │
│  │  GET    /api/posts/{id}/export → ZIP: image+video+caption  │  │
│  │  POST   /api/export/{planId}   → ZIP: bulk plan export     │  │
│  │  PATCH  /api/posts/{id}/approve → Toggle approval          │  │
│  │  GET    /health                → Health check              │  │
│  └──────────────┬────────────────────────────────────────────┘  │
│                 │                                                │
│  ┌──────────────▼────────────────────────────────────────────┐  │
│  │           ADK SequentialAgent Pipeline                     │  │
│  │                                                           │  │
│  │   Step 1          Step 2          Step 3         Step 4   │  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐  ┌────────┐ │  │
│  │  │  Brand   │──▶│ Strategy │──▶│ Content  │─▶│ Review │ │  │
│  │  │ Analyst  │   │  Agent   │   │ Creator  │  │ Agent  │ │  │
│  │  │          │   │          │   │ ⭐        │  │        │ │  │
│  │  │ gemini-  │   │ gemini-  │   │ gemini-  │  │gemini- │ │  │
│  │  │ 3-flash- │   │ 3-flash- │   │ 3-flash- │  │3-flash-│ │  │
│  │  │ preview  │   │ preview  │   │ prev+img │  │preview │ │  │
│  │  └──────────┘   └──────────┘   └──────────┘  └────────┘ │  │
│  └──────────────┬────────────────────────────────────────────┘  │
│                 │                                                │
│  ┌──────────────▼────────────────────────────────────────────┐  │
│  │         Gemini API (generateContent)                       │  │
│  │         Text model: gemini-3-flash-preview                  │  │
│  │         Image model: gemini-3.1-flash-image-preview         │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────┬───────────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐  ┌──────────────────────────────────┐
│    Cloud Firestore       │  │       Cloud Storage               │
│    (us-east1)            │  │       (us-east1)                  │
│                          │  │                                   │
│  brands/{brandId}/       │  │  gs://amplifi-assets-2026/        │
│    business_name, tone,  │  │    brands/{brandId}/              │
│    colors, audience      │  │      logo.png                    │
│    content_plans/        │  │      product_photos/              │
│      {planId}/days/      │  │    generated/{postId}/            │
│        {day}/            │  │      image.png                   │
│          caption, image  │  │                                   │
└──────────────────────────┘  └──────────────────────────────────┘
```

## 2.2 Key Architectural Decisions

**Decision 1: REST + SSE (Not WebSocket)**
Unlike Fireside which requires bidirectional real-time communication, Amplispark uses standard REST APIs for all CRUD operations and Server-Sent Events (SSE) for the content generation stream. The frontend opens an SSE connection to `/api/generate/{planId}/{day}` and receives interleaved text and image data as the model produces it.

Rationale: Interleaved output uses the standard `generateContent` API (not Live API). SSE is the natural fit for a unidirectional server-to-client stream. It's simpler than WebSocket, doesn't require session affinity on Cloud Run, and works through CDNs and proxies.

**Decision 2: Per-Day Content Generation (Not Batch)**
The Content Creator Agent is invoked once per calendar day, producing one post per API call. A 7-day calendar requires 7 sequential calls.

Rationale: Each interleaved output call generates text + image in one response. Generating all 7 posts in one call would make the response too large and the UI would have to wait for the entire response before showing anything. Per-day calls allow progressive display: Day 1 streams in, then Day 2, etc.

**Decision 3: Image Storage in Cloud Storage with Backend Proxy**
Generated images are extracted from the Gemini response, uploaded to Cloud Storage. The `gs://` URI is stored in Firestore. Images are served to the frontend via a backend proxy endpoint (`/api/storage/serve/{blob_path}`) rather than signed URLs, because Application Default Credentials (ADC) in local dev lack the private key needed for URL signing.

Rationale: Base64 images in Firestore would quickly exceed document size limits (1 MiB). Cloud Storage is purpose-built for binary objects. The backend proxy provides a reliable serving path that works identically in local dev and Cloud Run. For export, media is downloaded directly via `blob.download_as_bytes()` — bypassing URL resolution entirely.

**Decision 5: Firebase Google Sign-In for Brand Ownership**
Firebase Google Sign-In via `signInWithPopup` + `GoogleAuthProvider` provides one-click authentication. Brands get an `owner_uid` field linking them to the authenticated Google user. On return, the app queries Firestore for all brands matching the UID and shows them on the dedicated Brands page (`/brands`) with pagination (5 per page). NavBar shows "My Brands" when signed in, "Get Started" when not. Account dropdown displays profile photo and display name.

Rationale: Google Sign-In provides persistent identity with real user profiles (name, photo, email) while remaining low-friction (one click). The dedicated Brands page keeps the landing page clean for marketing/conversion while giving returning users a home for brand management.

**Decision 5a: SPA Catch-All Routing on Cloud Run**
The backend serves the React SPA via a catch-all route handler. All paths not matching `/api/*` or existing static files under `/assets/` are served `index.html`, letting React Router handle client-side routing. This ensures deep links (e.g., `/brands`, `/dashboard/xyz`, `/auth/notion/callback`) work on Cloud Run without 404s.

Rationale: FastAPI's `StaticFiles(html=True)` doesn't serve `index.html` for deep SPA routes. The explicit catch-all route (`@app.get("/{full_path:path}")`) handles all SPA routes while still serving actual static assets.

**Decision 6: Image Fallback on Interleaved Failure**
If the Content Creator's interleaved output produces zero images (text-only response), a separate image-only generation call is made automatically. This is a two-tier fallback: (1) retry with explicit image instruction via `generate_post_fallback()`, (2) if still no image, emit an `IMAGE_GEN_FAILED` error event — caption is still saved.

Rationale: Gemini's interleaved output occasionally produces text-only responses. Rather than failing the entire generation, the fallback ensures the user always gets a caption and usually gets an image.

**Decision 7: Post Deduplication on Regeneration**
When regenerating a day, existing posts for the same `plan_id + day_index` are deleted before creating the new post. This prevents duplicate entries in the post library.

Rationale: Without deduplication, regenerating a day would create a second post alongside the first, confusing the export and library views.

**Decision 4: Review Agent Runs Independently**
The Review Agent is a separate LLM call that receives the generated post content + the brand profile and produces a structured review. It does NOT modify the generated content; it only flags issues and provides suggestions.

Rationale: Keeping generation and review separate allows the user to accept "flagged" posts anyway. It also avoids circular loops where the reviewer rewrites content that then needs re-reviewing.

**Decision 8: Modular Backend Architecture (Router Split + Module Extraction)**
The backend was refactored from two monolithic files (`server.py` at 2,150 lines, `content_creator.py` at 2,518 lines) into a modular architecture:

- **server.py** is now ~65 lines: app setup, middleware wiring, and `app.include_router()` calls for 7 routers.
- **7 FastAPI routers** (`backend/routers/`): `brands.py`, `plans.py`, `posts.py`, `generation.py`, `media.py`, `integrations.py`, `voice.py`. Each router owns its route prefix and endpoint logic.
- **5 content creator sub-modules** (`backend/agents/`): `caption_pipeline.py`, `carousel_builder.py`, `hashtag_engine.py`, `quality_gates.py`, `image_prompt_builder.py`. Extracted from `content_creator.py` for testability and separation of concerns.
- **Shared utilities**: `clients.py` (singleton Gemini client), `gcs_utils.py` (GCS URI parsing), `constants.py` (shared PILLARS, DERIVATIVE_TYPES, PLATFORM_STRENGTHS, PILLAR_DESCRIPTIONS, PILLAR_NARRATIVES, scoring weights), `middleware.py` (Firebase Auth + brand ownership verification).

Rationale: The monolithic files were approaching unmaintainable size. The router split follows FastAPI best practices (one router per domain). Module extraction from `content_creator.py` allows individual testing of caption generation, carousel building, and hashtag processing without invoking the full pipeline.

**Decision 9: Firebase Auth Middleware with Brand Ownership Verification**
All API routes are protected by a middleware chain: (1) `verify_firebase_token()` validates the Firebase ID token from the `Authorization: Bearer` header using `firebase_admin.verify_id_token()`, and (2) `verify_brand_owner()` checks that the authenticated user owns the brand being accessed. Both are wired to routers via FastAPI's `Depends()`.

Rationale: The previous auth model relied on client-side UID passing. Server-side token verification prevents unauthorized access to other users' brands.

**Decision 10: Security Hardening — Token Encryption, HMAC OAuth State, CORS Lockdown**
Notion OAuth access tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256) before storage in Firestore. The encryption key is derived from the application's secret configuration. As of v1.9, token encryption is **mandatory** — the application raises `RuntimeError` on startup if `TOKEN_ENCRYPT_KEY` is not set, preventing accidental plaintext token storage.

**HMAC-signed OAuth state (v1.9):** The Notion OAuth flow now generates an HMAC-SHA256 signature of `brand_id` using the application secret as the `state` parameter. On callback, the server recomputes the HMAC and compares — rejecting any request where the state does not match. This prevents CSRF attacks and ensures the OAuth callback is bound to the originating brand.

**Tightened CORS (v1.9):** The CORS middleware was locked down from `allow_methods=["*"], allow_headers=["*"]` to explicit lists: `allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]` and explicit `allow_headers` (Authorization, Content-Type, etc.). This reduces the attack surface from overly permissive wildcard CORS.

**Error response sanitization (v1.9):** All routers return sanitized error responses that do not leak internal details (stack traces, file paths, database structure). The global exception handler (see §4.2) catches unhandled exceptions and returns a clean `{"detail": "Internal server error"}` JSON response.

Rationale: OAuth tokens stored in plaintext in Firestore would be exposed if the database were compromised. Fernet provides authenticated encryption with a simple API. The mandatory key check, HMAC state validation, explicit CORS, and error sanitization form a defense-in-depth security posture.

**Decision 11: Multiplicative Two-Step Scoring System**
The Review Agent scoring was refactored from a single LLM-decided overall score (prone to inflation) to a two-step computation:

1. **LLM outputs** `engagement_scores` (5 dimensions, 1-10 each) + `structural_issues` (list of violations).
2. **Code computes** `score = content_quality x structural_modifier`, where:
   - `content_quality` = weighted average of engagement scores using platform-specific weights from `platforms.py` (15 profiles: 11 platforms + 4 derivative overrides).
   - `structural_modifier` = penalty factor based on structural issues, with a platform-specific floor (0.60-0.92).

Rationale: Separating subjective quality assessment (LLM) from objective structural checks (code) produces more consistent, reproducible scores. The multiplicative formula ensures structural violations (wrong hashtag count, over character limit) always reduce the score, regardless of how high the LLM rates engagement.

---

# 3. Agent Specifications

## 3.1 Pipeline Architecture (ADK SequentialAgent)

```python
from google.adk.agents import Agent, SequentialAgent

# The full pipeline as an ADK SequentialAgent
amplifi_pipeline = SequentialAgent(
    name="amplifi_pipeline",
    description="Brand analysis → strategy → content creation → review",
    sub_agents=[brand_analyst, strategy_agent, content_creator, review_agent],
)
```

Note: For MVP, the pipeline is invoked step-by-step through REST endpoints rather than as a single SequentialAgent run. This gives the user control between steps (edit brand profile, rearrange calendar). The SequentialAgent definition exists for completeness and could be used for a "one-click generate everything" flow.

## 3.2 Brand Analyst Agent

```python
brand_analyst = Agent(
    name="brand_analyst",
    model="gemini-3-flash-preview",
    description="Analyzes a brand from its website and assets to build a brand profile",
    # Temperature 0.15 for deterministic, consistent analysis across repeated runs
    generation_config=types.GenerateContentConfig(temperature=0.15),
    instruction="""You are a brand strategist analyzing a business to build a
    comprehensive brand profile.

    BUSINESS DESCRIPTION: {business_description}

    Infer the business type and tailor your analysis accordingly:
    - Local/physical businesses: Emphasize product photography direction, local community 
      engagement, seasonal promotions, foot traffic drivers.
    - Service/consulting businesses: Emphasize expertise signaling, trust markers, thought 
      leadership topics, client outcome language.
    - Personal brands/creators: Emphasize personal voice authenticity, opinion-driven content 
      themes, storytelling angles, audience relationship building.
    - E-commerce/DTC: Emphasize product features, seasonal campaigns, UGC-style aesthetics,
      conversion-oriented content themes.
    
    Given a website URL (if provided), free-text business description, and/or uploaded brand 
    assets (images and PDFs like brand guides or menus), extract:
    1. BRAND COLORS: Primary, secondary, and accent colors (hex values)
    2. TONE OF VOICE: Select exactly 3 adjectives from this list:
       professional, friendly, authoritative, playful, warm, bold, minimal, luxurious,
       casual, inspiring, educational, witty, empathetic, confident, sophisticated
    3. TARGET AUDIENCE: Demographics, psychographics, and interests
    4. INDUSTRY & POSITIONING: What category they're in and how they differentiate
    5. CONTENT THEMES: 5-8 recurring topics the brand should post about
       (weighted by business_type — personal brands get thought leadership topics,
        local businesses get community/product topics)
    6. VISUAL STYLE: Select one from: clean-minimal, warm-organic, bold-vibrant,
       dark-luxurious, bright-playful, professional-corporate, rustic-artisan
    7. COMPETITORS: 2-3 direct competitors if identifiable
    8. IMAGE STYLE DIRECTIVE (P1): A 2-3 sentence visual identity fragment that will be
       prepended to EVERY image generation prompt for this brand. Be extremely specific.
       Bad: "professional and clean"
       Good: "warm earth tones with terracotta and sage green accents, soft natural 
       lighting with golden hour warmth, minimalist compositions with generous whitespace, 
       organic textures like linen and raw wood, shot from slightly above at 30-degree angle"
       This directive is the brand's visual DNA — it ensures every AI-generated image
       feels like it belongs to the same feed even when generated in separate API calls.
    9. CAPTION STYLE DIRECTIVE (P1): A 2-4 sentence writing rhythm guide that will be
       prepended to EVERY caption generation prompt for this brand. Describe the structural
       pattern of the brand's writing, not just adjectives about tone.
       Bad: "professional and friendly"
       Good: "Open with a one-sentence hook under 10 words. Second beat is a personal 
       anecdote or concrete example. Third beat delivers the counterintuitive insight or 
       actionable takeaway. Close with a direct question to drive comments. Use em dashes 
       liberally. Never use exclamation marks. Keep paragraphs to 1-2 sentences max."
       This directive is the brand's textual DNA — it ensures every caption sounds like 
       the same person wrote it, even across platforms and content types.
    
    OUTPUT FORMAT: Return a structured JSON object with these fields.
    Be specific and actionable. "Professional" is too vague — 
    "confident, authoritative, slightly playful" is useful.
    
    If the website is unavailable, work from the user's description and uploaded assets.
    """,
    tools=[fetch_website, analyze_brand_colors, extract_brand_voice, scan_competitors],
    output_key="brand_profile",
)
```

**Tool: `fetch_website`**
```python
import httpx
from bs4 import BeautifulSoup

async def fetch_website(url: str) -> dict:
    """Fetch and parse a website for brand analysis.
    
    Extracts: page title, meta description, visible text (first 5000 chars),
    CSS color values, image alt texts, navigation structure.
    
    Returns: {
        title: str, description: str, text_content: str,
        colors_found: list[str], images: list[str],
        nav_items: list[str]
    }
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        response = await client.get(url)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract text content
    for tag in soup(['script', 'style', 'nav', 'footer']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)[:5000]
    
    # Extract colors from inline styles and stylesheets
    colors = extract_css_colors(response.text)
    
    # Extract images
    images = [img.get('alt', '') for img in soup.find_all('img') if img.get('alt')]
    
    return {
        "title": soup.title.string if soup.title else "",
        "description": soup.find('meta', {'name': 'description'}),
        "text_content": text,
        "colors_found": colors[:10],
        "images": images[:20],
        "nav_items": [a.text.strip() for a in soup.find_all('a') if a.text.strip()][:20],
    }
```

**Tool: `analyze_brand_colors`**
```python
def analyze_brand_colors(css_colors: list[str], logo_path: str | None = None) -> dict:
    """Analyze extracted colors to determine brand palette.
    
    Returns: { 
        primary: str (hex), secondary: str (hex), accent: str (hex),
        background: str (hex), text: str (hex)
    }
    """
    # Sort by frequency, filter out common neutral colors
    # Return top colors as primary/secondary/accent
    pass
```

## 3.3 Strategy Agent

```python
strategy_agent = Agent(
    name="strategy_agent",
    model="gemini-3-flash-preview",
    description="Creates a multi-platform content calendar with AI-researched posting frequency from a brand profile using pillar-based repurposing",
    instruction="""You are a social media strategist creating a weekly content calendar.
    
    PILLAR-BASED STRATEGY (P1):
    Instead of 7 disconnected posts, identify 1-2 PILLAR ideas for the week — core themes
    or messages that can be repurposed across platforms. Then plan derivatives:
    
    Example for a coaching business with pillar "Pricing your services":
    - Monday: LinkedIn long-form post (deep dive, personal story)
    - Tuesday: X thread (same idea, condensed into 5 punchy tweets)  
    - Wednesday: Instagram carousel (visual tips, actionable steps)
    - Thursday: TikTok/Reel script (quick take, face-to-camera direction)
    - Friday: Instagram story poll ("How do you price your services?")
    - Saturday: LinkedIn comment/engagement post (follow-up to Monday)
    - Sunday: Rest or light content (behind-the-scenes, personal)
    
    Each day should include:
    1. PILLAR_ID: Which pillar this derives from (e.g., "pillar_1" or "standalone")
    2. PLATFORM: Which social platform (instagram, tiktok, linkedin, x)
    3. CONTENT THEME: What the post should be about
    4. DERIVATIVE_TYPE: How this relates to the pillar (original, condensed, visual, 
       conversational, engagement, standalone)
    5. CONTENT TYPE: photo, carousel, story, reel, thread
    6. POSTING TIME: Optimal time based on platform best practices
    7. CAPTION DIRECTION: Brief guidance for the caption tone/angle
    8. IMAGE DIRECTION: Brief guidance for the visual style
    9. PILLAR_CONTEXT: If a derivative, what was the original pillar's key message
       (so the Content Creator can maintain coherence across derivatives)
    
    CALENDAR PRINCIPLES:
    - Pillar derivatives should tell a coherent story across the week
    - Vary platforms throughout the week (not all Instagram)
    - Mix derivative types (not all text-heavy)
    - Space promotional content (max 2 direct sales posts per week)
    - Include engagement posts (questions, polls) alongside informational content
    - Consider day-of-week context (Monday motivation, Friday fun)
    - 1-2 standalone posts are fine for variety
    
    EVENT-AWARE PLANNING (P1):
    If BUSINESS_EVENTS_THIS_WEEK is provided, these are REAL events happening at the 
    business this week. They MUST be incorporated into the calendar:
    - A product launch, sale, or event should become a pillar with derivatives
    - Time-specific events should land on the correct day (e.g., "farmers market Saturday" 
      → Saturday's post is about the farmers market)
    - Events take priority over generic theme ideas — real is always better than invented
    - If no events are provided, generate thematic pillars as usual
    
    OUTPUT FORMAT: Return a JSON object with:
    - pillars: [{ id: string, theme: string, key_message: string, source: "event" | "generated" }]
    - days: [7 day objects with the fields above]
    
    BRAND PROFILE: {brand_profile}
    USER GOALS: {user_goals}
    BUSINESS_EVENTS_THIS_WEEK: {business_events or "None provided — generate thematic pillars."}
    """,
    tools=[generate_calendar, research_trending_hashtags],
    output_key="content_calendar",
)
```

### 3.3.1 Social Proof Tier System

The Strategy Agent computes a social proof tier from the brand profile and adjusts pillar balance, CTA strategy, and content depth accordingly. The same tier logic is replicated identically in the Content Creator, Review Agent, and Voice Coach.

```python
# Social proof tier computation (shared across all agents)
_has_years = bool(brand_profile.get("years_in_business"))
_has_clients = bool(brand_profile.get("client_count"))

if _has_years and _has_clients:
    proof_tier = "data_rich"       # Full freedom: lead with hard numbers
elif _has_years or _has_clients:
    proof_tier = "partial_data"    # Lean on available data, process authority for gaps
else:
    proof_tier = "thin_profile"    # Education-heavy — teach to build credibility
```

| Tier | Condition | Pillar Balance | Promotion Cap | CTA Strategy |
|------|-----------|---------------|---------------|--------------|
| `data_rich` | years + clients | All 5 pillars, balanced | 2/week, can lead with social proof | Full rotation: engagement, conversion, implied |
| `partial_data` | years OR clients | Education anchor (3+), available data only | 1-2/week, reference available data | Conversion CTAs reference available data only |
| `thin_profile` | Neither | Education anchor (4+ of 7), UGC excluded | 1/week max, service-only (no social proof) | Engagement CTAs preferred, max 1 conversion/week |

### 3.3.2 Platform Intelligence (Google Search Grounding)

The Strategy Agent uses Google Search grounding to research the best platforms for a specific business type/industry. Results are cached in Firestore (keyed by industry + business_type, TTL 7 days).

```python
# Platform research with Google Search grounding
config = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())],
    temperature=0.2,
    # NOTE: response_mime_type="application/json" is NOT used here —
    # it is incompatible with Google Search grounding and causes a 400 error.
)
```

### 3.3.3 Post Metadata Fields

Each day brief now includes `pillar`, `format`, and `cta_type` fields that are stored on the post document and passed to the Content Creator and Review Agent:

```python
# Strategy Agent output per day
{
    "pillar": "education",         # One of: education, inspiration, promotion, behind_the_scenes, user_generated
    "format": "carousel",          # One of: original, carousel, thread_hook, blog_snippet, story, pin, video_first
    "cta_type": "engagement",      # One of: engagement, conversion, implied, none
    "derivative_type": "carousel", # How this post relates to its pillar
    "suggested_time": "6:00 PM",  # AI-researched best posting time for this platform
    ...
}
```

### 3.3.4 Prior Hook Deduplication

The Strategy Agent receives a list of prior hooks from previously generated posts (for the same brand and plan) and instructs the LLM to avoid repeating hooks. This prevents repetitive content across the week.

### 3.3.5 Posting Frequency Research (Google Search Grounding)

The Strategy Agent calls `_research_posting_frequency()` to determine optimal posting cadence per platform. This function uses Gemini with Google Search grounding to research how often a business in a given industry/type should post on each selected platform, and at what times.

```python
async def _research_posting_frequency(
    industry: str, business_type: str, platforms: list[str]
) -> dict:
    """Research optimal posts/week and best posting times per platform.

    Uses Gemini + Google Search to get current best-practice data.

    Returns:
        {
            "instagram": {"posts_per_week": 4, "best_times": ["9:00 AM", "1:00 PM", "6:00 PM"]},
            "linkedin": {"posts_per_week": 3, "best_times": ["8:00 AM", "12:00 PM"]},
            ...
        }
    """
```

Results are cached in Firestore under the `posting_frequency` collection, keyed by `industry + business_type + platforms` (sorted, joined). Cache TTL is 7 days.

The total number of briefs generated is computed as:

```python
total_briefs = sum(freq["posts_per_week"] for freq in platform_frequencies.values())
```

This replaces the previous fixed `num_days` (7) for generation count, allowing the calendar to contain more or fewer briefs depending on AI-researched frequency.

The `_enforce_platform_concentration` function is disabled when frequency research is active, since the research output already handles platform distribution.

### 3.3.6 Multi-Platform Brief Indexing

With multi-platform calendars, the number of briefs can exceed 7 (one per day). Two indices track each brief's position:

- **`brief_index`**: The brief's position in the `plan.days[]` array (0-based). This is the canonical array index used for URL navigation (e.g., `/generate/{planId}/{brief_index}`).
- **`day_index`**: The calendar day number (0-6, Monday=0). Multiple briefs can share the same `day_index` if multiple posts are scheduled for the same day.

Posts store both fields:
- `day_index` is used for display grouping and day-based matching in the calendar view.
- `brief_index` is used for URL navigation and API routing.

On the frontend, `_arrayIndex` tracks the original array position through day-group sorting, ensuring that navigation links point to the correct brief even after the UI reorders items by day.

Post deletion matches on `brief_index + platform` to uniquely identify the target brief within a plan.

## 3.4 Content Creator Agent ⭐ (Interleaved Output)

This is the star of the submission. It uses Gemini's interleaved output to generate caption text and matching product images in a single API call. When a user uploads their own photo (P1 BYOP mode), the agent switches to image-understanding mode — analyzing the photo and generating captions for it instead of generating an image.

```python
from google import genai
from google.genai import types

client = genai.Client()

async def generate_post(brand_profile: dict, day_brief: dict, 
                         user_photo_url: str | None = None) -> AsyncGenerator:
    """Generate a single post. Two modes:
    
    MODE A (no user photo): Interleaved text + image output. 
        Caption and image are born together. The "wow" demo moment.
    MODE B (user photo provided, P1): Text-only output with image understanding.
        AI analyzes the user's photo and writes a caption specifically for it.
    
    Yields SSE events as parts stream from the model.
    """
    
    # --- Build prompt based on mode ---
    base_context = f"""You are the creative director for {brand_profile['business_name']}.

BRAND VOICE: {brand_profile['tone']}
BRAND COLORS: {', '.join(brand_profile['colors'])}
TARGET AUDIENCE: {brand_profile['target_audience']}
VISUAL STYLE: {brand_profile.get('visual_style', 'clean, modern, professional')}
INDUSTRY: {brand_profile['industry']}
BUSINESS TYPE: {brand_profile.get('business_type', 'general')}

CAPTION STYLE DIRECTIVE (follow this writing rhythm for ALL captions):
{brand_profile.get('caption_style_directive', 'Write in a natural, engaging tone appropriate for the platform.')}

TODAY'S BRIEF:
- Platform: {day_brief['platform']}
- Theme: {day_brief['theme']}
- Content Type: {day_brief['content_type']}
- Caption Direction: {day_brief['caption_direction']}
"""

    if user_photo_url:
        # --- MODE B: BYOP — write captions FOR user's photo ---
        photo_bytes = await download_from_gcs(user_photo_url)
        
        prompt_parts = [
            types.Part.from_text(base_context + """
PHOTO PROVIDED: The user has uploaded their own photo for this post.
Analyze the photo carefully and generate content that complements it:

1. A compelling caption for {platform} that references specific visual elements in the photo
   (colors, composition, subjects, mood, setting — be specific, not generic)
2. 5-8 relevant hashtags (mix of popular and niche, tailored to what's IN the photo)
3. Recommended posting time

Do NOT describe the photo generically. Reference specific details you see.
The caption should make followers feel like they're seeing a curated, intentional post.
""".format(platform=day_brief['platform'])),
            types.Part.from_image(types.Image.from_bytes(
                data=photo_bytes, mime_type="image/jpeg"
            ))
        ]
        
        response_stream = client.models.generate_content_stream(
            model="gemini-3-flash-preview",
            contents=prompt_parts,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],  # Text-only — we already have the image
                temperature=0.8,
            )
        )
        
        async for chunk in response_stream:
            for part in chunk.candidates[0].content.parts:
                if part.text:
                    yield {"type": "text", "content": part.text}
        
        # Emit the user's own photo as the image event
        yield {"type": "image", "url": user_photo_url, "mime_type": "image/jpeg", 
               "source": "user_upload"}
    
    else:
        # --- MODE A: Interleaved output — generate caption + image together ---
        prompt = base_context + f"""
- Image Direction: {day_brief['image_direction']}

VISUAL IDENTITY DIRECTIVE (apply to ALL generated images for this brand):
{brand_profile.get('image_style_directive', 'clean, modern, professional aesthetic')}

GENERATE THE FOLLOWING IN ORDER:
1. A compelling caption for {day_brief['platform']} (appropriate length for platform)
2. A matching product/lifestyle image that fits the brand aesthetic
   - IMPORTANT: Follow the Visual Identity Directive above for color palette, 
     lighting, composition, and texture. Every image must feel like it belongs 
     to the same Instagram feed.
   - NO text overlays on the image
   - Style: {day_brief['image_direction']}
   - Resolution: High quality, suitable for social media
3. 5-8 relevant hashtags (mix of popular and niche)
4. Recommended posting time

Generate the caption and image TOGETHER as interleaved output.
The image should visually match the mood and message of the caption.
"""
        
        response_stream = client.models.generate_content_stream(
            model="gemini-3.1-flash-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.8,
            )
        )
        
        async for chunk in response_stream:
            for part in chunk.candidates[0].content.parts:
                if part.text:
                    yield {"type": "text", "content": part.text}
                elif part.inline_data:
                    image_url = await upload_image_to_gcs(
                        part.inline_data.data,
                        part.inline_data.mime_type
                    )
                    yield {"type": "image", "url": image_url, "mime_type": part.inline_data.mime_type}
```

**Critical Implementation Note:** The `generate_content_stream` method may not stream individual parts of interleaved output — it may buffer the entire response. If streaming is unavailable for interleaved mode, fall back to the non-streaming `generate_content` and simulate progressive display:

```python
async def generate_post_fallback(brand_profile: dict, day_brief: dict):
    """Non-streaming fallback if interleaved output doesn't support streaming."""
    
    response = await client.aio.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        )
    )
    
    results = []
    for part in response.candidates[0].content.parts:
        if part.text:
            results.append({"type": "text", "content": part.text})
        elif part.inline_data:
            image_url = await upload_image_to_gcs(
                part.inline_data.data,
                part.inline_data.mime_type
            )
            results.append({"type": "image", "url": image_url})
    
    return results
```

### 3.4.1 video_first Pipeline

For posts with `derivative_type: "video_first"`, the Content Creator generates a caption-only (no image) and then automatically triggers Veo 3.1 video generation. This is the reverse of the standard flow where image comes first and video is additive.

```
Standard pipeline:  Caption + Image (interleaved) → optional Veo video from hero image
video_first:        Caption-only (no image gen) → auto-trigger Veo text-to-video
```

The platform's `char_limits["video_first"]` enforces teaser-length captions (e.g., 200 chars for Instagram, 500 for LinkedIn).

### 3.4.2 Carousel Optimization (v1.9)

Carousel image generation was optimized from sequential batches to full concurrency:

- **Semaphore raised from 3 to 7:** `asyncio.Semaphore(7)` in `carousel_builder.py` allows all 7 carousel slides to generate concurrently. Previously, a semaphore of 3 produced images in 3+3+1 sequential batches.
- **Generation time improvement:** ~15 min → ~3 min for a full 7-slide carousel (bottleneck is now the slowest single Gemini image generation call, not cumulative sequential calls).
- **Text-only regeneration:** The `regen_mode=text_only` query parameter on `GET /api/generate/{planId}/{day}` enables regenerating captions and hashtags without re-generating images. The `existing_images` parameter passes through the current image URLs, which are re-emitted as SSE image events without touching the Gemini image API. This supports rapid caption iteration without burning image budget.

```python
# backend/agents/carousel_builder.py — concurrent carousel generation
semaphore = asyncio.Semaphore(7)  # v1.9: raised from 3

async def generate_carousel_images(brand, brief, slide_prompts: list[str]):
    """Generate all carousel slides concurrently within semaphore bounds."""
    async def gen_slide(prompt):
        async with semaphore:
            return await generate_single_image(brand, brief, prompt)

    results = await asyncio.gather(*[gen_slide(p) for p in slide_prompts])
    return results
```

### 3.4.3 Brand Reference Image Injection

The Content Creator and Video Creator both use the Brand Assets Service (`backend/services/brand_assets.py`) to inject up to 3 brand reference images into every Gemini generation call. This ensures visual consistency with the brand's actual assets.

```python
# Images prepended to Gemini request as visual reference
ref_images = await get_brand_reference_images(brand_profile, max_images=3)
# ref_images = [(bytes, mime_type), ...] — logo, product photos, style ref
# Priority: logo → product_photos → style_reference → uploaded_assets
# Cached in-memory per brand_id for process lifetime
```

### 3.4.4 Platform Registry Integration

The Content Creator imports platform-specific content prompts from the Platform Registry (`backend/platforms.py`) rather than maintaining local platform dicts. This ensures all agents share a single source of truth for platform formatting rules.

```python
from backend.platforms import get as get_platform

spec = get_platform(platform)  # Returns PlatformSpec
# spec.content_prompt  — platform-specific generation instructions
# spec.char_limits     — per-derivative character limits
# spec.hashtag_limit   — max hashtags for this platform
# spec.fold_at         — "see more" fold position (if applicable)
```

## 3.5 Review Agent

```python
review_agent = Agent(
    name="review_agent",
    model="gemini-3-flash-preview",
    description="Reviews generated content against brand profile for consistency",
    instruction="""You are a brand consistency reviewer. Evaluate generated social 
    media content against the brand profile.
    
    CHECK THE FOLLOWING:
    1. TONE CONSISTENCY: Does the caption match the brand voice?
       Score: 1-5 (5 = perfect match)
    2. AUDIENCE FIT: Is the content appropriate for the target audience?
       Score: 1-5
    3. PLATFORM RULES: Does it meet platform-specific targets?
       - Instagram: 150-250 words, 8-12 hashtags
       - LinkedIn: 150-300 words, 3-5 hashtags
       - Twitter/X: ≤280 chars, 1-2 hashtags woven into text
       - TikTok: 50-150 chars, 4-6 hashtags
       - Facebook: 100-250 words, 0-3 hashtags
       - LinkedIn: < 3,000 chars
       - TikTok caption: < 2,200 chars
       - Hashtag count: 5-30 for Instagram, 3-5 for other platforms
    4. BRAND COLOR CONSISTENCY: Does the image appear to use brand colors?
       Score: 1-5
    5. OVERALL QUALITY: Is this content ready to post?
       Score: 1-5
    
    OUTPUT FORMAT: Return a JSON object:
    {
        "overall_score": number (1-5),
        "approved": boolean (true if all scores >= 3),
        "checks": {
            "tone": { "score": number, "feedback": string },
            "audience": { "score": number, "feedback": string },
            "platform": { "score": number, "feedback": string },
            "visual": { "score": number, "feedback": string },
            "quality": { "score": number, "feedback": string }
        },
        "suggestions": [string],  // Actionable improvement suggestions
        "revised_caption": string | null,   // Proposed improved caption (if score < 4)
        "revised_hashtags": [string] | null // Auto-cleaned hashtags (stopwords removed,
                                            // per-platform count enforced, junk stripped)
    }

    HASHTAG CLEANING RULES:
    - Strip tags shorter than 3 characters
    - Strip common English stopwords (#the, #for, #your, #an, #is, #here, #this)
    - Validate each tag is alphanumeric + underscores only (no apostrophes, spaces, punctuation)
    - Enforce per-platform max count: IG: 12, LinkedIn: 5, Twitter: 2, TikTok: 6, Facebook: 3
    - CRITICAL: Only output real hashtags. Never convert sentence fragments into hashtags
    
    BRAND PROFILE: {brand_profile}
    GENERATED CAPTION: {caption}
    GENERATED HASHTAGS: {hashtags}
    TARGET PLATFORM: {platform}
    """,
    tools=[check_brand_consistency, validate_hashtags, check_platform_rules],
    output_key="review_result",
)
```

### 3.5.1 Multiplicative Two-Step Scoring System (Shipped, supersedes calibrated rubric)

> **Superseded:** The previous "calibrated 1-10 rubric" (v1.6) relied on the LLM to output a single overall score, which was prone to inflation. The new system separates LLM judgment from score computation.

The Review Agent scoring is now a two-step process:

**Step 1 — LLM Assessment:** The LLM outputs two structured fields:
- `engagement_scores`: 5 dimensions (hook_strength, relevance, cta_effectiveness, platform_fit, teaching_depth), each scored 1-10.
- `structural_issues`: A list of objective violations (e.g., "caption exceeds 280 chars for X", "hashtag count exceeds platform limit").

**Step 2 — Code Computation:**
```python
# content_quality = weighted average of engagement_scores
# Weights are platform-specific, loaded from platforms.py
content_quality = sum(
    score * weight
    for score, weight in zip(engagement_scores.values(), platform_weights.values())
)

# structural_modifier = penalty for violations, floored per platform
structural_modifier = max(
    platform_floor,  # 0.60-0.92 depending on platform
    1.0 - (penalty_per_issue * len(structural_issues))
)

# Final score
score = content_quality * structural_modifier
```

**Platform-specific weights** are defined in `platforms.py` across 15 profiles (11 platforms + 4 derivative overrides: carousel, thread_hook, video_first, story). Each profile adjusts which engagement dimensions matter most — e.g., X weighs hook_strength heavily, LinkedIn weighs teaching_depth.

**Structural modifier floors** prevent a single minor issue from tanking the score:

| Platform | Floor | Rationale |
|----------|-------|-----------|
| Instagram | 0.70 | Moderate — hashtag/fold violations common |
| LinkedIn | 0.75 | Professional context tolerates fewer issues |
| X | 0.60 | Tight constraints (280 chars) mean violations are severe |
| TikTok | 0.80 | Casual platform, minor issues less impactful |
| Pinterest | 0.92 | SEO-focused, structural violations rare |

Approval threshold: `score >= 8` (hard-coded, not trusted from model output).

### 3.5.2 Engagement Scoring (5 Dimensions)

Each review returns `engagement_scores` with 5 independently scored dimensions:

```json
{
  "engagement_scores": {
    "hook_strength": 7,       // How compelling is the opening line?
    "relevance": 8,           // How on-brand and relevant to target audience?
    "cta_effectiveness": 6,   // How clear and motivating is the CTA?
    "platform_fit": 9,        // Format, length, hashtag count for this platform?
    "teaching_depth": 8       // Does it teach something specific and actionable?
  },
  "engagement_prediction": "high"  // "low" | "medium" | "high" | "viral"
}
```

`teaching_depth` scores: 8-10 names a concrete technique/framework, 5-7 gives general advice, 1-4 is purely promotional, 0 for non-education posts.

### 3.5.3 Platform-Specific Checks

Review checks are loaded from the Platform Registry (`get_review_guidelines_block()`) and from per-platform check dictionaries covering all 10 platforms: Instagram (fold ≤125 chars), LinkedIn (fold ≤140 chars, no external links), TikTok (lowercase voice, keyword density), Facebook (shareability, engagement CTA default), X (280 char hard limit, no hashtag blocks), Pinterest (SEO keywords, no hashtags, no first-person), YouTube Shorts (video format, keyword SEO), Threads (anti-promotion, engagement-only CTA), Mastodon (CamelCase hashtags, no engagement bait), and Bluesky (300 char limit, specificity).

### 3.5.4 Derivative-Specific Checks

Additional checks are applied based on `derivative_type`: `video_first` (teaser length, curiosity-driven), `carousel` (up to 7-slide structure, hook/teach/takeaway), `thread_hook` (3-7 posts, per-platform char limits, standalone value per post), `story` (≤50 words, single CTA), `blog_snippet` (150-200 words, bold opener), `pin` (title + description format, keyword-rich).

### 3.5.5 Thin-Profile Social Proof Check

For brands with `social_proof_tier == "thin_profile"`, a critical check deducts 3 points for any fabricated social proof: client references, client counts, years of experience, made-up statistics, dollar amounts, or percentages not in the brand profile. The only valid proof for thin-profile brands is teaching depth.

### 3.5.6 CTA Type Enforcement

The review enforces the `cta_type` assigned by the Strategy Agent (`engagement`, `conversion`, `implied`, `none`). Each type has specific scoring criteria — e.g., an `engagement` post with conversion language loses 2 points; a `none` post with any CTA loses 2 points.

## 3.6 Voice Coach (Gemini Live API)

The Voice Coach uses the Gemini Live API (`BidiGenerateContent`) for multi-turn voice coaching sessions. It now includes full strategic awareness — the same social proof tier system, pillar definitions, CTA strategy, and platform strengths that drive the content calendar.

```python
# Voice coach prompt injection (from backend/agents/voice_coach.py)
# Builds tier-aware CONTENT STRATEGY CONTEXT block:
# - Social proof tier block (data_rich / partial_data / thin_profile)
# - Content pillars with tier-adjusted balance
# - CTA approach with tier-appropriate guidance
# - Platform strengths scoped to brand's connected_platforms
strategy_context = (
    f"CONTENT STRATEGY CONTEXT:\n"
    f"You built this brand's content calendar — know these principles "
    f"so you can explain WHY:\n\n"
    f"{tier_block}\n\n{pillar_block}\n\n{cta_block}\n\n{platform_block}\n\n"
    f"FORMAT LOGIC:\n"
    f"- Carousels: Slide 1 hooks, Slide 2 teaches, Slide 3 takeaway\n"
    f"- Threads: every post teaches; never end with brand pitch\n"
    f"- Reels/video: outperforms static — always the reach play"
)
```

**WebSocket Authentication (v1.8):** The Voice Coach WebSocket endpoint is authenticated via the `Sec-WebSocket-Protocol` header — the only mechanism the browser WebSocket API supports for sending credentials during the handshake. The frontend sends `auth.<firebase_id_token>` as a subprotocol; the backend's `verify_ws_brand_owner` dependency extracts and verifies the token via `firebase_admin.verify_id_token()` (run in a thread executor to avoid blocking the event loop) *before* calling `websocket.accept()`. The server echoes back the exact subprotocol string per RFC 6455 §4.2.2. This ensures unauthenticated connections never consume server resources (no pre-auth DoS vector) and the token never appears in Cloud Run URL logs.

**Content Calendar Context Injection (v1.7):** The Voice Coach now receives the full content calendar context when invoked from the Dashboard. The `plan_id` is passed from `DashboardPage` → `VoiceCoach` → `useVoiceCoach` → WebSocket URL. The backend loads the plan and injects:
- Calendar days (themes, platforms, derivative types)
- Review scores for already-generated posts
- Trend insights from Google Search grounding
- Pillar definitions and CTA strategy

This allows the coach to answer questions like "Why did you schedule a carousel on Wednesday?" or "How can I improve my LinkedIn post that scored 6.2?"

Key capabilities: explain WHY the calendar has its specific pillar mix, coach caption writing in the brand's authentic voice, give platform-specific advice, suggest content ideas grounded in the brand's actual business, and discuss specific posts from the current calendar with awareness of their review scores.

---

# 4. API Specification

## 4.1 REST Endpoints

### Brand Management

```
POST /api/brands
Body: { website_url?: string, description: string, uploaded_assets?: string[], owner_uid?: string }
  // description: free-text business description (min 20 chars, required)
  // website_url: optional — omitted in no-website mode
  // uploaded_assets: optional array of Cloud Storage refs for brand assets (images, PDFs)
  // owner_uid: Firebase Google Auth UID — links this brand to the user
Response: { brand_id: string, status: "created" }

GET /api/brands?owner_uid={uid}
  // Returns all brands linked to this Firebase Google Auth UID
Response: { brands: BrandProfile[] }

PATCH /api/brands/{brandId}/claim
Body: { owner_uid: string }
  // Grandfathers a pre-auth brand to the current user — only if brand has no owner yet
Response: { status: "claimed" | "already_owned" }

POST /api/brands/{brandId}/analyze
Body: { website_url?: string, description: string }
  // If website_url present: crawl site + analyze description + process uploads
  // If website_url absent (no-website mode): infer brand from description + uploads only
Response: { brand_profile: BrandProfile, status: "analyzed" }
  // Triggers Brand Analyst Agent

GET /api/brands/{brandId}
Response: { brand_profile: BrandProfile }

PUT /api/brands/{brandId}
Body: Partial<BrandProfile>  // User corrections
Response: { brand_profile: BrandProfile, status: "updated" }

POST /api/brands/{brandId}/upload
Body: multipart/form-data (images: jpg/png, documents: pdf — max 3 files)
Response: { uploaded: [{ filename, url, type: "image" | "document" }] }
  // PDFs processed via Gemini multimodal for brand guide extraction
  // Images analyzed for brand colors, style, and product identification

DELETE /api/brands/{brandId}/assets/{assetIndex}
Response: { status: "deleted" }
  // Removes an uploaded asset by index from the brand profile

PATCH /api/brands/{brandId}/logo
Body: { logo_url: string | null }
Response: { status: "updated" }
  // Sets or clears the brand logo URL
```

### Notion Integration

```
GET /api/brands/{brandId}/integrations/notion/auth-url
Response: { url: string }
  // Returns Notion OAuth authorization URL for the user to initiate connection

GET /api/integrations/notion/callback?code={code}&state={brandId}
Response: Redirect to /dashboard/{brandId}
  // Handles Notion OAuth callback — exchanges code for access token, stores in Firestore

POST /api/brands/{brandId}/integrations/notion/disconnect
Response: { status: "disconnected" }
  // Removes Notion tokens and database selection from the brand

GET /api/brands/{brandId}/integrations/notion/databases
Response: { databases: [{ id: string, title: string }] }
  // Lists Notion databases accessible to the integration

POST /api/brands/{brandId}/integrations/notion/select-database
Body: { database_id: string }
Response: { status: "selected" }
  // Stores the selected Notion database for future exports

POST /api/brands/{brandId}/plans/{planId}/export/notion
Response: { exported: number, database_id: string }
  // Exports all posts in the plan to the connected Notion database
  // Creates one page per post with properties: Name, Platform, Day, Status,
  // Caption, Posting Time, Content Type, Hashtags, Image URL
  // Auto-creates missing database properties via ensure_database_schema()
```

### Calendar Export

```
GET /api/brands/{brandId}/plans/{planId}/calendar.ics
Response: text/calendar (iCalendar .ics file)
  // Downloads an .ics file with VEVENT entries for each day's posting schedule
  // Events include: SUMMARY (platform + theme), DESCRIPTION (full caption),
  // DTSTART (posting time), DTEND (posting time + 30 min)

POST /api/brands/{brandId}/plans/{planId}/calendar/email
Body: { email: string }
Response: { status: "sent" }
  // Sends the .ics calendar file as an email attachment via Resend API
  // Subject: "Your {brand_name} Content Calendar — Amplispark"
```

### Content Planning

```
POST /api/plans
Body: { brand_id: string, goals?: string, platforms?: string[], business_events?: string }
Response: { plan_id: string, pillars: Pillar[], calendar: DayBrief[7] }
  // Triggers Strategy Agent
  // Pillar: { id: string, theme: string, key_message: string, source: "event" | "generated" }
  // business_events: free-text, e.g. "launching lavender croissant Tuesday, farmer's market Saturday"
  // DayBrief now includes: pillar_id, derivative_type, pillar_context

GET /api/plans/{planId}
Response: { plan: ContentPlan }

PUT /api/plans/{planId}/days/{dayIndex}
Body: Partial<DayBrief>  // User rearrangement
Response: { day: DayBrief }
```

### Photo Upload (P1 — BYOP)

```
POST /api/plans/{planId}/days/{dayIndex}/photo
Body: multipart/form-data (photo)
Response: { photo_url: string, day_index: int }
  // Uploads user photo to GCS, sets user_photo_url on the day brief
  // When this day is generated, Content Creator uses Mode B (image understanding)

DELETE /api/plans/{planId}/days/{dayIndex}/photo
Response: { status: "removed" }
  // Removes user photo, day reverts to Mode A (interleaved generation)
```

### Content Generation (SSE Stream)

```
GET /api/generate/{planId}/{dayIndex}
Accept: text/event-stream
Response: SSE stream of events:

  MODE A (AI-generated image — single image post):
  event: text
  data: {"content": "Rise and grind! Our new espresso blend..."}

  event: image
  data: {"url": "/api/storage/serve/generated/.../image.png", "mime_type": "image/png", "source": "generated"}

  event: text
  data: {"content": "#coffee #morningroutine #espresso..."}

  MODE A-CAROUSEL (Instagram carousel — up to 7 slides, concurrent image gen):
  event: text
  data: {"content": "Swipe for the full story..."}

  event: image
  data: {"url": "/api/storage/serve/generated/.../slide_1.png", "mime_type": "image/png", "source": "generated"}
  ...
  event: image
  data: {"url": "/api/storage/serve/generated/.../slide_7.png", "mime_type": "image/png", "source": "generated"}

  event: text
  data: {"content": "#carousel #tips..."}

  MODE B (user photo uploaded for this day — P1 BYOP):
  event: text
  data: {"content": "That golden hour light hitting the fresh batch..."}

  event: image
  data: {"url": "/api/storage/serve/.../user_photo.jpg", "mime_type": "image/jpeg", "source": "user_upload"}

  event: text
  data: {"content": "#bakerylife #freshbread #goldenhour..."}

  IMAGE FALLBACK (when interleaved mode produces no image):
  event: status
  data: {"message": "Retrying image generation..."}

  event: image
  data: {"url": "/api/storage/serve/generated/.../fallback.png", "mime_type": "image/png", "source": "generated"}

  BOTH MODES:
  event: complete
  data: {"post_id": "post_abc123"}

  event: review
  data: {"overall_score": 4.2, "approved": true, "checks": {...}, "revised_hashtags": [...]}
```

### Post Management

```
GET /api/posts?brand_id={brandId}&plan_id={planId}
Response: { posts: Post[] }

PUT /api/posts/{postId}/approve
Response: { status: "approved" }

POST /api/posts/{postId}/regenerate
Body: { feedback?: string }
Response: SSE stream (same as generate)

GET /api/posts/{postId}/export?brand_id={brandId}
Response: StreamingResponse (application/zip)
  // Returns a ZIP containing:
  //   {post_name}/{post_name}.{png|jpg}   — hero image (downloaded via blob.download_as_bytes)
  //   {post_name}/{post_name}.mp4          — video (if generated)
  //   {post_name}/caption.txt              — caption + hashtags

POST /api/export/{planId}?brand_id={brandId}
Response: StreamingResponse (application/zip)
  // Returns a ZIP of ALL posts in the plan:
  //   day_N_{platform}/{post_name}.{png|jpg}
  //   day_N_{platform}/{post_name}.mp4
  //   day_N_{platform}/caption.txt
  //   metadata.json   — full post data (image_gcs_uri stripped)
  // Media downloaded directly from GCS via blob.download_as_bytes()
  // (not via signed URLs — works identically in local dev and prod)

PATCH /api/posts/{postId}/approve?brand_id={brandId}
Response: { status: "approved" | "unapproved" }
  // Toggles approval status on the post
```

## 4.2 SSE Implementation

> **Note (v1.7):** The app setup below reflects the modular router architecture. `server.py` is now ~65 lines. Each router is a separate module in `backend/routers/`.

```python
# backend/server.py (~80 lines — app setup + middleware + router includes + exception handler)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.middleware import firebase_auth_middleware
from backend.middleware_logging import RequestContextMiddleware
from backend.routers import brands, plans, posts, generation, media, integrations, voice
import logging

logger = logging.getLogger(__name__)

app = FastAPI()

# Structured JSON logging middleware (v1.9) — must be added before CORS
# Uses contextvars to propagate request_id and user_uid across async call stack
app.add_middleware(RequestContextMiddleware)

# CORS middleware — explicit methods and headers (v1.9, tightened from wildcards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("CORS_ORIGINS", "http://localhost:5173")],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    allow_credentials=True,
)

# Firebase Auth middleware (verifies ID tokens on all /api/* routes)
app.middleware("http")(firebase_auth_middleware)

# Global exception handler (v1.9) — catches unhandled errors, returns clean JSON 500
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", extra={
        "path": request.url.path,
        "method": request.method,
        "error_type": type(exc).__name__,
        "error_detail": str(exc),
    })
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Router includes — each router owns its route prefix
app.include_router(brands.router, prefix="/api")       # /api/brands/*
app.include_router(plans.router, prefix="/api")        # /api/plans/*
app.include_router(posts.router, prefix="/api")        # /api/posts/*
app.include_router(generation.router, prefix="/api")   # /api/generate/*
app.include_router(media.router, prefix="/api")        # /api/storage/*, /api/export/*
app.include_router(integrations.router, prefix="/api") # /api/brands/*/integrations/*
app.include_router(voice.router, prefix="/api")        # /api/voice/* — WS auth via Sec-WebSocket-Protocol (verify_ws_brand_owner)

# SPA catch-all with path traversal prevention
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # Reject path traversal attempts (../ sequences)
    if ".." in full_path:
        raise HTTPException(400, "Invalid path")
    # Serve static asset if exists, otherwise index.html
    ...
```

```python
# backend/middleware.py — Firebase Auth + brand ownership verification
import firebase_admin
from firebase_admin import auth as firebase_auth

async def verify_firebase_token(request: Request) -> dict:
    """Extract and verify Firebase ID token from Authorization header.
    Returns decoded token with uid, email, etc."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return firebase_auth.verify_id_token(token)

async def verify_brand_owner(brand_id: str, token: dict = Depends(verify_firebase_token)):
    """Verify the authenticated user owns the requested brand."""
    brand = await firestore_client.get_brand(brand_id)
    if brand.get("owner_uid") != token["uid"]:
        raise HTTPException(403, "Not authorized for this brand")
```

@app.get("/api/generate/{plan_id}/{day_index}")
async def generate_post_endpoint(
    plan_id: str, day_index: int, request: Request,
    regen_mode: str | None = None,   # v1.9: "text_only" skips image generation
    existing_images: str | None = None,  # v1.9: comma-separated existing image URLs to preserve
):
    """Stream interleaved post generation via SSE.

    v1.9: regen_mode=text_only query param enables text-only regeneration,
    preserving existing carousel images while regenerating captions/hashtags.
    existing_images parameter passes through URLs to skip image generation.
    """

    # Budget guard (Gap #7)
    if not await budget_tracker.can_generate_image():  # v1.9: async, Firestore-backed
        return JSONResponse(
            status_code=429,
            content={"error": "Image generation budget exhausted",
                     "budget": await budget_tracker.get_remaining()}
        )

    # Load brand profile and day brief
    # v1.9: brand profile cached with 30s TTL during generation
    plan = await firestore_client.get_plan(plan_id)
    brand = await get_brand_cached(plan["brand_id"], ttl_seconds=30)
    day_brief = plan["days"][day_index]

    # Check if user uploaded their own photo for this day (P1 BYOP)
    user_photo_url = day_brief.get("user_photo_url", None)

    async def event_stream():
        # v1.9: bounded SSE queue — prevents unbounded memory growth
        queue = asyncio.Queue(maxsize=200)
        post_data = {"texts": [], "images": [], "post_id": None}

        try:
            # Generate interleaved content (Mode A or B based on user photo)
            async for part in generate_post(brand, day_brief, user_photo_url=user_photo_url):
                if part["type"] == "text":
                    post_data["texts"].append(part["content"])
                    yield f"event: text\ndata: {json.dumps(part)}\n\n"
                elif part["type"] == "image":
                    post_data["images"].append(part["url"])
                    yield f"event: image\ndata: {json.dumps(part)}\n\n"
            
            # Zero-image fallback (Gap #5): only check if we expected AI image generation
            # In BYOP mode (user_photo_url present), no AI image is expected
            if not post_data["images"] and not user_photo_url:
                logger.warning("generation_no_image", extra={
                    "plan_id": plan_id, "day_index": day_index,
                    "text_parts": len(post_data["texts"]),
                })
                yield f'event: status\ndata: {json.dumps({"message": "Retrying image generation..."})}\n\n'
                
                # Retry with more explicit image instruction
                retry_results = await generate_post_fallback(brand, day_brief)
                retry_images = [r for r in retry_results if r["type"] == "image"]
                
                if retry_images:
                    for img in retry_images:
                        post_data["images"].append(img["url"])
                        yield f"event: image\ndata: {json.dumps(img)}\n\n"
                else:
                    # Both attempts failed — emit error event
                    yield f'event: error\ndata: {json.dumps({"code": "IMAGE_GEN_FAILED", "message": "Image generation failed after retry. Caption was saved — you can regenerate the image."})}\n\n'
            
            # Track budget
            budget_tracker.record_generation(len(post_data["images"]))
            
            # Save post to Firestore
            post_id = await firestore_client.save_post(
                brand_id=plan["brand_id"],
                plan_id=plan_id,
                day_index=day_index,
                caption="\n".join(post_data["texts"]),
                image_urls=post_data["images"],
                platform=day_brief["platform"],
            )
            post_data["post_id"] = post_id
            yield f"event: complete\ndata: {json.dumps({'post_id': post_id})}\n\n"
            
            # Run review agent
            review = await run_review_agent(brand, post_data)
            await firestore_client.save_review(post_id, review)
            yield f"event: review\ndata: {json.dumps(review)}\n\n"
        
        except Exception as e:
            logger.error("generation_error", extra={
                "plan_id": plan_id, "day_index": day_index, "error": str(e),
            })
            yield f'event: error\ndata: {json.dumps({"code": "GENERATION_ERROR", "message": str(e)})}\n\n'
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
```

## 4.3 TypeScript API Client

```typescript
// Frontend SSE consumer — supports single image and carousel (multiple images)
function usePostGeneration(planId: string, dayIndex: number) {
  const [caption, setCaption] = useState<string>("");
  const [imageUrl, setImageUrl] = useState<string | null>(null);      // First/hero image
  const [imageUrls, setImageUrls] = useState<string[]>([]);           // All images (carousel support)
  const [imageSource, setImageSource] = useState<"generated" | "user_upload" | null>(null);
  const [hashtags, setHashtags] = useState<string>("");
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [status, setStatus] = useState<"idle" | "generating" | "reviewing" | "done" | "error">("idle");
  
  const generate = useCallback(() => {
    setStatus("generating");
    setCaption("");
    setImageUrl(null);
    setHashtags("");
    setError(null);
    
    const eventSource = new EventSource(
      `/api/generate/${planId}/${dayIndex}`
    );
    
    let textParts: string[] = [];
    
    eventSource.addEventListener("text", (e) => {
      const data = JSON.parse(e.data);
      textParts.push(data.content);
      
      // First text part is usually the caption, subsequent are hashtags
      if (textParts.length === 1) {
        setCaption(data.content);
      } else {
        setHashtags(prev => prev + data.content);
      }
    });
    
    eventSource.addEventListener("image", (e) => {
      const data = JSON.parse(e.data);
      setImageUrl(prev => prev || data.url);  // First image becomes hero
      setImageUrls(prev => [...prev, data.url]);  // All images collected (carousel)
      setImageSource(data.source || "generated");  // "generated" or "user_upload"
    });
    
    eventSource.addEventListener("complete", (e) => {
      setStatus("reviewing");
    });
    
    eventSource.addEventListener("review", (e) => {
      const data = JSON.parse(e.data);
      setReview(data);
      setStatus("done");
      eventSource.close();
    });
    
    eventSource.addEventListener("error", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setError(data);
        // IMAGE_GEN_FAILED is non-fatal — caption was still saved
        if (data.code === "IMAGE_GEN_FAILED") {
          setStatus("done");  // Allow user to retry image only
        } else {
          setStatus("error");
        }
      } catch {
        setStatus("error");
        setError({ code: "UNKNOWN", message: "Connection lost" });
      }
      eventSource.close();
    });
    
    eventSource.onerror = () => {
      eventSource.close();
      setStatus("error");
      setError({ code: "CONNECTION_ERROR", message: "Lost connection to server" });
    };
  }, [planId, dayIndex]);
  
  return { caption, imageUrl, imageUrls, hashtags, review, error, status, generate };
}
```

---

# 5. Platform Registry (Shipped)

The Platform Registry (`backend/platforms.py`) is the single source of truth for all platform-specific configuration. Every backend agent imports from this module instead of maintaining local platform dicts. Adding a new platform requires one `PlatformSpec` entry here plus one entry in the frontend registry (`frontend/src/platformRegistry.ts`).

## 5.1 PlatformSpec Dataclass

```python
@dataclass(frozen=True)
class PlatformSpec:
    key: str                          # "instagram"
    display_name: str                 # "Instagram"
    content_prompt: str               # Full platform-specific generation prompt
    review_guidelines: str            # One-line summary for review agent
    hashtag_limit: int                # Max hashtags (e.g., 5 for IG, 1 for X)
    caption_max: int                  # Hard character limit (e.g., 2200 for IG)
    char_limits: dict[str, int]       # Per-derivative limits: {"default": 1200, "video_first": 200}
    fold_at: int | None               # "See more" fold position (125 for IG, 140 for LI)
    image_aspect: str                 # "1:1", "16:9", "9:16", "1.91:1"
    is_portrait_video: bool           # Whether video should be 9:16 (IG, TikTok)
    derivative_types: list[str]       # Supported formats: ["original", "carousel", "video_first", ...]
    voice: str                        # How content should *sound* on this platform
```

## 5.2 Platform Table (11 Platforms)

| Platform | Key | fold_at | hashtag_limit | caption_max | image_aspect | derivative_types |
|----------|-----|---------|---------------|-------------|--------------|-----------------|
| Instagram | `instagram` | 125 | 5 | 2200 | 1:1 | original, carousel, story, video_first |
| LinkedIn | `linkedin` | 140 | 5 | 3000 | 1.91:1 | original, carousel, blog_snippet, video_first |
| X | `x` | — | 1 | 280 | 16:9 | original, thread_hook, video_first |
| TikTok | `tiktok` | — | 6 | 2200 | 9:16 | original, carousel, video_first |
| Facebook | `facebook` | — | 3 | 63206 | 1.91:1 | original, carousel, story, video_first |
| Threads | `threads` | — | 3 | 500 | 1:1 | original |
| Pinterest | `pinterest` | — | 0 | 500 | 2:3 | original, pin |
| YouTube Shorts | `youtube_shorts` | — | 5 | 5000 | 9:16 | original, video_first |
| Mastodon | `mastodon` | — | 5 | 500 | 1:1 | original |
| Bluesky | `bluesky` | — | 3 | 300 | 1:1 | original, thread_hook |

## 5.3 Public Helpers

```python
def get(key: str) -> PlatformSpec | None:
    """Get a platform spec by key. Returns None if not found."""

def keys() -> list[str]:
    """Return all registered platform keys."""

def get_review_guidelines_block() -> str:
    """Build a formatted block of all platform review guidelines for the Review Agent prompt."""
```

## 5.4 Frontend Registry Mirror

`frontend/src/platformRegistry.ts` mirrors the backend registry with display-oriented fields: `displayName`, `icon`, `foldAt`, `captionMax`, `hashtagLimit`, `color`. Used by `PlatformPreview` for live character counts and fold indicators.

---

# 6. Brand Assets Service (Shipped)

The Brand Assets Service (`backend/services/brand_assets.py`) provides reference image injection for Gemini and Veo generation calls, ensuring visual consistency with the brand's actual assets.

## 6.1 Priority Order

Images are collected in priority order (up to `max_images`, default 3):

1. **Logo** — `logo_url` field, or first image-type entry in `uploaded_assets`
2. **Product photos** — `product_photos` list
3. **Style reference** — `style_reference_gcs_uri` from brand analyst
4. **Remaining uploaded image assets** — any other image uploads

## 6.2 Caching

Results are cached in-memory per `brand_id` for the process lifetime. Cache is keyed by `brand_id` and populated on first call.

```python
# Usage in Content Creator and Video Creator
from backend.services.brand_assets import get_brand_reference_images

ref_images = await get_brand_reference_images(brand_profile, max_images=3)
# Returns: list[tuple[bytes, str]]  — (image_bytes, mime_type) per image
```

## 6.3 Consumers

- **Content Creator** — prepends reference images as `types.Part.from_bytes()` to Gemini `generateContent` calls
- **Video Creator** — includes reference images in Veo prompt context for visual consistency

---

# 7. Data Model (Firestore)

## 7.1 Complete Schema

```
amplifi-db/
├── brands/
│   └── {brandId}/                         # Auto-generated
│       ├── owner_uid: string | null       # Firebase Google Auth UID — links brand to user
│       ├── business_name: string          # "Sunrise Bakery"
│       ├── business_type: string          # AI-inferred from description: "local_business" | "service" | "personal_brand" | "ecommerce"
│       ├── website_url: string | null     # "https://sunrisebakery.com" — null in no-website mode
│       ├── description: string            # Required free-text business description (min 20 chars)
│       ├── uploaded_assets: [{            # Optional brand assets (max 3)
│       │     filename: string,
│       │     url: string,                 # Cloud Storage signed URL
│       │     type: "image" | "document"
│       │   }]
│       ├── industry: string               # "Food & Beverage"
│       ├── tone: string                   # "warm, approachable, artisanal"
│       ├── colors: string[]               # ["#D4A574", "#8B4513", "#FFF8DC"]
│       ├── target_audience: string        # "Local food enthusiasts, 25-45, urban"
│       ├── visual_style: string           # "warm lighting, rustic textures, close-up product shots"
│       ├── image_style_directive: string  # P1: persistent visual identity fragment prepended to every image gen
│       │                                  # e.g. "warm earth tones, terracotta and sage accents, soft golden 
│       │                                  # hour lighting, minimalist compositions, organic textures"
│       ├── caption_style_directive: string # P1: persistent writing rhythm guide prepended to every caption gen
│       │                                  # e.g. "Open with one-sentence hook under 10 words. Personal anecdote
│       │                                  # second. Counterintuitive insight third. End with direct question."
│       ├── content_themes: string[]       # ["artisan process", "seasonal menu", "community events"]
│       ├── competitors: string[]          # ["competitor_a.com", "competitor_b.com"]
│       ├── logo_url: string | null        # "gs://amplifi-assets/brands/{brandId}/logo.png"
│       ├── product_photos: string[]       # ["gs://...", "gs://..."]
│       ├── years_in_business: number | null    # e.g. 5 — used for social proof tier
│       ├── client_count: number | null         # e.g. 200 — used for social proof tier
│       ├── location: string | null             # "Austin, TX"
│       ├── unique_selling_points: string | null # Brand differentiators
│       ├── connected_platforms: string[]        # ["instagram", "linkedin", "x"] — platforms the user is active on
│       ├── integrations: {                      # Third-party service connections
│       │     notion: {
│       │       access_token: string | null,
│       │       workspace_name: string | null,
│       │       database_id: string | null,
│       │       database_name: string | null
│       │     }
│       │   }
│       ├── created_at: timestamp
│       ├── updated_at: timestamp
│       ├── analysis_status: string        # "pending" | "analyzing" | "complete" | "failed"
│       │
│       ├── content_plans/                 # Subcollection
│       │   └── {planId}/
│       │       ├── week_of: string        # "2026-02-24" (ISO date of Monday)
│       │       ├── goals: string | null   # "Launch spring menu"
│       │       ├── business_events: string | null  # P1: "launching lavender croissant Tuesday, farmer's market Saturday"
│       │       ├── platforms: string[]    # ["instagram", "linkedin"]
│       │       ├── created_at: timestamp
│       │       ├── status: string         # "draft" | "generating" | "complete"
│       │       │
│       │       ├── pillars/               # Subcollection (P1 content repurposing)
│       │       │   └── {pillarId}/
│       │       │       ├── theme: string          # "Pricing your services"
│       │       │       ├── key_message: string    # "Value-based pricing builds better businesses"
│       │       │       ├── source: string         # "event" | "generated" — whether from business_events or AI-created
│       │       │       └── derivative_count: number  # How many days derive from this pillar
│       │       │
│       │       └── days/                  # Subcollection (7 documents)
│       │           └── {dayIndex}/        # "0" through "6" (Monday=0)
│       │               ├── day_name: string          # "Monday"
│       │               ├── platform: string          # "instagram"
│       │               ├── theme: string             # "Behind the scenes: morning bake"
│       │               ├── content_type: string      # "photo" | "carousel" | "story" | "reel" | "thread"
│       │               ├── caption_direction: string # "Show the early morning process, warm and inviting"
│       │               ├── image_direction: string   # "Golden hour lighting on fresh bread, flour dusted surface"
│       │               ├── posting_time: string      # "11:30 AM EST"
│       │               │
│       │               ├── pillar_id: string | null          # Reference to pillar (P1 repurposing)
│       │               ├── derivative_type: string | null    # "original" | "condensed" | "visual" | "conversational" | "engagement" | "standalone"
│       │               ├── pillar_context: string | null     # Key message from pillar for Content Creator coherence
│       │               │
│       │               ├── user_photo_url: string | null     # GCS URL of user-uploaded photo (P1 BYOP)
│       │               ├── image_source: string              # "generated" | "user_upload" (set after generation)
│       │               │
│       │               ├── generated: boolean        # Has content been generated?
│       │               ├── post_id: string | null    # Reference to generated post
│       │               └── status: string            # "planned" | "generated" | "approved" | "posted"
│       │
│       └── posts/                         # Subcollection
│           └── {postId}/
│               ├── plan_id: string        # Parent plan reference
│               ├── day_index: number      # 0-6 (calendar day, Monday=0)
│               ├── brief_index: number    # Array position in plan.days[] — used for URL navigation
│               ├── platform: string       # "instagram"
│               ├── caption: string        # Full caption text
│               ├── image_urls: string[]   # ["gs://amplifi-assets/generated/{postId}/image.png"]
│               ├── hashtags: string[]     # ["#artisanbread", "#freshbaked", ...]
│               ├── posting_time: string   # "11:30 AM EST"
│               ├── status: string         # "draft" | "approved" | "posted"
│               ├── pillar: string | null          # "education" | "inspiration" | "promotion" | "behind_the_scenes" | "user_generated"
│               ├── format: string | null          # "original" | "carousel" | "thread_hook" | "blog_snippet" | "story" | "pin" | "video_first"
│               ├── cta_type: string | null        # "engagement" | "conversion" | "implied" | "none"
│               ├── derivative_type: string | null # How this post relates to its pillar
│               │
│               ├── review/                # Embedded document
│               │   ├── score: number              # 1-10 (calibrated rubric)
│               │   ├── brand_alignment: string    # "strong" | "moderate" | "weak"
│               │   ├── approved: boolean          # true if score >= 8
│               │   ├── strengths: string[]        # 2-3 strength descriptions
│               │   ├── improvements: string[]     # 1-3 specific improvement suggestions
│               │   ├── revision_notes: string | null  # Specific edit instructions if score < 8
│               │   ├── revised_hashtags: string[] # Cleaned/validated hashtag array
│               │   ├── engagement_scores: {       # 5 independently scored dimensions
│               │   │     hook_strength: number,   # 1-10
│               │   │     relevance: number,       # 1-10
│               │   │     cta_effectiveness: number, # 1-10
│               │   │     platform_fit: number,    # 1-10
│               │   │     teaching_depth: number   # 1-10 (0 for non-education posts)
│               │   │   }
│               │   ├── engagement_prediction: string  # "low" | "medium" | "high" | "viral"
│               │   └── reviewed_at: timestamp
│               │
│               ├── video/                 # Embedded document (P1)
│               │   ├── video_gcs_uri: string | null  # gs:// URI to MP4 in Cloud Storage
│               │   ├── url: string | null            # Serving URL (backend proxy or signed)
│               │   ├── duration_seconds: number      # 8
│               │   ├── aspect_ratio: string          # "9:16" | "16:9"
│               │   ├── model: string                 # "veo-3.1-generate-preview"
│               │   ├── job_id: string | null         # Reference to video_jobs
│               │   └── generated_at: timestamp | null
│               │
│               ├── created_at: timestamp
│               ├── updated_at: timestamp
│               ├── status: string         # "draft" | "approved" | "posted" | "deleted" (v1.9 soft delete)
│               └── deleted_at: timestamp | null  # v1.9: set by delete_post, null when active
│
│       └── video_jobs/                    # Subcollection (P1)
│           └── {jobId}/
│               ├── post_id: string
│               ├── status: string                 # "queued" | "generating" | "complete" | "failed"
│               ├── tier: string                   # "fast" | "standard"
│               ├── result: map | null             # { video_url, duration_seconds, ... }
│               ├── error: string | null
│               ├── created_at: timestamp
│               └── updated_at: timestamp
```

**System documents (v1.9):**

```
amplifi-db/
├── _system/
│   └── budget                              # Singleton — global budget state (v1.9)
│       ├── images_generated: number        # Total images generated across all brands
│       ├── videos_generated: number        # Total videos generated
│       ├── image_cost: number              # Cumulative image cost ($)
│       ├── video_cost: number              # Cumulative video cost ($)
│       └── updated_at: timestamp           # Last write timestamp
```

**Soft deletes (v1.9):** `delete_post` sets `status="deleted"` and `deleted_at` timestamp on the post document rather than performing a hard delete. `list_posts` filters out posts where `status == "deleted"`. No hard deletes are performed — this enables future recovery/undo functionality.

## 7.2 Cloud Storage Structure

```
gs://amplifi-assets-2026/
├── brands/
│   └── {brandId}/
│       ├── logo.png                       # Uploaded by user
│       ├── product_photos/
│       │   ├── photo_1.jpg
│       │   ├── photo_2.jpg
│       │   └── ...
│       └── website_screenshot.png         # Auto-captured during analysis
│
└── generated/
    └── {postId}/
        ├── image_{hash}.png               # Generated image (naming uses content hash)
        ├── image_{hash2}.png              # Additional images (carousel — up to 7 slides, v1.9)
        ├── image_{hash3}.png              # ...through slide 7
        ├── video_{hash}.mp4               # Generated video clip (Veo 3.1)
        └── ...

# Image serving: /api/storage/serve/{blob_path} — backend proxy for local dev
# Export: blob.download_as_bytes() — direct GCS download for ZIP packaging
```

## 7.3 Cloud Storage Operations

```python
from google.cloud import storage
import uuid
from datetime import timedelta

storage_client = storage.Client()
BUCKET_NAME = f"{os.environ['GOOGLE_CLOUD_PROJECT']}-amplifi-assets"
bucket = storage_client.bucket(BUCKET_NAME)

async def upload_image_to_gcs(image_bytes: bytes, mime_type: str, 
                                post_id: str = None) -> str:
    """Upload a generated image to Cloud Storage and return a signed URL.
    
    Args:
        image_bytes: Raw image data from Gemini's inline_data
        mime_type: e.g., "image/png"
        post_id: Optional post ID for organized storage
    
    Returns: Signed URL valid for 7 days
    """
    if not post_id:
        post_id = str(uuid.uuid4())
    
    blob_path = f"generated/{post_id}/image_{uuid.uuid4().hex[:8]}.png"
    blob = bucket.blob(blob_path)
    
    blob.upload_from_string(image_bytes, content_type=mime_type)
    
    # Generate signed URL (7-day expiry)
    signed_url = blob.generate_signed_url(
        expiration=timedelta(days=7),
        method="GET"
    )
    
    return signed_url

async def upload_brand_asset(brand_id: str, file_bytes: bytes, 
                              filename: str, mime_type: str) -> str:
    """Upload a user's brand asset (logo, product photo)."""
    blob_path = f"brands/{brand_id}/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(file_bytes, content_type=mime_type)
    return f"gs://{BUCKET_NAME}/{blob_path}"
```

---

# 8. Interleaved Output: Deep Dive

## 8.1 How It Works

The Gemini API's interleaved output generates text and images in a single `generateContent` call. The response contains an ordered list of `Part` objects that alternate between `text` parts and `inline_data` parts (raw image bytes).

```python
# Actual API call
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents="Create an Instagram post for a bakery's fresh sourdough bread. "
             "Include a warm, inviting caption and generate a matching product image.",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"]
    )
)

# Response structure
# response.candidates[0].content.parts = [
#   Part(text="Rise and shine! Our signature sourdough is fresh out of the oven..."),
#   Part(inline_data=InlineData(mime_type="image/png", data=b'\x89PNG...')),
#   Part(text="#sourdough #freshbread #artisanbakery #morningroutine #bakerylife"),
# ]
```

## 8.2 Response Parsing

```python
from dataclasses import dataclass

@dataclass
class GeneratedPost:
    caption: str
    image_urls: list[str]
    hashtags: str
    raw_text_parts: list[str]

async def parse_interleaved_response(response, post_id: str) -> GeneratedPost:
    """Parse interleaved text + image response into structured post data."""
    
    text_parts = []
    image_urls = []
    
    for part in response.candidates[0].content.parts:
        if part.text:
            text_parts.append(part.text.strip())
        elif part.inline_data:
            url = await upload_image_to_gcs(
                part.inline_data.data,
                part.inline_data.mime_type,
                post_id=post_id
            )
            image_urls.append(url)
    
    # Heuristic: first text part = caption, last text part containing # = hashtags
    caption = text_parts[0] if text_parts else ""
    hashtags = ""
    for t in reversed(text_parts):
        if "#" in t:
            hashtags = t
            break
    
    return GeneratedPost(
        caption=caption,
        image_urls=image_urls,
        hashtags=hashtags,
        raw_text_parts=text_parts
    )
```

## 8.3 Budget Management

```python
# Image generation cost tracking
IMAGE_COST_TOKENS = 1290        # Tokens per generated image
TOKEN_COST_PER_MILLION = 30.0   # $30 per 1M output tokens
COST_PER_IMAGE = IMAGE_COST_TOKENS * TOKEN_COST_PER_MILLION / 1_000_000  # ~$0.039
COST_PER_VIDEO_FAST = 0.15 * 8  # $0.15/sec × 8 sec = $1.20 per clip (Veo 3.1 Fast)
COST_PER_VIDEO_STD = 0.40 * 8   # $0.40/sec × 8 sec = $3.20 per clip (Veo 3.1 Standard)
TOTAL_CREDIT = 100.0            # $100 Google Cloud credit

# Budget allocation (updated to include video)
IMAGE_BUDGET = 70.0             # $70 for images (~1,795 images)
VIDEO_BUDGET = 30.0             # $30 for videos (~25 Fast clips or ~9 Standard)
MAX_IMAGES = int(IMAGE_BUDGET / COST_PER_IMAGE)
MAX_VIDEOS_FAST = int(VIDEO_BUDGET / COST_PER_VIDEO_FAST)

class BudgetTracker:
    """Track image AND video generation costs against $100 credit.

    v1.9: Rewritten for Firestore persistence. All state is stored in the
    _system/budget document. All methods are async. Reads/writes go through
    Firestore on every call, ensuring correctness across Cloud Run cold starts
    and auto-scaling instances (no in-memory state that resets on scale-down).

    Firestore document: _system/budget
    Fields: images_generated, videos_generated, image_cost, video_cost, updated_at
    """

    BUDGET_DOC = "_system/budget"

    async def _read_budget(self) -> dict:
        """Read current budget state from Firestore."""
        doc = await firestore_client.get_document(self.BUDGET_DOC)
        return doc or {"images_generated": 0, "videos_generated": 0,
                       "image_cost": 0.0, "video_cost": 0.0}

    async def can_generate_image(self) -> bool:
        budget = await self._read_budget()
        total = budget["image_cost"] + budget["video_cost"]
        return total < (TOTAL_CREDIT * 0.8)

    async def can_generate_video(self) -> bool:
        budget = await self._read_budget()
        total = budget["image_cost"] + budget["video_cost"]
        return total + COST_PER_VIDEO_FAST < (TOTAL_CREDIT * 0.8)

    async def record_image(self, num_images: int = 1):
        """Atomically increment image count and cost in Firestore.
        Emits structured metric log for Cloud Monitoring."""
        await firestore_client.increment_budget(
            self.BUDGET_DOC,
            {"images_generated": num_images,
             "image_cost": num_images * COST_PER_IMAGE}
        )
        logger.info("budget_record", extra={
            "metric_name": "budget_record",
            "record_type": "image",
            "count": num_images,
            "cost": num_images * COST_PER_IMAGE,
        })

    async def record_video(self, tier: str = "fast"):
        """Atomically increment video count and cost in Firestore.
        Emits structured metric log for Cloud Monitoring."""
        cost = COST_PER_VIDEO_FAST if tier == "fast" else COST_PER_VIDEO_STD
        await firestore_client.increment_budget(
            self.BUDGET_DOC,
            {"videos_generated": 1, "video_cost": cost}
        )
        logger.info("budget_record", extra={
            "metric_name": "budget_record",
            "record_type": "video",
            "tier": tier,
            "cost": cost,
        })

    async def get_remaining(self) -> dict:
        budget = await self._read_budget()
        total = budget["image_cost"] + budget["video_cost"]
        return {
            "images_generated": budget["images_generated"],
            "videos_generated": budget["videos_generated"],
            "image_cost": f"${budget['image_cost']:.2f}",
            "video_cost": f"${budget['video_cost']:.2f}",
            "total_cost": f"${total:.2f}",
            "budget_remaining": f"${TOTAL_CREDIT - total:.2f}",
        }
```

## 8.4 Video Generation via Veo 3.1 (P1)

Video generation is a **separate, additive flow** that builds on top of the P0 interleaved image output. It is NOT part of the SSE generation stream. It has its own endpoint, its own UI button, and its own async lifecycle.

**Platform-aware display:** On text-first platforms (LinkedIn, X, Twitter, Facebook), the video section defaults to a collapsed pill ("🎬 Video Clip (not typical for this platform) ›") to reduce visual noise. `TEXT_PLATFORMS = new Set(['linkedin', 'x', 'twitter', 'facebook'])` controls this behavior. `videoExpanded` state (default `false`) toggles between collapsed pill and full section. State resets to collapsed on every `postId` change. Video-first platforms (Instagram, TikTok, Reels) always show the full expanded section.

### 8.4.1 Architecture Decision

The interleaved output hero image becomes Veo's **first frame**, ensuring visual continuity between the static post and the video clip. This is the key design insight: the image and video share the same visual DNA because one literally starts from the other.

```
Interleaved Output (P0)              Veo Video (P1)
┌─────────────────────┐              ┌─────────────────────┐
│ Caption text         │              │                     │
│ ┌─────────────────┐ │   first      │  ┌─────────────┐   │
│ │  Hero Image     │─┼───frame────▶ │  │  8-sec MP4  │   │
│ │  (generated)    │ │              │  │  720p/1080p  │   │
│ └─────────────────┘ │              │  │  with audio  │   │
│ Hashtags             │              │  └─────────────┘   │
└─────────────────────┘              └─────────────────────┘
     SSE (streaming)                    REST (async poll)
     ~10-20 sec                         ~2-3 min
```

### 8.4.2 Veo API Integration

```python
from google import genai
from google.genai import types
import asyncio

client = genai.Client()

async def generate_video(
    hero_image_bytes: bytes,
    caption: str,
    brand_profile: dict,
    platform: str,
    tier: str = "fast"
) -> dict:
    """Generate an 8-second video clip from a hero image using Veo 3.1.
    
    Args:
        hero_image_bytes: Raw bytes of the interleaved-output hero image
        caption: Post caption (used to build video prompt)
        brand_profile: Brand profile for style guidance
        platform: Target platform (determines aspect ratio)
        tier: "fast" ($1.20/clip) or "standard" ($3.20/clip)
    
    Returns: { video_url: str, duration_seconds: int, status: str }
    """
    
    # Select model based on tier
    model = "veo-3.1-fast-generate-preview" if tier == "fast" else "veo-3.1-generate-preview"
    
    # Determine aspect ratio from platform
    aspect_ratio = "9:16" if platform in ["instagram", "tiktok"] else "16:9"
    
    # Build cinematic video prompt from caption + brand context
    video_prompt = f"""Create a smooth, professional social media video for {brand_profile['business_name']}.

BRAND STYLE: {brand_profile.get('visual_style', 'clean, modern, professional')}
BRAND TONE: {brand_profile.get('tone', 'professional')}
POST CAPTION CONTEXT: {caption[:200]}

VIDEO DIRECTION:
- Start from the provided hero image as the first frame
- Add subtle, elegant motion: slow zoom, parallax, product reveal, or lifestyle movement
- Maintain the color palette and mood of the starting image throughout
- NO text overlays, NO watermarks, NO logos
- The motion should feel cinematic and intentional, not stock-footage generic
- Audio: ambient, brand-appropriate background music or subtle sound design
"""
    
    # Convert hero image bytes to Veo-compatible image
    hero_image = types.Image.from_bytes(data=hero_image_bytes, mime_type="image/png")
    
    # Start async video generation
    operation = client.models.generate_videos(
        model=model,
        prompt=video_prompt,
        image=hero_image,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            number_of_videos=1,
        ),
    )
    
    # Poll for completion (2-3 min typical)
    while not operation.done:
        await asyncio.sleep(10)
        operation = client.operations.get(operation)
    
    # Extract video
    generated_video = operation.response.generated_videos[0]
    video_bytes = generated_video.video.video_bytes
    
    # Upload to Cloud Storage
    video_url = await upload_video_to_gcs(video_bytes, post_id=None)
    
    return {
        "video_url": video_url,
        "duration_seconds": 8,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "status": "complete",
    }


async def upload_video_to_gcs(video_bytes: bytes, post_id: str) -> str:
    """Upload generated MP4 to Cloud Storage and return signed URL."""
    blob_path = f"generated/{post_id}/video_{uuid.uuid4().hex[:8]}.mp4"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(video_bytes, content_type="video/mp4")
    
    signed_url = blob.generate_signed_url(
        expiration=timedelta(days=7),
        method="GET"
    )
    return signed_url
```

### 8.4.3 REST Endpoint

```python
@app.post("/api/posts/{post_id}/generate-video")
async def generate_video_endpoint(post_id: str, tier: str = "fast"):
    """Start async video generation for a post that already has a hero image.
    
    Returns immediately with a job_id. Client polls for completion.
    """
    
    # Budget check
    if not budget_tracker.can_generate_video():
        return JSONResponse(
            status_code=429,
            content={"error": "Video generation budget exhausted",
                     "budget": budget_tracker.get_status()}
        )
    
    # Load post data
    post = await firestore_client.get_post(post_id)
    brand = await firestore_client.get_brand(post["brand_id"])
    
    if not post.get("image_urls"):
        return JSONResponse(
            status_code=400,
            content={"error": "Post must have a hero image before video generation"}
        )
    
    # Download hero image from GCS
    hero_image_bytes = await download_from_gcs(post["image_urls"][0])
    
    # Create job record in Firestore
    job_id = await firestore_client.create_video_job(post_id, tier)
    
    # Start generation in background
    asyncio.create_task(
        _run_video_generation(job_id, post_id, hero_image_bytes, post, brand, tier)
    )
    
    return {"job_id": job_id, "status": "processing", "estimated_seconds": 150}


async def _run_video_generation(job_id, post_id, hero_image_bytes, post, brand, tier):
    """Background task for video generation."""
    try:
        await firestore_client.update_video_job(job_id, "generating")
        
        result = await generate_video(
            hero_image_bytes=hero_image_bytes,
            caption=post["caption"],
            brand_profile=brand,
            platform=post["platform"],
            tier=tier,
        )
        
        # Save video URL to post
        await firestore_client.update_post_video(post_id, result["video_url"])
        await firestore_client.update_video_job(job_id, "complete", result)
        
        # Track budget
        budget_tracker.record_video(tier)
        
    except Exception as e:
        logger.error("video_generation_error", extra={
            "job_id": job_id, "post_id": post_id, "error": str(e)
        })
        await firestore_client.update_video_job(job_id, "failed", {"error": str(e)})


@app.get("/api/video-jobs/{job_id}")
async def get_video_job_status(job_id: str):
    """Poll video generation status."""
    job = await firestore_client.get_video_job(job_id)
    return job
```

### 8.4.4 Frontend Integration

```typescript
// useVideoGeneration.ts
function useVideoGeneration(postId: string, existingVideoUrl?: string | null) {
  const [status, setStatus] = useState<"idle" | "generating" | "complete" | "error">(
    existingVideoUrl ? "complete" : "idle"
  );
  const [videoUrl, setVideoUrl] = useState<string | null>(existingVideoUrl || null);
  const [progress, setProgress] = useState(existingVideoUrl ? 100 : 0);
  
  const generateVideo = useCallback(async (tier: "fast" | "standard" = "fast") => {
    setStatus("generating");
    setProgress(0);
    
    // Start generation
    const res = await fetch(`/api/posts/${postId}/generate-video?tier=${tier}`, {
      method: "POST"
    });
    const { job_id, estimated_seconds } = await res.json();
    
    // Poll for completion
    const startTime = Date.now();
    const pollInterval = setInterval(async () => {
      const statusRes = await fetch(`/api/video-jobs/${job_id}`);
      const job = await statusRes.json();
      
      // Update progress estimate
      const elapsed = (Date.now() - startTime) / 1000;
      setProgress(Math.min(95, (elapsed / estimated_seconds) * 100));
      
      if (job.status === "complete") {
        clearInterval(pollInterval);
        setVideoUrl(job.result.video_url);
        setProgress(100);
        setStatus("complete");
      } else if (job.status === "failed") {
        clearInterval(pollInterval);
        setStatus("error");
      }
    }, 5000);  // Poll every 5 seconds
  }, [postId]);
  
  return { status, videoUrl, progress, generateVideo };
}
```

```typescript
// VideoGenerateButton.tsx — appears on DayCards for reel/story/tiktok content types
function VideoGenerateButton({ postId, contentType }: Props) {
  const { status, videoUrl, progress, generateVideo } = useVideoGeneration(postId);
  
  // Only show for video-eligible content types
  if (!["reel", "story", "tiktok"].includes(contentType)) return null;
  
  return (
    <div className="video-generation">
      {status === "idle" && (
        <button 
          onClick={() => generateVideo("fast")}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg flex items-center gap-2"
        >
          <VideoIcon size={16} /> Generate Video Clip
        </button>
      )}
      
      {status === "generating" && (
        <div className="flex items-center gap-3">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-purple-600 h-2 rounded-full transition-all" 
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
        </div>
      )}
      
      {status === "complete" && videoUrl && (
        <video 
          src={videoUrl} 
          controls 
          className="rounded-lg shadow-lg w-full"
          poster={/* hero image URL */}
        />
      )}
      
      {status === "error" && (
        <button onClick={() => generateVideo("fast")} className="text-red-500">
          Video failed — Retry
        </button>
      )}
    </div>
  );
}
```

---

# 9. Frontend Architecture

## 9.1 React Component Tree

```
App (React Router)
├── NavBar (sticky top bar)
│   ├── Logo + "Amplispark" brand (click → /)
│   ├── StaticLinks (Home | My Brands or Get Started — dynamic based on auth)
│   ├── ExportLink (shown when activeBrandId is detected from URL)
│   └── AccountDropdown (signed in: profile photo + name + sign out | not signed in: "Sign in" button)
│
├── LandingPage (/) — pure marketing page, no user state
│   ├── HeroSection (gradient headline, value prop, dual CTAs)
│   ├── PlatformStrip (Instagram, LinkedIn, X, Facebook badges)
│   ├── HowItWorks (3-step cards: Describe → Strategy → Generate)
│   ├── ProductPreview (mini calendar preview with pillar tags)
│   ├── FeaturesGrid (2×3: brand-aware, multi-platform, BYOP, video, pillars, events)
│   └── FooterCTA (repeat start button — triggers Google Sign-In then navigates to /brands)
│
├── BrandsPage (/brands) — requires sign-in, redirects to / if not authenticated
│   ├── CreateBrandCard (prominent CTA: "+ New Brand" → /onboard)
│   └── YourBrands (paginated list, 5 per page)
│       ├── BrandCard[] (avatar initial, name, industry, status badge, click → /dashboard/:id)
│       ├── EmptyState ("No brands yet — create your first brand")
│       └── Pagination (Previous | Page X of Y | Next)
│
├── ProtectedRoute — v1.9 auth wrapper component in App.tsx
│   │   Wraps all authenticated routes (/brands, /onboard, /dashboard/*)
│   │   Redirects to / (landing page) if user is not signed in
│   │
├── OnboardPage (/onboard) — thin shell, delegates to OnboardWizard
│   │   v1.9 onboarding guard: checks for existing brands, redirects to /brands
│   │   ?new=true query param bypasses the guard (for "add another brand" flow)
│   └── OnboardWizard (732 lines, 3-step deferred-creation flow)
│       ├── Step 1: "Tell us about your brand"
│       │   ├── URLInput (website URL — hidden in no-website mode)
│       │   ├── DescriptionInput (free-text textarea, min 20 chars, always visible)
│       │   └── NoWebsiteToggle ("No website? Describe your business instead →")
│       ├── Step 2: "Upload brand assets"
│       │   └── AssetUploadZone (optional drag-drop for images/PDFs, max 3 files)
│       │       └── UploadedFileList (filename, type icon, remove button)
│       ├── Step 3: "Analyzing your brand"
│       │   └── AnalysisProgress (step-by-step with adaptive steps based on mode)
│       │       └── FinalizingRow (pulsing "Finalizing your brand profile..." after all steps complete)
│       ├── useWizardState (85 lines — state machine for 3-step flow)
│       │   ├── SessionStorage persistence for text fields across refresh
│       │   └── 2-minute timeout safety net (auto-error if analysis hangs)
│       └── Deferred creation: brand created only on final step
│           └── API chain: createBrand → updateBrand → uploadBrandAsset → setBrandLogo → analyzeBrand
│
├── DashboardPage (/dashboard/{brandId})
│   ├── BrandProfileCard (editable brand profile summary — inline save with loading state and error feedback)
│   │   ├── InferredBusinessType (AI-inferred from description, editable)
│   │   ├── VoiceCoachButton ("🗣️ Voice Coach" — opens Gemini Live multi-turn session)
│   │   ├── ColorSwatches (clickable hex colors)
│   │   ├── ToneChips (editable tone adjectives)
│   │   ├── ImageStyleDirective (P1 — shows visual identity seed, editable)
│   │   │   └── "warm earth tones, soft natural lighting, minimalist..."
│   │   ├── CaptionStyleDirective (P1 — shows writing rhythm guide, editable)
│   │   │   └── "Open with hook under 10 words. Personal story second..."
│   │   ├── AudienceDescription
│   │   └── EditButton → BrandEditModal
│   │
│   ├── TabBar (Calendar | Posts | Export — default: Calendar)
│   │
│   ├── [Tab: Calendar]
│   ├── ContentCalendar
│   │   ├── CalendarHeader (week selector, "Generate All" button, ClearPlanButton with confirm dialog)
│   │   ├── EventsInput (P1 — "What's happening this week?" free-text area, disabled during brand analysis)
│   │   │   └── Placeholder: "launching lavender croissant Tuesday, farmer's market Saturday..."
│   │   ├── CalendarProgress (6-step animated sequence: understanding brand → mapping events → building pillars → scheduling platform mix → crafting repurposing chains → finalizing)
│   │   ├── PillarSummary (P1 — shows 1-2 pillar themes with derivative count + event/generated badge)
│   │   └── DayCard[7]
│   │       ├── DayLabel ("Monday")
│   │       ├── PlatformBadge (Instagram icon)
│   │       ├── PillarTag (P1 — "Pillar: Pricing Strategy" or "Standalone")
│   │       ├── DerivativeType (P1 — "Original" | "X Thread" | "Carousel" | etc.)
│   │       ├── ThemePreview (truncated theme text)
│   │       ├── PhotoDropZone (P1 BYOP — "Drop your photo here" / uploaded thumbnail)
│   │       ├── StatusBadge (planned / generated / approved)
│   │       └── GenerateButton → opens PostGenerator
│   │
│   ├── [Tab: Posts]
│   ├── PostLibrary (grid of all generated posts — auto-polls every 8s while generating, defaultFilter prop)
│   │   ├── FilterTabs (All / ✓ Approved / Ready / Generating / Failed — with counts)
│   │   ├── HeaderRow
│   │   │   ├── RefreshButton
│   │   │   ├── CopyAllButton ("📋 Copy All" / "✓ Copied N" — bulk clipboard export)
│   │   │   └── ExportAllButton (ZIP download — bulk plan ZIP with all media)
│   │   └── PostCard[]
│   │       ├── ImageThumbnail (carousel: shows first slide with slide count badge)
│   │       ├── VideoPlayer (if video generated, P1 — collapsible on text-first platforms)
│   │       ├── CaptionPreview
│   │       ├── PlatformBadge
│   │       ├── ReviewScore (1-5 stars, cached in post document)
│   │       ├── ApprovedBadge (green "Approved" — shown when post.approved === true)
│   │       ├── ApproveButton ("✓ Approve" / "↩ Unapprove" toggle)
│   │       ├── DismissButton (× — shown on generating/failed posts for local removal)
│   │       └── ActionButtons (copy caption, export ZIP, view)
│   │
│   └── [Tab: Export]
│       └── ExportPanel (Copy All clipboard, per-post ZIP, bulk plan ZIP — inline, not separate page)
│
├── GeneratePage (/generate/{planId}/{dayIndex})
│   ├── PageSubtitle ("Day N · Platform · Content Theme" — human-readable context)
│   ├── DayBriefPanel (theme, platform, directions — editable)
│   │   └── PillarContext (P1 — shows pillar key message if this is a derivative)
│   │
│   ├── GenerationStream ⭐ (the "wow" moment)
│   │   ├── CaptionArea (text streams in progressively)
│   │   ├── ImageArea
│   │   │   ├── Mode A (single image): SkeletonLoader → AI-generated image materializes
│   │   │   ├── Mode A-Carousel (3 slides): CarouselViewer with arrows, dots, slide counter
│   │   │   │   ├── LeftArrow / RightArrow (navigate slides)
│   │   │   │   ├── DotIndicators (1 dot per slide, active dot highlighted)
│   │   │   │   └── SlideCounter ("1 / 3")
│   │   │   ├── Mode B (BYOP): User photo displayed immediately, caption streams around it
│   │   │   └── Fallback: "Retrying image generation..." status → fallback image materializes
│   │   ├── HashtagArea (tags appear last)
│   │   └── GenerationStatus ("Crafting your caption..." → "done")
│   │
│   ├── VideoSection (P1 — collapsed pill on text-first platforms, expanded on video platforms)
│   │   ├── CollapsedPill (LinkedIn/X/Facebook: "🎬 Video Clip (not typical for this platform) ›")
│   │   ├── GenerateButton ("Generate Video Clip" — visible when expanded)
│   │   ├── ProgressBar (0-100% during async generation)
│   │   └── VideoPlayer (plays MP4 on completion)
│   │
│   ├── ReviewPanel (auto-triggers on mount once generation completes — sole approval path)
│   │   ├── ScoreCircle (brand alignment score with badge)
│   │   ├── EngagementPrediction (bars: hook strength, relevance, CTA clarity, platform fit)
│   │   ├── StrengthsList (green ✓ checkmarks)
│   │   ├── ImprovementsList (yellow → arrows with suggestions)
│   │   ├── UseThisCaptionButton (copy-to-clipboard — shown when AI proposes a revised caption)
│   │   ├── ApproveButton (sole location for post approval)
│   │   └── NextDayCTA ("Next Day →" — navigates to next day in plan after review)
│   │
│   └── ActionBar
│       ├── RegenerateButton
│       ├── DownloadImageButton
│       └── CopyCaptionButton
│
├── ExportPage (/export/{brandId}?plan_id={planId} — linked from NavBar when plan is active)
│   ├── PageSubtitle ("Copy captions to clipboard, download individual posts, or export as ZIP")
│   └── PostLibrary (reused — defaultFilter="approved", CopyAllButton, filter tabs, PostCard grid)
│       // Export is also integrated into Dashboard's Export tab — no separate page required
│
└── GuidedTour (436 lines — 11-step interactive product tour, rendered at app root)
    ├── SVG spotlight overlay (full-viewport mask with cutout around target element)
    ├── Tooltip (positioned relative to spotlight, step counter, Next/Back/Skip controls)
    ├── useTour (84 lines — tour step state machine)
    │   ├── data-tour-id attribute targeting (querySelector("[data-tour-id='...']"))
    │   ├── onBeforeShow callback (e.g., auto-switch dashboard tab before highlighting)
    │   ├── rAF-throttled scroll/resize handlers for responsive repositioning
    │   ├── Async skip for missing DOM targets with loop prevention
    │   └── Per-brand localStorage completion tracking (tour not re-shown once finished)
    └── Tour triggers on first dashboard visit for a brand (if not previously completed)
```

## 9.2 Key UI Interactions

### Generation Stream (SSE Consumer)

```typescript
// PostGenerator.tsx
function PostGenerator({ planId, dayIndex }: Props) {
  const { caption, imageUrl, imageUrls, imageSource, hashtags, review, error, status, generate } =
    usePostGeneration(planId, dayIndex);
  const [carouselIndex, setCarouselIndex] = useState(0);
  const isCarousel = imageUrls.length > 1;
  
  return (
    <div className="generation-stream">
      {/* Caption area — text streams in character by character */}
      <div className="caption-area">
        {status === "generating" && !caption && (
          <div className="typing-indicator">
            {imageSource === "user_upload" 
              ? "Analyzing your photo and crafting a caption..." 
              : "Crafting your caption..."}
          </div>
        )}
        {caption && (
          <TypewriterText text={caption} speed={20} />
        )}
      </div>
      
      {/* Image area — carousel, single image, or BYOP */}
      <div className="image-area">
        {/* Skeleton while generating */}
        {status === "generating" && !imageUrl && imageSource !== "user_upload" && (
          <SkeletonImage className="animate-pulse bg-gray-200 rounded-lg w-full aspect-square" />
        )}
        {/* Carousel: multiple images with navigation */}
        {isCarousel && (
          <div className="relative">
            <img
              src={imageUrls[carouselIndex]}
              alt={`Slide ${carouselIndex + 1}`}
              className="rounded-lg shadow-lg w-full animate-fade-in"
            />
            <button onClick={() => setCarouselIndex(i => Math.max(0, i - 1))}
              className="absolute left-2 top-1/2 -translate-y-1/2">←</button>
            <button onClick={() => setCarouselIndex(i => Math.min(imageUrls.length - 1, i + 1))}
              className="absolute right-2 top-1/2 -translate-y-1/2">→</button>
            <div className="text-center mt-2 text-sm text-gray-500">
              {carouselIndex + 1} / {imageUrls.length}
            </div>
            <div className="flex justify-center gap-1 mt-1">
              {imageUrls.map((_, i) => (
                <span key={i} className={`w-2 h-2 rounded-full ${i === carouselIndex ? 'bg-purple-600' : 'bg-gray-300'}`} />
              ))}
            </div>
          </div>
        )}
        {/* Single image (non-carousel) */}
        {!isCarousel && imageUrl && (
          <div className="relative">
            <img
              src={imageUrl}
              alt="Generated content"
              className="rounded-lg shadow-lg w-full animate-fade-in"
            />
            {imageSource === "user_upload" && (
              <span className="absolute top-2 right-2 bg-blue-500 text-white text-xs px-2 py-1 rounded">
                Your Photo
              </span>
            )}
          </div>
        )}
        {/* Image generation failed — show retry option */}
        {error?.code === "IMAGE_GEN_FAILED" && !imageUrl && (
          <div className="image-error bg-amber-50 border border-amber-200 rounded-lg p-4 text-center">
            <p className="text-amber-800">Image generation failed. Caption was saved.</p>
            <button onClick={generate} className="mt-2 px-4 py-2 bg-amber-500 text-white rounded">
              Retry Image
            </button>
          </div>
        )}
      </div>
      
      {/* General error state */}
      {status === "error" && (
        <div className="error-state bg-red-50 border border-red-200 rounded-lg p-4 text-center">
          <p className="text-red-800">{error?.message || "Generation failed"}</p>
          <button onClick={generate} className="mt-2 px-4 py-2 bg-red-500 text-white rounded">
            Try Again
          </button>
        </div>
      )}
      
      {/* Hashtags */}
      {hashtags && (
        <div className="hashtags text-blue-500 mt-4">
          {hashtags.split(/\s+/).map(tag => (
            <span key={tag} className="mr-2">{tag}</span>
          ))}
        </div>
      )}
      
      {/* Review panel */}
      {review && <ReviewPanel review={review} />}
      
      {/* Action buttons */}
      {status === "done" && (
        <ActionBar postId={...} caption={caption} imageUrl={imageUrl} />
      )}
    </div>
  );
}
```

## 9.3 New User Experience (NUX) Design

The NUX consists of two complementary systems: the **Onboarding Wizard** (brand creation) and the **Guided Tour** (dashboard orientation). Together they form a deferred-creation funnel: the wizard collects all inputs before touching the backend, and the tour teaches the dashboard after the brand exists.

### 9.3.1 Onboarding Wizard (OnboardWizard.tsx, useWizardState.ts)

**Pattern: Deferred Creation.** Unlike the original single-page onboard flow, the 3-step wizard collects all user input (URL, description, assets) across multiple screens before making any API calls. The brand document is created only when the user reaches the final analysis step. This eliminates orphaned brand records from abandoned onboarding.

**Step progression:**

| Step | Title | User Action | Backend Calls |
|------|-------|------------|---------------|
| 1 | Tell us about your brand | Enter URL and/or description | None |
| 2 | Upload brand assets | Drag-drop images/PDFs (optional) | None |
| 3 | Analyzing your brand | Wait for analysis pipeline | `createBrand` → `updateBrand` → `uploadBrandAsset` (per file) → `setBrandLogo` → `analyzeBrand` |

**State management (`useWizardState.ts`, 85 lines):**
- Tracks current step, input values, validation state, and analysis progress.
- Text fields (URL, description) are persisted to `sessionStorage` on every change, surviving accidental page refreshes. Asset file references are not persisted (File objects are not serializable).
- A 2-minute timeout safety net fires if the analysis step does not complete, surfacing an error state rather than leaving the user on an infinite spinner.

**Key design decisions:**
- No plan generation in the wizard. Plan generation was moved to the dashboard to keep onboarding focused on brand creation. Users land on their new dashboard with a clear "Generate Calendar" CTA.
- `OnboardPage.tsx` was simplified to a thin shell that renders `<OnboardWizard />` and handles the post-completion redirect to `/dashboard/:id`.
- **Onboarding guard (v1.9):** `OnboardPage` checks whether the user already has brands. If brands exist, the user is redirected to `/brands` instead of the wizard — preventing accidental re-onboarding. The `?new=true` query parameter bypasses this guard, used by the "Add Another Brand" button on the Brands page.

### 9.3.2 Guided Tour (GuidedTour.tsx, useTour.ts)

**Pattern: SVG Spotlight Overlay.** The tour renders a full-viewport SVG with a `<mask>` element that creates a darkened overlay with a transparent cutout around the target element. This approach avoids z-index wars with the existing UI — the overlay is a single SVG layer, and the spotlight is a mask hole, not a repositioned element.

**11 tour steps** cover the core dashboard workflow: brand profile, calendar tab, event input, day card, generate button, posts tab, post card, approve button, export tab, voice coach, and edit brand. Steps are defined declaratively with `targetId`, `title`, `body`, `placement`, and optional `onBeforeShow`.

**Targeting pattern:**
- Each tourable element in the dashboard has a `data-tour-id` attribute (e.g., `data-tour-id="calendar-tab"`).
- `useTour` uses `document.querySelector('[data-tour-id="..."]')` to locate targets at render time, not at mount time. This handles elements that appear conditionally (e.g., after tab switch).
- If a target element is not found in the DOM, the step is skipped asynchronously with a loop counter to prevent infinite skip cycles if multiple consecutive targets are missing.

**Tab auto-switching:**
- Steps targeting elements on non-active tabs provide an `onBeforeShow` callback that programmatically switches the dashboard tab (e.g., switch to "Posts" before highlighting the post card). The tour waits one animation frame after the callback before measuring target position.

**Scroll and resize handling:**
- `scroll` and `resize` event listeners recompute spotlight position and tooltip placement.
- Both handlers are throttled via `requestAnimationFrame` to avoid layout thrashing.

**Completion tracking:**
- Tour completion is stored in `localStorage` keyed by brand ID (`tour_completed_{brandId}`).
- The tour auto-triggers on the first dashboard visit for a given brand. It is not shown again once marked complete (via finishing all steps or clicking "Skip Tour").

---

# 10. Deployment & Infrastructure

## 10.1 Deployment Architecture

Amplispark deploys as a single Docker container on Google Cloud Run. The multi-stage Dockerfile builds the React frontend (TypeScript + Vite 7) inside the image, then serves the compiled static assets alongside the FastAPI backend. This same-origin strategy eliminates CORS complexity in production — all requests hit a single Cloud Run URL.

**Production topology:**

```
Internet → Cloud Run :8080
             ├── /api/*       → FastAPI routes (REST + SSE streams)
             ├── /health      → Health check endpoint
             └── /*           → frontend/dist/ (compiled React SPA)
```

**Resource allocation rationale:**
- **2 CPU / 2 GiB RAM** — Gemini interleaved output (text + image) responses can exceed 1 MB per post; a 7-day plan with carousel images requires buffering multiple concurrent generation results.
- **300s timeout** — SSE content generation streams run 2-3 minutes for a full weekly calendar (Brand Analyst → Strategy → 7× Content Creator → Review per post).
- **0-10 instances, scale-to-zero** — Hackathon/demo usage is bursty; no idle cost when unused.

## 10.2 Docker Configuration

The Dockerfile installs `ffmpeg` for video processing (Veo 3.1 clips) and accepts Firebase config as build-time arguments. Vite bakes `VITE_*` environment variables into the JavaScript bundle at build time — they cannot be injected at runtime.

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ffmpeg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY frontend/ ./frontend/

# Firebase config must be provided at build time (Vite inlines VITE_* vars)
ARG VITE_FIREBASE_API_KEY=""
ARG VITE_FIREBASE_AUTH_DOMAIN=""
ARG VITE_FIREBASE_PROJECT_ID=""
ARG VITE_FIREBASE_STORAGE_BUCKET=""
ARG VITE_FIREBASE_MESSAGING_SENDER_ID=""
ARG VITE_FIREBASE_APP_ID=""

ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID

RUN cd frontend && npm ci && npm run build

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8080"]
```

Frontend static files are served by FastAPI's SPA catch-all route in `server.py`. The catch-all includes path traversal prevention (rejects `..` sequences) and serves `index.html` for all non-API, non-static paths:

```python
# server.py — SPA catch-all with security
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if ".." in full_path:
        raise HTTPException(400, "Invalid path")
    static_path = os.path.join(frontend_dist, full_path)
    if os.path.isfile(static_path):
        return FileResponse(static_path)
    return FileResponse(os.path.join(frontend_dist, "index.html"))
```

## 10.3 Terraform Infrastructure-as-Code

The `terraform/` directory provisions the complete GCP infrastructure with a single `terraform apply`. This includes API enablement, data stores, container registry, and the Cloud Run service with a post-deploy CORS auto-configuration step.

**Resources provisioned:**

| Resource | Purpose |
|----------|---------|
| `google_project_service.apis` (×6) | Enable Cloud Run, Cloud Build, Firestore, Storage, AI Platform, Artifact Registry |
| `google_firestore_database.default` | Brand profiles, content plans, posts — Firestore Native mode |
| `google_storage_bucket.assets` | Generated images, videos, uploaded brand assets — CORS-enabled |
| `google_artifact_registry_repository.docker` | Docker image repository for Cloud Build pushes |
| `google_cloud_run_v2_service.amplifi` | Application service — 2 CPU, 2 GiB, 300s timeout, 0-10 instances |
| `google_cloud_run_v2_service_iam_member.public` | Unauthenticated access (public-facing demo) |
| `null_resource.set_cors` | Post-deploy provisioner — auto-sets `CORS_ORIGINS` to the Cloud Run URL |

**CORS auto-configuration:** The Cloud Run URL is not known until the service is created. A `null_resource` with a `local-exec` provisioner runs `gcloud run services update` after deploy to set `CORS_ORIGINS` to the service URI, eliminating the manual post-deploy step.

**Terraform variables** (`variables.tf`):

| Variable | Type | Description |
|----------|------|-------------|
| `project_id` | `string` | GCP project ID |
| `region` | `string` | GCP region (default: `us-central1`) |
| `gemini_api_key` | `string` (sensitive) | Gemini API key from AI Studio |

**Outputs:**

| Output | Description |
|--------|-------------|
| `service_url` | Cloud Run URL (CORS auto-configured) |
| `image_url` | Artifact Registry image path to push to |
| `bucket_name` | GCS bucket name for generated assets |
| `firestore_database` | Firestore database name |

## 10.4 Cloud Build CI/CD Pipeline

The CI/CD pipeline is defined in `cloudbuild.yaml` and triggered via `scripts/deploy.sh`. The deploy script reads config from `.env` (gitignored), validates required variables, and submits a Cloud Build job with substitutions.

**Pipeline steps:**

| Step | Action | Key Details |
|------|--------|-------------|
| 0. Test (v1.9) | Run pytest | `python:3.12-slim` image, `pip install -r requirements.txt`, `pytest backend/tests/` — blocks build on failure |
| 1. Docker Build | Build multi-stage image | Firebase `VITE_*` vars passed as `--build-arg` (baked into JS bundle by Vite) |
| 2. Push | Push to Artifact Registry | `{region}-docker.pkg.dev/{project}/amplifi/amplifi:latest` |
| 3. Deploy | Deploy to Cloud Run | Runtime env vars: `GOOGLE_API_KEY`, `CORS_ORIGINS`, `RESEND_API_KEY`, `NOTION_*`, `GEMINI_MODEL` |

**Usage:**
```bash
# One-command deploy (reads all config from .env)
./scripts/deploy.sh
```

The `deploy.sh` script:
1. Sources `.env` from project root
2. Validates required variables (`VITE_FIREBASE_*`, `GCP_PROJECT_ID`, `GOOGLE_API_KEY`)
3. Runs `gcloud builds submit` with all substitutions
4. Prints the live Cloud Run URL after deploy

**Build-time vs runtime environment variables:**
- **Build-time** (`--build-arg`): `VITE_FIREBASE_*` — baked into the JS bundle by Vite at `npm run build`. Cannot be changed after build. These configure Firebase Google Sign-In.
- **Runtime** (`--set-env-vars`): `GOOGLE_API_KEY`, `CORS_ORIGINS`, `RESEND_API_KEY`, `NOTION_*`, `GEMINI_MODEL` — read by the Python backend at startup via `os.environ`.

## 10.5 Environment Variables

**Runtime environment** (set on Cloud Run service):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | — | Gemini API key for all agents |
| `GCP_PROJECT_ID` | Yes | — | GCP project ID |
| `GCS_BUCKET_NAME` | Yes | — | Cloud Storage bucket for images/video |
| `CORS_ORIGINS` | Yes | `http://localhost:5173` | Comma-separated allowed origins |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Default Gemini model override |
| `RESEND_API_KEY` | No | `""` | Resend API key for email delivery (.ics calendar) |
| `NOTION_CLIENT_ID` | No | `""` | Notion OAuth client ID |
| `NOTION_CLIENT_SECRET` | No | `""` | Notion OAuth client secret |
| `NOTION_REDIRECT_URI` | No | `""` | Notion OAuth redirect URI (must match Cloud Run URL) |
| `TOKEN_ENCRYPT_KEY` | **Yes** (v1.9) | — | Fernet encryption key for OAuth token encryption at rest. **Mandatory** — app raises `RuntimeError` on startup if missing. Replaces optional `FERNET_KEY`. |

**Build-time environment** (Docker build args — baked into JS bundle):

| Variable | Description |
|----------|-------------|
| `VITE_FIREBASE_API_KEY` | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | Firebase app ID |

## 10.6 GCP Services & Free Tier

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| **Gemini API** | Brand analysis, content creation, review, voice coach | Generous free tier |
| **Cloud Firestore** | Brand profiles, content plans, posts | 1 GiB free |
| **Cloud Storage** | Generated images, videos, uploaded assets | 5 GB free |
| **Cloud Run** | Application hosting (serverless) | 2M requests/month free |
| **Cloud Build** | CI/CD image builds | 120 build-min/day free |
| **Artifact Registry** | Docker image storage | 500 MB free |

---

# 11. Repository Structure

```
amplifi-hackaton/
├── backend/
│   ├── server.py                  # FastAPI app (~80 lines — app setup + middleware + exception handler + router includes)
│   ├── middleware.py              # Firebase Auth middleware (verify_firebase_token, verify_brand_owner)
│   ├── middleware_logging.py      # v1.9: RequestContextMiddleware — structured JSON logging with contextvars
│   ├── clients.py                 # Singleton Gemini client (shared across all agents)
│   ├── gcs_utils.py               # Shared GCS URI parsing utilities
│   ├── constants.py               # Shared constants: PILLARS, DERIVATIVE_TYPES, PLATFORM_STRENGTHS,
│   │                              #   PILLAR_DESCRIPTIONS, PILLAR_NARRATIVES, scoring weights
│   ├── config.py                  # Environment variables
│   ├── platforms.py               # Platform Registry — 11 platforms + 4 derivative overrides, PlatformSpec
│   │                              #   + platform-specific scoring weights + structural modifier floors
│   │
│   ├── routers/                   # FastAPI routers (split from monolithic server.py)
│   │   ├── brands.py             # /api/brands/* — CRUD, analyze, upload, logo, claim
│   │   ├── plans.py              # /api/plans/* — calendar generation, day updates
│   │   ├── posts.py              # /api/posts/* — list, approve, regenerate
│   │   ├── generation.py         # /api/generate/* — SSE content generation stream
│   │   ├── media.py              # /api/storage/*, /api/export/* — GCS proxy, ZIP export
│   │   ├── integrations.py       # /api/brands/*/integrations/* — Notion OAuth, email, .ics
│   │   └── voice.py              # /api/voice/* — Gemini Live WebSocket proxy
│   │
│   ├── agents/
│   │   ├── brand_analyst.py       # Brand Analyst Agent + system prompt
│   │   ├── strategy_agent.py      # Strategy Agent + calendar generation (social proof tiers)
│   │   ├── content_creator.py     # Content Creator Agent (orchestrator — delegates to sub-modules)
│   │   ├── caption_pipeline.py    # Caption generation pipeline (extracted from content_creator.py)
│   │   ├── carousel_builder.py    # 7-slide concurrent carousel generation (v1.9: semaphore=7, all slides parallel)
│   │   ├── hashtag_engine.py      # Hashtag generation, sanitization, per-platform limits (extracted)
│   │   ├── quality_gates.py       # Pre/post-generation quality checks (extracted)
│   │   ├── image_prompt_builder.py # Platform-aware image prompt construction (extracted)
│   │   ├── video_creator.py       # Video Creator (Veo 3.1 integration)
│   │   ├── review_agent.py        # Review Agent (multiplicative two-step scoring)
│   │   ├── voice_coach.py         # Voice Coach prompt builder (tier-aware + calendar context)
│   │   ├── social_voice_agent.py  # Platform voice analysis
│   │   └── video_repurpose_agent.py # Video clip repurposing
│   │
│   ├── tools/
│   │   ├── web_scraper.py         # fetch_website, extract colors
│   │   └── brand_tools.py         # analyze_brand_colors, extract_brand_voice
│   │
│   ├── services/
│   │   ├── firestore_client.py    # All Firestore CRUD operations
│   │   ├── storage_client.py      # Cloud Storage upload + signed URLs
│   │   ├── budget_tracker.py      # Image generation budget tracking
│   │   ├── brand_assets.py        # Brand reference image injection (logo, product photos, style ref)
│   │   ├── notion_client.py       # Notion OAuth + Fernet-encrypted token storage + database export
│   │   └── email_client.py        # Resend API — .ics calendar email delivery
│   │
│   ├── models/
│   │   ├── brand.py               # Pydantic models for BrandProfile
│   │   ├── plan.py                # ContentPlan, DayBrief models
│   │   ├── post.py                # Post, ReviewResult models
│   │   └── api.py                 # Request/Response models
│   │
│   ├── tests/                     # v1.9: pytest test suite (35 tests across 5 files)
│   │   ├── conftest.py            # Shared fixtures: mock Firebase auth, mock Firestore, sample data
│   │   ├── test_auth_middleware.py # Auth middleware tests (12 tests)
│   │   ├── test_token_encryption.py # Token encryption tests (6 tests)
│   │   ├── test_budget_tracker.py # Budget tracker tests (12 tests)
│   │   ├── test_brand_sanitization.py # Brand sanitization tests (2 tests)
│   │   └── test_post_operations.py # Post operations tests (3 tests)
│   │
│   ├── requirements.txt           # v1.9: compatible version ranges (>=X,<Y) instead of exact pins
│   ├── Dockerfile                 # Multi-stage: Node.js frontend build + Python runtime
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # React Router (/, /brands, /onboard, /dashboard/:id, ...)
│   │   │                          #   v1.9: ProtectedRoute component wraps authenticated routes
│   │   ├── types/                 # Centralized type definitions (v1.7)
│   │   │   ├── index.ts           # Shared interfaces (Brand, Plan, Post, Review, etc.)
│   │   │   └── api.ts             # API response types (ApiResponse<T>, PaginatedResponse, etc.)
│   │   ├── constants/
│   │   │   └── statusMaps.ts      # Shared color/label maps for status badges
│   │   ├── utils/
│   │   │   └── downloads.ts       # downloadBlob helper (programmatic <a> click pattern)
│   │   ├── pages/                 # Route-level page components
│   │   │   ├── LandingPage.tsx    # Marketing landing page (hero, features, CTA)
│   │   │   ├── BrandsPage.tsx     # Brand list with pagination + "Create" CTA
│   │   │   ├── OnboardPage.tsx    # Brand creation wizard (thin shell → OnboardWizard)
│   │   │   ├── DashboardPage.tsx  # Brand dashboard (calendar, posts, export tabs)
│   │   │   ├── EditBrandPage.tsx  # Brand profile editor + asset management
│   │   │   ├── GeneratePage.tsx   # Per-day content generation with SSE
│   │   │   ├── ExportPage.tsx     # Bulk export (ZIP, Notion, .ics)
│   │   │   ├── NotionCallbackPage.tsx # Notion OAuth callback handler
│   │   │   ├── TermsPage.tsx      # Terms of Service
│   │   │   └── PrivacyPage.tsx    # Privacy Policy
│   │   ├── components/            # Reusable UI components
│   │   │   ├── OnboardWizard.tsx  # 3-step onboarding wizard (732 lines, deferred creation)
│   │   │   ├── GuidedTour.tsx     # 11-step SVG spotlight tour (436 lines)
│   │   │   ├── ui/                # Shared primitives (v1.7)
│   │   │   │   ├── PageContainer.tsx  # Consistent page wrapper (max-width, padding)
│   │   │   │   ├── ErrorBanner.tsx    # Dismissible error display
│   │   │   │   └── Spinner.tsx        # Loading spinner
│   │   │   ├── NavBar.tsx         # Sticky nav (Home, My Brands, Export, Account dropdown)
│   │   │   ├── PostCard.tsx       # Individual post display
│   │   │   ├── PostGenerator.tsx  # SSE consumer, generation stream
│   │   │   ├── PostLibrary.tsx    # Post list with "Copy All" clipboard
│   │   │   ├── ReviewPanel.tsx    # AI review scores and suggestions
│   │   │   ├── ContentCalendar.tsx # 7-day calendar grid
│   │   │   ├── EventsInput.tsx    # Business events input
│   │   │   ├── BrandProfileCard.tsx # Brand profile display
│   │   │   ├── BrandSummaryBar.tsx  # Compact brand info bar
│   │   │   ├── PlatformPreview.tsx  # Platform-specific post preview
│   │   │   ├── VoiceCoach.tsx     # Gemini Live voice coaching UI
│   │   │   ├── VideoRepurpose.tsx # Video generation controls
│   │   │   ├── IntegrationConnect.tsx # Notion/email integration UI
│   │   │   └── SocialConnect.tsx  # Social platform OAuth (future)
│   │   ├── hooks/
│   │   │   ├── useAuth.ts        # Firebase Google Auth hook (signIn, signOut, uid, user)
│   │   │   ├── useFetch.ts       # Generic data fetching hook useFetch<T> (v1.7)
│   │   │   ├── useWizardState.ts # Onboarding wizard state machine (85 lines, sessionStorage)
│   │   │   ├── useTour.ts        # Guided tour step state machine (84 lines, localStorage)
│   │   │   ├── useIsMobile.ts    # Mobile breakpoint hook (useMediaQuery helper) (v1.7)
│   │   │   └── useIsTablet.ts    # Tablet breakpoint hook (v1.7)
│   │   ├── api/
│   │   │   ├── client.ts         # REST API client (handleResponse + handleBlobResponse)
│   │   │   │                     #   Sends Firebase ID token in Authorization: Bearer header
│   │   │   │                     #   v1.9: Auth headers added to all 9 previously-missing fetch calls
│   │   │   └── firebase.ts       # Firebase config + Google Sign-In
│   │   │                          #   v1.9: setPersistence(auth, browserLocalPersistence)
│   │   └── theme.ts              # Design system tokens (colors, spacing)
│   ├── package.json              # React 19 + react-router-dom + Vite 7
│   ├── tsconfig.json             # TypeScript config
│   ├── vite.config.ts            # Proxy /api → :8080
│   └── index.html
├── scripts/
│   └── deploy.sh                 # One-command Cloud Build deploy
├── cloudbuild.yaml               # Cloud Build CI/CD pipeline (4 steps — v1.9: pytest before Docker build)
├── terraform/
│   ├── main.tf                   # All GCP resource definitions
│   ├── variables.tf              # Input variables
│   └── terraform.tfvars.example  # Secret values template
├── .env.example                  # Root-level deploy config template
├── docs/
│   ├── PRD.md
│   ├── TDD.md
│   ├── DEPLOYMENT.md
│   ├── architecture.mermaid
│   ├── amplifi-ui.jsx
│   ├── playtest-personas.md
│   ├── future-enhancements.md
│   └── buffer-notion-integration-plan.md
├── README.md
└── LICENSE (MIT)
```

---

# 12. Testing Strategy

## 12.1 Testing Tiers

| Tier | What | How | When |
|------|------|-----|------|
| **Unit** | Brand profile parsing, hashtag validation, platform rules | pytest, mocked Gemini responses | Week 1 |
| **Integration** | Brand Analyst → Firestore write → read | Live Gemini API + Firestore emulator | Week 1 |
| **Interleaved Output** | Generate post with text + image, verify both present | Live Gemini API, inspect response parts | Week 1 Friday |
| **SSE Streaming** | Frontend receives progressive events in correct order | FastAPI TestClient + manual browser testing | Week 2 |
| **End-to-End** | Full flow: paste URL → analysis → calendar → generate 7 posts → review | Manual testing with real business URLs | Week 2 Friday |
| **Budget** | Verify cost tracking accuracy across multiple generations | Automated test with counter assertions | Week 2 |

## 12.2 Test Infrastructure (v1.9)

**Stack:** pytest + pytest-asyncio + pytest-cov. All tests run with `pytest` from the project root. Async tests use `@pytest.mark.asyncio` and are executed with the asyncio event loop.

**Shared fixtures (`backend/tests/conftest.py`):**
- `mock_firebase_auth` — patches `firebase_admin.auth.verify_id_token` to return a deterministic decoded token
- `mock_firestore` — patches `firestore_client` with an in-memory dict-backed store
- `sample_brand` — returns a complete brand profile dict with all required fields
- `sample_plan` — returns a content plan with 7 day briefs
- `sample_post` — returns a generated post document

**35 tests across 5 test files:**

| File | Tests | Coverage |
|------|-------|----------|
| `test_auth_middleware.py` | 12 | Token verification, missing header, expired token, invalid token, brand ownership check, cross-user access denial |
| `test_token_encryption.py` | 6 | Encrypt/decrypt round-trip, missing key RuntimeError, corrupted ciphertext, key rotation |
| `test_budget_tracker.py` | 12 | can_generate_image, record_image, record_video, budget exhaustion, concurrent access, Firestore persistence across cold starts |
| `test_brand_sanitization.py` | 2 | XSS prevention in brand names, SQL-like injection in description field |
| `test_post_operations.py` | 3 | Soft delete sets status+timestamp, list_posts excludes deleted, delete idempotency |

**CI integration:** `cloudbuild.yaml` runs pytest as Step 0 before the Docker build (see §10.4). A test failure blocks the build and deploy.

## 12.3 Critical Test Cases

```python
# test_content_creator.py

async def test_interleaved_output_has_text_and_image():
    """Every generated post must contain at least 1 text part and 1 image part."""
    brand = sample_brand_profile()
    brief = sample_day_brief()
    result = await generate_post_fallback(brand, brief)

    text_parts = [r for r in result if r["type"] == "text"]
    image_parts = [r for r in result if r["type"] == "image"]

    assert len(text_parts) >= 1, "Must have at least one text part (caption)"
    assert len(image_parts) >= 1, "Must have at least one image"

async def test_image_uploaded_to_gcs():
    """Generated images must be stored in Cloud Storage with valid signed URL."""
    # Generate a post, extract image URL
    # Verify URL is accessible via HTTP GET
    # Verify URL expires after 7 days
    pass

async def test_review_agent_catches_wrong_platform_length():
    """Review agent should flag a tweet caption that exceeds 280 characters."""
    brand = sample_brand_profile()
    post = {"caption": "x" * 300, "platform": "x", "hashtags": ["#test"]}
    review = await run_review_agent(brand, post)
    assert review["checks"]["platform"]["score"] < 3
    assert not review["approved"]

async def test_brand_analysis_from_url():
    """Brand Analyst should extract meaningful colors and tone from a real URL."""
    result = await brand_analyst.analyze("https://example-bakery.com")
    assert len(result["colors"]) >= 2
    assert len(result["tone"].split(",")) >= 2
    assert result["industry"] != ""
```

---

# 13. Performance & Monitoring

## 13.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Brand analysis | < 15s | URL fetch + Gemini analysis |
| Calendar generation | < 10s | Strategy Agent response |
| Post generation (text) | < 5s to first text chunk | SSE first event |
| Post generation (image) | < 20s to image | SSE image event (Gemini image gen latency) |
| Post generation (total) | < 30s per post | SSE complete event |
| Full week generation | < 4 min (7 × 30s) | All 7 posts generated |
| Review | < 5s per post | Review Agent response |
| Image upload to GCS | < 2s | Upload + signed URL generation |
| Video generation (Veo Fast) | < 3 min per clip | Async poll completion |
| Video upload to GCS | < 5s | MP4 upload + signed URL |
| Cold start | < 8s | Cloud Run first request |

## 13.2 Latency Optimization

```python
# Parallel review: run review while user looks at generated content
# (already handled: review runs after generation and streams as separate SSE event)

# Image pre-upload: start uploading image to GCS as soon as inline_data arrives,
# don't wait for the full response to complete
async def stream_and_upload(response_parts):
    upload_tasks = []
    for part in response_parts:
        if part.inline_data:
            # Fire-and-forget upload, collect URL later
            task = asyncio.create_task(
                upload_image_to_gcs(part.inline_data.data, part.inline_data.mime_type)
            )
            upload_tasks.append(task)
    
    # Await all uploads
    urls = await asyncio.gather(*upload_tasks)
    return urls
```

## 13.3 Observability

### 13.3.1 Structured JSON Logging (v1.9)

All backend logging uses `python-json-logger` to emit JSON-formatted log entries. Cloud Logging automatically parses the JSON structure, enabling log-based queries on any field.

**RequestContextMiddleware (`backend/middleware_logging.py`):**
- Assigns a unique `request_id` (UUID4) to every incoming request via `contextvars`
- Extracts `user_uid` from the Firebase auth token and propagates it via `contextvars`
- Logs `request_complete` event on every response with: `method`, `path`, `status_code`, `duration_ms`, `user_uid`
- Skips `/health` endpoint to reduce noise from Cloud Run health checks
- All downstream `logger.*` calls automatically include `request_id` and `user_uid` in the JSON output

```python
# backend/middleware_logging.py — RequestContextMiddleware
import contextvars, uuid, time, logging
from pythonjsonlogger import json as json_log

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
user_uid_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_uid", default="")

class RequestContextMiddleware:
    async def __call__(self, request, call_next):
        request_id_var.set(str(uuid.uuid4()))
        start = time.monotonic()
        response = await call_next(request)
        if request.url.path != "/health":
            logger.info("request_complete", extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000),
                "user_uid": user_uid_var.get(),
                "request_id": request_id_var.get(),
            })
        return response
```

### 13.3.2 Metric Logging (v1.9)

Structured metric logs are emitted at key points throughout the application. Each metric log includes an `extra` dict with a `metric_name` field, enabling Cloud Monitoring log-based metrics to trigger alerts and dashboards.

```python
# Key metric events and their extra fields:
logger.info("generation_complete", extra={
    "metric_name": "generation_complete",
    "brand_id": brand_id,
    "plan_id": plan_id,
    "day_index": day_index,
    "platform": platform,
    "text_parts": num_text_parts,
    "image_parts": num_image_parts,
    "generation_latency_ms": latency,
    "image_upload_latency_ms": upload_latency,
    "review_score": review_score,
    "estimated_cost": cost,
    "budget_remaining": budget_remaining,
})

logger.error("generation_failed", extra={
    "metric_name": "generation_failed",
    "brand_id": brand_id, "plan_id": plan_id,
    "error_type": type(exc).__name__,
})

logger.warning("auth_failure", extra={
    "metric_name": "auth_failure",
    "path": request.url.path,
    "reason": "expired_token" | "invalid_token" | "missing_header",
})

logger.info("budget_record", extra={
    "metric_name": "budget_record",
    "record_type": "image" | "video",
    "count": num, "cost": cost,
})

logger.info("notion_export", extra={
    "metric_name": "notion_export",
    "brand_id": brand_id, "plan_id": plan_id,
    "pages_exported": count,
})
```

---

# 14. PRD Cross-Reference & Compliance Matrix

| PRD Requirement | TDD Section | Implementation Status |
|---|---|---|
| Brand analysis from URL (P0) | §3.2 Brand Analyst Agent, §4.1 POST /api/brands/{id}/analyze | ✓ Specified |
| Content calendar generation (P0) | §3.3 Strategy Agent, §4.1 POST /api/plans | ✓ Specified |
| Interleaved post generation (P0) | §3.4 Content Creator Agent, §8 Interleaved Output Deep Dive | ✓ Specified |
| Brand consistency review (P0) | §3.5 Review Agent, §4.1 POST /api/review/{postId} | ✓ Specified |
| React dashboard (P0) | §9 Frontend Architecture | ✓ Specified |
| Image storage — Cloud Storage (P0) | §7.2 Cloud Storage Structure, §7.3 Operations | ✓ Specified |
| Streaming UI — SSE (P0) | §4.2 SSE Implementation, §4.3 TypeScript Client | ✓ Specified |
| Generation error handling | §4.2 SSE error/retry flow, §4.3 error event type, §9.2 error UI | ✓ Specified |
| Budget protection | §4.2 Budget guard (429), §8.3 BudgetTracker | ✓ Specified |
| Individual download (P0) | §9.1 PostCard Export button, §4.1 GET /api/posts/{id}/export | ✓ ZIP download (image + video + caption) |
| Bring Your Own Photos (P1) | §3.4 Mode B, §4.1 Photo Upload endpoint, §4.2 user_photo_url, §7.1 day schema, §9.1 PhotoDropZone | ✓ Specified |
| Content repurposing / pillars (P1) | §3.3 Strategy Agent pillar prompt, §7.1 pillars subcollection + day pillar fields, §9.1 PillarSummary/PillarTag | ✓ Specified |
| Business persona (P1) | §3.2 Brand Analyst business_type prompt, §4.1 POST /api/brands, §7.1 business_type field, §9.1 BusinessTypeBadge | ✓ Specified |
| Event-aware calendar (P1) | §3.3 Strategy Agent BUSINESS_EVENTS_THIS_WEEK prompt, §4.1 POST /api/plans business_events param, §7.1 business_events field, §9.1 EventsInput | ✓ Specified |
| Visual identity seed (P1) | §3.2 Brand Analyst image_style_directive output, §3.4 Content Creator Mode A prepend, §7.1 image_style_directive field, §9.1 ImageStyleDirective | ✓ Specified |
| Caption style directive (P1) | §3.2 Brand Analyst caption_style_directive output, §3.4 Content Creator base_context prepend, §7.1 caption_style_directive field, §9.1 CaptionStyleDirective | ✓ Specified |
| Video generation via Veo 3.1 (P1) | §8.4 Video Generation, §8.4.2 Veo API, §8.4.3 REST endpoint, §8.4.4 Frontend | ✓ Specified |
| Platform Registry (P2) | §5 Platform Registry | ✓ Shipped |
| Brand reference images (P2) | §6 Brand Assets Service, §3.4.2 Brand Reference Image Injection | ✓ Shipped |
| Calibrated review scoring (P2) | §3.5.1 Calibrated 1-10 Scoring, §3.5.2 Engagement Scoring | ✓ Shipped |
| Social proof tiers (P2) | §3.3.1 Social Proof Tier System | ✓ Shipped |
| Edit Brand page (P2) | §4.1 DELETE asset, PATCH logo | ✓ Shipped |
| Notion integration (P2) | §4.1 Notion Integration endpoints | ✓ Shipped |
| Calendar .ics export (P2) | §4.1 Calendar Export endpoints | ✓ Shipped |
| Voice coach strategic awareness (P2) | §3.6 Voice Coach | ✓ Shipped |
| ZIP export (P2) | §14.1.1 Full Export (shipped — per-post ZIP + bulk plan ZIP with media) | ✓ Shipped |
| Engagement prediction (P2) | §3.5.2 Engagement Scoring (shipped) | ✓ Shipped |
| Social media voice analysis (P2) | §14.1.9 Social Media Voice Analysis | ✓ Specified |
| Platform meta intelligence (P2) | §14.1.10 Platform Meta Intelligence | ✓ Specified |
| Video repurposing / smart editing (P2) | §14.1.12 Video Repurposing / Smart Editing | ✓ Specified |
| Instagram grid consistency (P2) | §6 Brand Assets Service (shipped via brand reference images) | ✓ Shipped |
| One-tap caption export (P2) | §14.1.1 Full Export (shipped — clipboard + ZIP) | ✓ Shipped |
| Platform preview formatting (P2) | §14.1.2 Platform Preview Formatting | ✓ Specified |
| Content editing/regeneration (P2) | §14.1.3 Content Editing & Regeneration | ✓ Specified |
| Competitor visibility toggle (P2) | §14.1.4 Competitor Visibility Toggle | ✓ Specified |
| AI image quality validation (P2) | §14.1.5 AI Image Quality Validation | ✓ Specified |
| Description-first onboarding (P2) | §14.1.6 Description-First Onboarding Option | ✓ Specified |
| Multi-platform formatting (P2) | §5 Platform Registry (shipped) | ✓ Shipped |
| Frontend serving (single container) | §10.1 Docker Configuration | ✓ Specified |
| CORS configuration | §4.2 FastAPI app setup | ✓ Specified |
| Gemini model compliance | §3.4 model="gemini-3-flash-preview" / "gemini-3.1-flash-image-preview" | ✓ gemini-3-flash-preview (text) + gemini-3.1-flash-image-preview (image) |
| ADK compliance | §3.1 SequentialAgent pipeline | ✓ ADK SequentialAgent |
| Cloud Run + Firestore + Storage | §10 Deployment, §7 Data Model | ✓ All three services |
| Interleaved output (category req) | §8 Deep Dive, responseModalities | ✓ ["TEXT", "IMAGE"] |
| Automated deployment (bonus) | §10.2 Terraform, §10.3 Cloud Build | ✓ Specified |
| Public GitHub repo | §11 Repository Structure | ✓ MIT License |

## 14.1 P2 Architecture Notes (Post-Hackathon)

These features are documented in the PRD and sequenced by PM sprint priority (see PRD Post-Hackathon P2 Roadmap). Each includes implementation detail sufficient to build.

---

### 14.1.1 Full Export (Shipped)

**Type:** Frontend + backend endpoints | **Status:** Shipped

**Three export tiers (clipboard-first hierarchy):**

1. **Bulk clipboard ("Copy All")** — PostLibrary header button copies all filtered captions as a structured string with `[N] Platform · Day N` headers and `---` separators. Count is snapshotted at click time via `useRef` (not re-derived at render) to prevent label drift during polling refresh. Timer cleaned up on unmount.

2. **Per-post clipboard + ZIP** — Each PostCard has a copy button (caption + hashtags, 1.5s flash) and an export button that downloads a ZIP containing image + video + caption.txt.

3. **Bulk plan ZIP ("Export All")** — `POST /api/export/{plan_id}?brand_id={brandId}` generates a ZIP containing all posts. Each post gets a subfolder (`day_N_{platform}/`) with image, video (if generated), and caption.txt. A root `metadata.json` contains full post data (with `image_gcs_uri` stripped for security).

**Media download architecture:**
```python
# Direct GCS download — bypasses URL signing entirely
async def _download_post_image(post: dict) -> bytes | None:
    gcs_uri = post.get("image_gcs_uri")
    if not gcs_uri: return None
    prefix = f"gs://{GCS_BUCKET_NAME}/"
    if not gcs_uri.startswith(prefix): return None
    blob = get_bucket().blob(gcs_uri[len(prefix):])
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, blob.download_as_bytes)

# Image + video downloaded in parallel for each post
image_bytes_list = await asyncio.gather(*[_download_post_image(p) for p in posts])
video_bytes_list = await asyncio.gather(*[_download_post_video(p) for p in posts])
```

**Frontend ZIP handling:**
```typescript
// Both per-post and bulk export use blob download + programmatic <a> click
const blob = await response.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = filename;  // From Content-Disposition header
a.click();
URL.revokeObjectURL(url);
```

**PostLibrary header button order:** `[Refresh] [Copy All] [Export All]` — lightweight to heavy, left to right. Copy All hidden when no filtered posts exist.

---

### 14.1.2 Platform Preview Formatting (Sprint 4)

**Effort:** 1–2 days | **Type:** Frontend components

```typescript
// Platform-specific preview components

const PLATFORM_LIMITS = {
  instagram: { captionMax: 2200, hashtagMax: 30 },
  linkedin: { captionMax: 3000, foldAt: 140 },  // "see more" fold
  x: { captionMax: 280 },
  tiktok: { captionMax: 2200 },
  facebook: { captionMax: 63206 }
};

const LinkedInPreview: React.FC<{ caption: string; image?: string }> = ({ caption, image }) => {
  const foldAt = PLATFORM_LIMITS.linkedin.foldAt;
  const isFolded = caption.length > foldAt;
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="linkedin-preview">
      <div className="preview-header">
        <span className="brand-avatar" />
        <span className="brand-name">{brandName}</span>
      </div>
      {image && <img src={image} className="preview-image" style={{ aspectRatio: '1.91/1' }} />}
      <p className="preview-caption">
        {expanded || !isFolded ? caption : caption.slice(0, foldAt)}
        {isFolded && !expanded && (
          <button onClick={() => setExpanded(true)} className="see-more">...see more</button>
        )}
      </p>
      <div className="char-count">{caption.length} / {PLATFORM_LIMITS.linkedin.captionMax}</div>
      {isFolded && (
        <div className="fold-indicator">
          ⚠️ First {foldAt} characters appear above fold — hook must be here
        </div>
      )}
    </div>
  );
};

const XPreview: React.FC<{ caption: string }> = ({ caption }) => {
  const overLimit = caption.length > PLATFORM_LIMITS.x.captionMax;
  return (
    <div className="x-preview">
      <p className={overLimit ? "caption-over-limit" : ""}>
        {overLimit ? caption.slice(0, 277) + "..." : caption}
      </p>
      <div className={`char-count ${overLimit ? "over" : ""}`}>
        {caption.length} / {PLATFORM_LIMITS.x.captionMax}
        {overLimit && " ⚠️ Will be truncated"}
      </div>
    </div>
  );
};

const InstagramPreview: React.FC<{ caption: string; image?: string }> = ({ caption, image }) => (
  <div className="instagram-preview">
    {image && <img src={image} className="preview-image" style={{ aspectRatio: '1/1' }} />}
    <p className="preview-caption">{caption}</p>
    <div className="hashtag-count">
      {(caption.match(/#/g) || []).length} / {PLATFORM_LIMITS.instagram.hashtagMax} hashtags
    </div>
  </div>
);

// Platform preview switcher on ContentDetail page
const PlatformPreview: React.FC<{ platform: string; caption: string; image?: string }> = (props) => {
  switch (props.platform) {
    case "linkedin": return <LinkedInPreview {...props} />;
    case "x": return <XPreview {...props} />;
    case "instagram": return <InstagramPreview {...props} />;
    default: return <GenericPreview {...props} />;
  }
};
```

**Component tree update:**
```
├── ContentDetail
│   ├── PlatformPreview (NEW — shows how post appears on target platform)
│   │   ├── LinkedInPreview (character count, "see more" fold, 1.91:1 image crop)
│   │   ├── XPreview (280 char limit, truncation warning)
│   │   ├── InstagramPreview (square crop, hashtag count)
│   │   └── TikTokPreview (caption + video frame)
│   ├── CaptionText
│   └── CopyButton
```

No backend changes. No Firestore changes. Pure frontend.

---

### 14.1.3 Content Editing & Regeneration (Sprint 4)

**Effort:** 1–2 days | **Type:** New endpoint + frontend

**Backend — Single post regeneration:**
```python
@app.post("/api/content/{plan_id}/day/{day_index}/regenerate")
async def regenerate_single_post(plan_id: str, day_index: int, 
                                  edit_instructions: str = None):
    """Regenerate a single day's content without regenerating the full week."""
    db = firestore.client()
    plan_ref = db.collection("plans").document(plan_id)
    plan = plan_ref.get().to_dict()
    brand_id = plan["brand_id"]
    
    brand_ref = db.collection("brands").document(brand_id)
    brand = brand_ref.get().to_dict()
    
    day = plan["days"][day_index]
    
    # Build context from brand + strategy for this specific day
    context = {
        "brand_profile": brand,
        "day_strategy": day,  # pillar, platform, content_type
        "edit_instructions": edit_instructions,  # Optional: "make it more casual" / "focus on the sale"
    }
    
    # Call Content Creator for just this one post
    result = await content_creator_agent.generate_single_post(context)
    
    # Update Firestore — only this day's content
    plan["days"][day_index]["caption"] = result["caption"]
    plan["days"][day_index]["hashtags"] = result["hashtags"]
    if result.get("image_url"):
        plan["days"][day_index]["image_url"] = result["image_url"]
    plan["days"][day_index]["regenerated"] = True
    plan["days"][day_index]["regenerated_at"] = firestore.SERVER_TIMESTAMP
    
    plan_ref.update({"days": plan["days"]})
    
    return {"day": plan["days"][day_index]}
```

**Frontend — Inline editing:**
```typescript
const EditableCaption: React.FC<{ caption: string; onSave: (text: string) => void }> = ({ caption, onSave }) => {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(caption);
  
  if (!editing) {
    return (
      <div onClick={() => setEditing(true)} className="editable-caption">
        <p>{caption}</p>
        <span className="edit-hint">✏️ Click to edit</span>
      </div>
    );
  }
  
  return (
    <div className="caption-editor">
      <textarea value={text} onChange={e => setText(e.target.value)} />
      <button onClick={() => { onSave(text); setEditing(false); }}>Save</button>
      <button onClick={() => { setText(caption); setEditing(false); }}>Cancel</button>
    </div>
  );
};

// Regenerate button with optional instructions
const RegenerateButton: React.FC<{ planId: string; dayIndex: number }> = ({ planId, dayIndex }) => {
  const [instructions, setInstructions] = useState("");
  const [showInput, setShowInput] = useState(false);
  
  const handleRegenerate = async () => {
    const result = await api.regeneratePost(planId, dayIndex, instructions || undefined);
    // Update local state with new content
  };
  
  return (
    <div>
      <button onClick={() => setShowInput(!showInput)}>🔄 Regenerate</button>
      {showInput && (
        <div className="regen-input">
          <input placeholder="Optional: 'make it funnier' or 'focus on the promotion'" 
                 value={instructions} onChange={e => setInstructions(e.target.value)} />
          <button onClick={handleRegenerate}>Go</button>
        </div>
      )}
    </div>
  );
};
```

---

### 14.1.4 Competitor Visibility Toggle (Sprint 4)

**Effort:** 2–3 hours | **Type:** Frontend only

```typescript
// Add to BrandProfileCard
const CompetitorSection: React.FC<{ competitors: Competitor[] }> = ({ competitors }) => {
  const [visible, setVisible] = useState(true);  // Default visible
  
  return (
    <div className="competitor-section">
      <div className="section-header">
        <h3>Competitor Landscape</h3>
        <ToggleSwitch checked={visible} onChange={setVisible} label={visible ? "Showing" : "Hidden"} />
      </div>
      {visible && (
        <div className="competitor-grid">
          {competitors.map(c => <CompetitorCard key={c.name} {...c} />)}
        </div>
      )}
    </div>
  );
};
```

**Firestore schema addition:**
```
brands/{brandId}/
  ├── ui_preferences: {
  │     show_competitors: true   # NEW — user toggle
  │   }
```

Competitor data is always extracted during brand analysis (it informs content strategy). The toggle only affects the user-facing display.

---

### 14.1.5 AI Image Quality Validation (Sprint 5)

**Effort:** 4–6 hours | **Type:** Prompt change + frontend indicator

**Brand Analyst prompt addition:**
```
INDUSTRY RISK ASSESSMENT:
After inferring the business type, assess AI image generation risk:
- HIGH RISK (recommend BYOP): food photography, fashion, real estate, jewelry, 
  automotive, cosmetics — industries where bad AI images are worse than no images
- MEDIUM RISK: fitness, travel, education — AI images acceptable but user photos preferred
- LOW RISK: SaaS, consulting, coaching, finance — abstract/graphic images work well

Output a new field:
  "image_generation_risk": "high" | "medium" | "low"
  "byop_recommendation": "We recommend using your own photos for food content — 
    AI-generated food photography can look unappetizing. Upload your best shots 
    and we'll write perfect captions."
```

**Frontend — Quality confidence indicator:**
```typescript
const ImageQualityIndicator: React.FC<{ risk: string; contentType: string }> = ({ risk, contentType }) => {
  if (risk === "high" && contentType === "photo") {
    return (
      <div className="quality-warning">
        ⚠️ AI image quality may be limited for {industry}. 
        <strong>Upload your own photos</strong> for best results.
        <ToggleSwitch label="Caption-only mode" />
      </div>
    );
  }
  return null;
};
```

**Firestore schema addition:**
```
brands/{brandId}/
  ├── image_generation_risk: "high" | "medium" | "low"  # NEW
  ├── byop_recommendation: "..."                          # NEW
```

---

### 14.1.6 Description-First Onboarding Option (Sprint 5)

**Effort:** 3–4 hours | **Type:** Frontend flow change + A/B test

```typescript
// Two onboarding modes — A/B tested

// Mode A (current): URL primary, description secondary
// Mode B (new): Description primary, URL as optional enhancement

const OnboardPage: React.FC<{ variant: "url_first" | "description_first" }> = ({ variant }) => {
  if (variant === "description_first") {
    return (
      <div className="onboard">
        <h2>Tell us about your business</h2>
        <DescriptionInput required minLength={20} />
        <AssetUploadZone optional />
        <CollapsibleSection label="Have a website? Paste it for even better results">
          <URLInput optional />
        </CollapsibleSection>
        <AnalyzeButton />
      </div>
    );
  }
  
  // Mode A: existing flow
  return (
    <div className="onboard">
      <URLInput />
      <NoWebsiteToggle />
      <DescriptionInput />
      <AssetUploadZone />
      <AnalyzeButton />
    </div>
  );
};
```

**Analytics event:** Track conversion rate per variant:
```python
# POST /api/analytics/onboard
{
  "variant": "description_first",
  "completed": true,
  "had_url": false,
  "had_assets": true,
  "time_to_complete_ms": 45000
}
```

No backend API changes — the `POST /api/brands` endpoint already accepts `description` (required) and `website_url` (optional).

---

### 14.1.7 Multi-Platform Formatting (Sprint 5)

**Effort:** 1–2 days | **Type:** Prompt engineering per platform

**Content Creator prompt update — platform-specific generation:**
```python
PLATFORM_PROMPTS = {
    "instagram": """
    FORMAT: Instagram caption. 
    - Hook in first line (appears above fold)
    - 2-3 short paragraphs with line breaks
    - Call to action (comment, save, share)
    - 20-30 relevant hashtags at the end
    - Emoji use: moderate, on-brand
    Max: 2200 characters
    """,
    "linkedin": """
    FORMAT: LinkedIn post.
    - Strong opening hook (first 140 chars appear above "see more")
    - Professional but personable tone
    - 3-5 short paragraphs
    - End with a question or CTA to drive comments
    - 3-5 hashtags maximum (LinkedIn penalizes more)
    - No emoji overuse — 1-2 per post max
    Max: 3000 characters
    """,
    "x": """
    FORMAT: X (Twitter) post.
    - Concise, punchy, conversational
    - One clear idea per post
    - Thread format if content needs more than 280 chars (indicate with 🧵)
    - 1-3 hashtags integrated naturally (not appended)
    Max: 280 characters per tweet
    """,
    "tiktok": """
    FORMAT: TikTok caption.
    - Ultra-casual, trend-aware
    - Hook immediately — first 3 words matter most
    - Hashtags mixed with trending tags
    - CTA: "Follow for more" or "Save this for later"
    Max: 2200 characters
    """,
    "facebook": """
    FORMAT: Facebook post.
    - Conversational, community-oriented
    - Ask questions to drive comments
    - Longer form acceptable
    - 1-3 hashtags or none
    - Emoji use: moderate
    """,
}
```

**Integration:** The Strategy Agent already assigns a platform per day. When the Content Creator generates each post, it receives the corresponding `PLATFORM_PROMPTS[platform]` fragment prepended to the generation prompt. This is a prompt change, not architecture.

---

### 14.1.8 Engagement Prediction Scoring (Sprint 6)

**Effort:** 3–5 days | **Type:** New tool on Review Agent

```python
# Add to Review Agent tools

@tool
def predict_engagement(caption: str, platform: str, brand_profile: dict, 
                       image_description: str = None) -> dict:
    """Predict engagement potential for a post. Returns score and reasoning.
    
    Scoring rubric (heuristic v1 — replace with ML model when data available):
    - Hook strength (0-25): Does the first line grab attention?
    - Relevance (0-25): Does content match audience interests?
    - CTA effectiveness (0-20): Clear call-to-action that drives interaction?
    - Visual appeal (0-15): Image/video quality and relevance?
    - Platform fit (0-15): Optimized for this specific platform's algorithm?
    """
    prompt = f"""Score this social media post for predicted engagement.
    
    Platform: {platform}
    Brand audience: {brand_profile.get('target_audience')}
    Brand tone: {brand_profile.get('tone')}
    Caption: {caption}
    Image: {image_description or 'No image description available'}
    
    Score each dimension 0-100 and provide one-sentence reasoning:
    1. Hook strength (weight: 25%)
    2. Audience relevance (weight: 25%)
    3. CTA effectiveness (weight: 20%)
    4. Visual appeal (weight: 15%)
    5. Platform optimization (weight: 15%)
    
    Return JSON: {{
      "overall_score": 0-100,
      "dimensions": {{
        "hook": {{"score": N, "reasoning": "..."}},
        "relevance": {{"score": N, "reasoning": "..."}},
        "cta": {{"score": N, "reasoning": "..."}},
        "visual": {{"score": N, "reasoning": "..."}},
        "platform_fit": {{"score": N, "reasoning": "..."}}
      }},
      "improvement_suggestions": ["...", "..."]
    }}
    """
    
    response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
    return json.loads(response.text)
```

**Firestore schema addition:**
```
plans/{planId}/days[N]/
  ├── engagement_prediction: {
  │     overall_score: 78,
  │     dimensions: { hook: {score: 85, reasoning: "..."}, ... },
  │     improvement_suggestions: ["Add a question to drive comments", ...]
  │   }
```

**Frontend:** Show engagement score as a colored badge on each calendar day card (green 80+, yellow 60-79, red <60). Tap to expand full breakdown.

---

### 14.1.9 Social Media Voice Analysis (Sprint 6)

**Effort:** 3–5 days | **Type:** OAuth integrations + new input pipeline

**Frontend — Per-platform demo voice data:** The SocialConnect component includes built-in demo voice data (`DEMO_VOICE_ANALYSES: Record<string, VoiceAnalysis>`) so users can preview the voice analysis workflow without connecting a real account. Each platform card has a "try demo" link (visible when `!connected && !expanded`) that loads platform-appropriate sample data:
- **LinkedIn:** Authoritative B2B coaching voice — no emoji, long-form (250-400 words), tone: candid, specific, no-nonsense
- **Instagram:** Warm artisanal lifestyle — moderate emoji, medium-form, tone: warm, authentic, enthusiastic
- **X:** Punchy hot-take style — minimal emoji, short-form (under 280 chars), tone: sharp, opinionated, provocative

Demo data is wired via `onLoadDemo` prop: `onLoadDemo={DEMO_VOICE_ANALYSES[key] ? () => handleConnected(key, DEMO_VOICE_ANALYSES[key]) : undefined}`. The `hasAnyActive` banner check covers all four voice-analysis data sources: connected platforms array, session-local analyses, `existingVoiceAnalyses` prop (server-stored), and `existingVoiceAnalysis` + platform pair.

**Backend — OAuth flow (for real account connection):**

```python
# New endpoint for connecting social accounts
@app.post("/api/brands/{brand_id}/connect-social")
async def connect_social_account(brand_id: str, platform: str, oauth_token: str):
    """Connect a social media account for voice analysis."""
    # Platform-specific API calls
    if platform == "linkedin":
        posts = await fetch_linkedin_posts(oauth_token, limit=50)
    elif platform == "instagram":
        posts = await fetch_instagram_posts(oauth_token, limit=50)
    elif platform == "x":
        posts = await fetch_x_posts(oauth_token, limit=50)
    
    # Analyze voice patterns
    voice_analysis = await analyze_social_voice(posts)
    
    # Update brand profile with social voice data
    db = firestore.client()
    db.collection("brands").document(brand_id).update({
        "social_voice_analysis": voice_analysis,
        "connected_platforms": firestore.ArrayUnion([platform])
    })
    
    return voice_analysis

async def analyze_social_voice(posts: list[dict]) -> dict:
    """Use Gemini to analyze writing patterns from existing posts."""
    post_texts = "\n---\n".join([p["text"] for p in posts[:30]])
    
    prompt = f"""Analyze these social media posts and extract the writer's voice:
    
    {post_texts}
    
    Return JSON:
    {{
      "voice_characteristics": ["conversational", "uses humor", "asks questions"],
      "common_phrases": ["here's the thing", "let me explain"],
      "emoji_usage": "moderate" | "heavy" | "minimal" | "none",
      "average_post_length": N,
      "successful_patterns": ["posts with questions get 2x engagement", ...],
      "tone_adjectives": ["warm", "authoritative", "playful"]
    }}
    """
    
    response = await client.aio.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
    return json.loads(response.text)
```

**Brand Analyst integration:** When `social_voice_analysis` exists on a brand, the Brand Analyst includes it in context:
```
The user's existing social media voice has been analyzed:
Voice characteristics: {voice_characteristics}
Common phrases: {common_phrases}
Successful patterns: {successful_patterns}

IMPORTANT: Generated content should match this existing voice, not replace it.
```

---

### 14.1.10 Platform Meta Intelligence (Sprint 6)

**Effort:** 2–3 days | **Type:** Data pipeline + Strategy Agent tool

```python
# New tool for Strategy Agent

@tool
def research_platform_trends(platform: str, industry: str) -> dict:
    """Research current trending content patterns for a platform + industry.
    
    Uses Gemini with web search grounding to find current best practices.
    """
    prompt = f"""Research the current trending content patterns on {platform} 
    for the {industry} industry.
    
    What's working right now (this week/month)?
    - Trending formats (carousel, short video, text post, etc.)
    - Trending topics or hooks
    - Algorithm preferences (what's being boosted?)
    - Posting time recommendations
    
    Return JSON: {{
      "trending_formats": ["carousel", "behind-the-scenes reels"],
      "trending_hooks": ["hot takes", "myth-busting", "day-in-the-life"],
      "algorithm_notes": "LinkedIn is boosting document posts and polls this month",
      "best_posting_times": ["Tue 8am", "Thu 12pm"],
      "freshness": "2026-02-22"
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
        )
    )
    return json.loads(response.text)
```

**Caching:** Trend data is cached in Firestore per platform+industry for 7 days. Strategy Agent checks cache before making a new research call.

```
platform_trends/{platform}_{industry}/
  ├── data: { ... trend JSON ... }
  ├── fetched_at: timestamp
  ├── expires_at: timestamp + 7 days
```

---

### 14.1.11 Instagram Grid Visual Consistency (Sprint 6)

**Effort:** 2–3 days | **Type:** Style reference image + Content Creator update

```python
# During brand analysis, generate a "style reference image"

async def generate_style_reference(brand_profile: dict) -> str:
    """Generate a reference image that captures the brand's visual identity.
    Used as context for every subsequent image generation call."""
    
    prompt = f"""Generate a style reference image for a brand with these characteristics:
    Colors: {brand_profile['colors']}
    Tone: {brand_profile['tone']}  
    Industry: {brand_profile['business_type']}
    Style directive: {brand_profile.get('image_style_directive', 'modern, clean')}
    
    This is NOT a real post — it's a visual reference showing:
    - The brand's color palette applied to a simple composition
    - The lighting style (warm/cool/natural)
    - The texture and mood (minimal/rich/rustic)
    - The typography style if applicable
    
    Generate a single cohesive image that a designer could use as a mood board reference.
    """
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=prompt,
        config=genai.types.GenerateContentConfig(response_modalities=["IMAGE"])
    )
    
    # Upload style reference to GCS
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            blob = bucket.blob(f"brands/{brand_id}/style_reference.png")
            blob.upload_from_string(part.inline_data.data, content_type="image/png")
            return blob.public_url
    
    return None

# Content Creator update — pass style reference with every image generation
# In the Content Creator prompt for Mode A (AI-generated images):
"""
VISUAL CONSISTENCY:
Reference this style image for color palette, lighting, and mood: {style_reference_url}
Every image you generate should feel like it belongs in the same Instagram grid 
as this reference. Match the warmth, saturation, and composition style.
"""
```

**Firestore schema addition:**
```
brands/{brandId}/
  ├── style_reference_url: "gs://..."   # NEW
```

---

### 14.1.12 Video Repurposing / Smart Editing (Sprint 7+)

**Effort:** 1–2 weeks | **Type:** New agent + async processing pipeline + FFmpeg integration

User uploads raw video (up to 5 min, .mp4/.mov). Amplispark produces 2–3 platform-ready short-form clips with auto-generated captions.

**New endpoint — Upload raw video:**
```python
@app.post("/api/brands/{brand_id}/video")
async def upload_raw_video(brand_id: str, file: UploadFile = File(...)):
    """Upload raw video for repurposing. Triggers async processing."""
    # Validate: max 500MB, .mp4 or .mov only
    if file.size > 500 * 1024 * 1024:
        raise HTTPException(413, "Video must be under 500MB")
    if not file.filename.lower().endswith(('.mp4', '.mov')):
        raise HTTPException(400, "Only .mp4 and .mov files accepted")
    
    # Upload to GCS
    video_id = str(uuid.uuid4())
    gcs_path = f"brands/{brand_id}/raw_video/{video_id}/{file.filename}"
    upload_to_gcs(gcs_path, await file.read())
    
    # Create processing job record
    db = firestore.client()
    db.collection("video_jobs").document(video_id).set({
        "brand_id": brand_id,
        "status": "queued",
        "source_url": f"gs://{GCS_BUCKET}/{gcs_path}",
        "created_at": firestore.SERVER_TIMESTAMP,
        "clips": [],  # Populated by processor
    })
    
    # Trigger async processing via Cloud Tasks or Pub/Sub
    enqueue_video_processing(video_id, brand_id, gcs_path)
    
    return {"video_id": video_id, "status": "processing"}
```

**New endpoint — Check job status / get clips:**
```python
@app.get("/api/video/{video_id}")
async def get_video_status(video_id: str):
    """Poll processing status. Returns clips when ready."""
    db = firestore.client()
    job = db.collection("video_jobs").document(video_id).get().to_dict()
    return {
        "status": job["status"],  # queued | processing | complete | failed
        "clips": job.get("clips", []),
        "error": job.get("error"),
    }
```

**Async processing pipeline (Cloud Run Job or Cloud Tasks handler):**
```python
class VideoEditorAgent:
    """New agent — activated only for user-uploaded video repurposing."""
    
    async def process_video(self, video_id: str, brand_id: str, source_url: str):
        db = firestore.client()
        db.collection("video_jobs").document(video_id).update({"status": "processing"})
        
        # Step 1: Download from GCS and extract audio
        video_path = download_from_gcs(source_url)
        audio_path = extract_audio(video_path)  # FFmpeg: ffmpeg -i input.mp4 -vn audio.wav
        
        # Step 2: Transcribe via Gemini
        transcript = await self.transcribe(audio_path)
        # Returns: [{"start": 0.0, "end": 3.2, "text": "So today I want to talk about..."}, ...]
        
        # Step 3: Analyze content for highlights
        brand_profile = db.collection("brands").document(brand_id).get().to_dict()
        
        analysis_prompt = f"""Analyze this video transcript for a {brand_profile.get('description', 'business')} 
        that posts on social media. Brand tone: {brand_profile.get('tone', 'professional')}.
        
        Transcript (with timestamps):
        {json.dumps(transcript)}
        
        Identify the TOP 3 clip-worthy moments. For each, provide:
        - start_time: float (seconds)
        - end_time: float (seconds) 
        - platform: best target platform ("reels" | "tiktok" | "linkedin" | "youtube_shorts")
        - hook: the opening line/moment that grabs attention
        - reason: why this moment is compelling (key insight, emotional beat, quotable line)
        - suggested_caption: a caption in the brand's voice style
        
        Platform constraints:
        - Reels/TikTok: 15-60 seconds, hook in first 3 seconds
        - LinkedIn: 30-90 seconds, insight-driven
        - YouTube Shorts: 15-60 seconds, high energy
        
        Return as JSON array sorted by engagement potential.
        """
        
        response = await generate_content(analysis_prompt)
        clip_specs = json.loads(response.text)
        
        # Step 4: Extract clips via FFmpeg
        clips = []
        for i, spec in enumerate(clip_specs[:3]):
            clip_filename = f"clip_{i+1}_{spec['platform']}.mp4"
            clip_path = f"/tmp/{video_id}/{clip_filename}"
            
            # FFmpeg clip extraction
            extract_clip(
                input_path=video_path,
                output_path=clip_path,
                start=spec["start_time"],
                end=spec["end_time"],
            )
            
            # Step 5: Add caption overlay
            captioned_path = add_captions(
                clip_path=clip_path,
                transcript=get_segment(transcript, spec["start_time"], spec["end_time"]),
                style=brand_profile.get("caption_style", "default"),
            )
            
            # Step 6: Platform-specific formatting
            formatted_path = format_for_platform(
                clip_path=captioned_path,
                platform=spec["platform"],
                # Reels/TikTok: 9:16 vertical
                # LinkedIn: 1:1 or 16:9
                # YouTube Shorts: 9:16 vertical
            )
            
            # Upload to GCS
            gcs_clip_path = f"brands/{brand_id}/clips/{video_id}/{clip_filename}"
            upload_to_gcs(gcs_clip_path, open(formatted_path, "rb").read())
            
            clips.append({
                "clip_url": f"gs://{GCS_BUCKET}/{gcs_clip_path}",
                "platform": spec["platform"],
                "duration_seconds": spec["end_time"] - spec["start_time"],
                "hook": spec["hook"],
                "suggested_caption": spec["suggested_caption"],
                "start_time": spec["start_time"],
                "end_time": spec["end_time"],
            })
        
        # Update job status
        db.collection("video_jobs").document(video_id).update({
            "status": "complete",
            "clips": clips,
            "completed_at": firestore.SERVER_TIMESTAMP,
        })
```

**FFmpeg utility functions:**
```python
import subprocess

def extract_audio(video_path: str) -> str:
    audio_path = video_path.replace(".mp4", ".wav").replace(".mov", ".wav")
    subprocess.run([
        "ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", 
        "-ar", "16000", "-ac", "1", audio_path
    ], check=True)
    return audio_path

def extract_clip(input_path: str, output_path: str, start: float, end: float):
    subprocess.run([
        "ffmpeg", "-i", input_path, "-ss", str(start), "-to", str(end),
        "-c:v", "libx264", "-c:a", "aac", "-y", output_path
    ], check=True)

def add_captions(clip_path: str, transcript: list, style: str = "default") -> str:
    """Burn-in captions using FFmpeg subtitles filter."""
    srt_path = clip_path.replace(".mp4", ".srt")
    generate_srt(transcript, srt_path)
    output_path = clip_path.replace(".mp4", "_captioned.mp4")
    
    # Style presets
    font_size = {"default": 24, "bold": 28, "minimal": 20}[style]
    subprocess.run([
        "ffmpeg", "-i", clip_path, "-vf",
        f"subtitles={srt_path}:force_style='FontSize={font_size},PrimaryColour=&HFFFFFF,Outline=2'",
        "-c:a", "copy", "-y", output_path
    ], check=True)
    return output_path

def format_for_platform(clip_path: str, platform: str) -> str:
    """Crop/pad to platform aspect ratio."""
    output_path = clip_path.replace(".mp4", f"_{platform}.mp4")
    aspect = {
        "reels": "9:16", "tiktok": "9:16", "youtube_shorts": "9:16",
        "linkedin": "1:1",
    }.get(platform, "16:9")
    
    w, h = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}[aspect]
    subprocess.run([
        "ffmpeg", "-i", clip_path, "-vf",
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        "-c:a", "copy", "-y", output_path
    ], check=True)
    return output_path
```

**Firestore schema:**
```
video_jobs/{videoId}/
  ├── brand_id: "brand_xyz"
  ├── status: "queued" | "processing" | "complete" | "failed"
  ├── source_url: "gs://bucket/brands/brand_xyz/raw_video/..."
  ├── created_at: timestamp
  ├── completed_at: timestamp | null
  ├── error: string | null
  ├── clips: [
  │     {
  │       clip_url: "gs://bucket/brands/brand_xyz/clips/...",
  │       platform: "reels",
  │       duration_seconds: 28.5,
  │       hook: "The biggest mistake I see new founders make...",
  │       suggested_caption: "Stop doing this one thing...",
  │       start_time: 42.0,
  │       end_time: 70.5
  │     }
  │   ]
```

**Frontend component tree addition:**
```
├── ContentDetail
│   ├── ... (existing)
│   ├── UploadVideoButton (NEW — appears alongside BYOP photo upload)
│   ├── VideoProcessingIndicator (NEW — shows "Analyzing your video..." with progress)
│   └── ClipPreviewCarousel (NEW — shows 2-3 clip options with:
│       ├── VideoPlayer (trimmed clip with caption overlay preview)
│       ├── PlatformBadge (which platform this clip is optimized for)
│       ├── HookPreview (the opening line that hooks viewers)
│       ├── CaptionEditor (edit suggested caption before export)
│       └── DownloadClipButton
│       )
```

**Docker dependency:** FFmpeg must be installed in the Cloud Run container image:
```dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

**Processing notes:**
- Processing is ASYNC — not in the request path. Upload returns immediately with a job ID.
- Client polls `GET /api/video/{video_id}` every 5 seconds until status = "complete".
- Processing time estimate: 30–90 seconds for a 3-minute video (dominated by Gemini transcription + analysis).
- Cloud Run jobs have a 60-minute timeout — sufficient for 5-minute videos.
- If processing fails, status is set to "failed" with error message. Client shows retry button.

---

# 15. Environment Variable Manifest

### Server-Side (Runtime — Cloud Run `--set-env-vars`)

| Variable | Required | Description | Example |
|---|---|---|---|
| `GOOGLE_API_KEY` | ✓ | Gemini API key for all agents | `AIzaSy...` |
| `GCP_PROJECT_ID` | ✓ | GCP project ID | `amplifi-488503-a0bd0` |
| `GCS_BUCKET_NAME` | ✓ | Cloud Storage bucket for images/video | `amplifi-488503-a0bd0-amplifi-assets` |
| `CORS_ORIGINS` | ✓ | Comma-separated allowed origins | `https://amplifi-xxxxx-uc.a.run.app` |
| `GEMINI_MODEL` | | Default Gemini model (default: `gemini-3-flash-preview`) | `gemini-3-flash-preview` |
| `RESEND_API_KEY` | | Resend API key for .ics email delivery | `re_...` |
| `NOTION_CLIENT_ID` | | Notion OAuth client ID | `315d872b-...` |
| `NOTION_CLIENT_SECRET` | | Notion OAuth client secret | `secret_...` |
| `NOTION_REDIRECT_URI` | | Notion OAuth redirect URI | `https://your-url/auth/notion/callback` |
| `FERNET_KEY` | | Fernet encryption key for Notion OAuth token encryption at rest | `base64-encoded-32-byte-key` |

### Client-Side (Build-Time — Docker `--build-arg`)

| Variable | Required | Description |
|---|---|---|
| `VITE_FIREBASE_API_KEY` | ✓ | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | ✓ | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | ✓ | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | ✓ | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | ✓ | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | ✓ | Firebase app ID |

### Deploy Config (`.env` in repo root — read by `deploy.sh`)

```bash
# .env.example
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
GOOGLE_API_KEY=
CORS_ORIGINS=*
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
```

---

# 16. Architectural Differences from Fireside

For engineers working on both projects, here is a comparison of the key architectural differences:

| Dimension | Fireside — Betrayal | Amplispark |
|---|---|---|
| **Primary API** | Gemini Live API (WebSocket, bidirectional) | Gemini generateContent (REST, unidirectional) |
| **Transport** | WebSocket (persistent, multiplayer) | REST + SSE (stateless, single user) |
| **Response Modality** | AUDIO (native voice) | TEXT + IMAGE (interleaved) + VIDEO (Veo 3.1, P1) |
| **Model** | gemini-2.5-flash-native-audio-preview-12-2025 | gemini-3-flash-preview + gemini-3.1-flash-image-preview + veo-3.1-fast-generate-preview |
| **Agent Architecture** | Narrator (LLM) + Game Master (deterministic) + Traitor (LLM) | Sequential pipeline: Analyst → Strategy → Creator → Review |
| **Session Management** | Persistent (10+ min, session resumption required) | Stateless per request (no session management needed) |
| **Cloud Run Config** | Session affinity ON, 3600s timeout, WebSocket | No session affinity needed, 300s timeout, HTTP |
| **Firestore Role** | Real-time game state (players, votes, phases) | Persistent content storage (brands, plans, posts) |
| **Cloud Storage Role** | Scene images (stretch goal) | Core feature — all generated images |
| **Auth** | None (anonymous game codes) | Firebase Google Sign-In (persistent UID, profile photo) |
| **Frontend** | Mobile-first PWA, audio playback, real-time updates | Dashboard, SSE streaming, image gallery, paginated brand list |
| **CI/CD** | Manual deploy | Cloud Build pipeline + `deploy.sh` |
| **Concurrent Users** | 3–6 players per game, 1 game at a time (demo) | 1 user at a time (demo) |
| **Budget Concern** | Minimal (voice is cheap) | Moderate (~$0.039/image, tracked) |

---

# 17. Post-Hackathon Architecture Migration

This section catalogs every architectural decision made for the 3-week hackathon that will NOT survive contact with real users at scale. These are not bugs — they are intentional shortcuts that need planned migrations.

**Severity Levels:**
- 🔴 **Breaking** — Stops working entirely at scale. Must fix before any public launch.
- 🟡 **Degraded** — Works but poorly. Users will notice. Fix within first month.
- 🟢 **Technical Debt** — Works fine but limits future features. Fix when convenient.

## 17.1 🔴 Single-Container Monolith → Microservices

**Hackathon:** One Docker container runs FastAPI + React + all 4 ADK agents in-process (§10.1). Single Cloud Run service.

**Why it breaks:** A content generation request (Brand Analyst → Strategy → Content Creator → Review) holds a Cloud Run instance for 30-60 seconds while 4 sequential LLM calls complete. The Content Creator with interleaved output blocks for 10-20 seconds per post; generating 7 posts = 70-140 seconds of wall-clock time per user. At 50 concurrent users generating weekly calendars, you need ~50 warm Cloud Run instances each burning CPU while waiting on Gemini API responses.

**Migration:**

```
HACKATHON                           PRODUCTION
┌─────────────────────────┐         ┌──────────┐  ┌──────────┐  ┌───────────┐
│ Cloud Run (1 container) │         │Firebase  │  │API       │  │Agent      │
│ React + FastAPI + ADK   │   →     │Hosting   │  │Gateway   │  │Workers    │
│ + SSE + Budget (memory) │         │(static)  │  │(stateless│  │(Cloud Run │
└─────────────────────────┘         └──────────┘  │ + auth)  │  │ Jobs)     │
                                                  └────┬─────┘  └────┬──────┘
                                                       │             │
                                                  Cloud Tasks ───────┘
                                                  (job queue)
```

- Split into 3 services: Frontend (Firebase Hosting / CDN), API Gateway (stateless Cloud Run), Agent Workers (Cloud Run Jobs — no request timeout, billed per vCPU-second)
- Generation requests enqueue via Cloud Tasks; workers pull and process
- Video generation (§8.4) already uses this async job pattern — extend it to all generation

**Effort:** 2-3 weeks.

## 17.2 🔴 Gemini API Rate Limits — The Hard Ceiling

**Hackathon:** Direct Gemini API calls from a single GCP project. Every agent call = 1 API request.

**Why it breaks:** Gemini 3 Flash on Paid Tier 1: ~150 RPM. A single user's full calendar generation = 16 API calls (1 brand analysis + 1 strategy + 7 content generations + 7 reviews). Maximum concurrent full-calendar generations before 429 errors: **~9 users**. This is not a scale problem — it's a "10th customer gets an error" problem.

Interleaved output (TEXT + IMAGE) requests are computationally expensive and may hit TPM (tokens per minute) limits before RPM. Image generation has its own IPM cap. Veo has even stricter quotas.

**Migration:**
- Request queue with priority + position tracking ("You are #3 in line" instead of 429 error)
- Vertex AI provisioned throughput (enterprise quotas, SLA) instead of AI Studio API keys
- Aggressive caching: identical brand analysis for the same URL hits cache, not Gemini
- Pre-generate common content templates during off-peak (Gemini Batch API)
- Multi-project sharding: split users across 2-3 GCP projects to multiply quotas (short-term)

**Effort:** 1-2 weeks for queuing + caching. Vertex AI migration is a config change.

## 17.3 🔴 In-Memory BudgetTracker → Persistent Budget Service

**Hackathon:** `BudgetTracker` (§8.3) is a Python class instance in memory on a single Cloud Run container.

**Why it breaks:** Cloud Run is stateless. Instance scales down → budget resets to zero. Two instances running simultaneously have independent counters — each thinks it has the full $100 budget. 2x overspend without knowing.

**Migration:**
- Firestore atomic increment on a `budget` document per project
- Firestore transactions for check-and-increment (`can_generate` + `record_generation` must be atomic)
- Cloud Monitoring alerts at 50%, 75%, 90% budget thresholds
- Per-user budget isolation (multi-tenant) in Firestore

**Effort:** Half a day. Should be done during hackathon if time allows.

## 17.4 🔴 No Authentication / Single-Tenant → Multi-Tenant with Auth

**Hackathon:** No authentication. One brand, one user. The Firestore schema (§7.1) has no `user_id` scoping on any document.

**Why it breaks:** Adding multi-tenancy retroactively requires restructuring every Firestore path from `brands/{brandId}/...` to `users/{userId}/brands/{brandId}/...` — affecting every query in the codebase.

**Migration:**
- Firebase Authentication (Google Sign-In, email/password)
- Restructure Firestore: `users/{userId}/brands/{brandId}/content_plans/{planId}/days/{dayIndex}/...`
- Firestore security rules scoped to authenticated user
- API middleware: extract `user_id` from Firebase JWT, scope all queries
- Data migration script for existing documents

**Effort:** 1 week. Auth is fast; restructuring Firestore + updating every query is the bulk.

## 17.5 🟡 SSE Streaming → Job Polling

**Hackathon:** Server-Sent Events (§4.2) for generation stream.

**Why it degrades:**
- SSE connections are unidirectional — client can't cancel mid-generation
- Each SSE connection holds a Cloud Run instance active for 30-60 seconds per post
- Connections don't survive Cloud Run instance restarts — client loses all progress
- No reconnection semantics; client must restart generation from scratch

**Migration (recommended: job-based polling):**
- Generation request returns `job_id` immediately
- Client polls `GET /api/jobs/{jobId}` every 2 seconds
- Backend writes generation progress to Firestore in real-time
- This is exactly the video generation pattern (§8.4.3) — extend to all content generation
- Alternative: Firestore `onSnapshot` listeners for real-time push without direct server connection

**Effort:** 3-4 days (pattern already exists in §8.4).

## 17.6 🟡 Sequential Agent Pipeline → Parallel Generation

**Hackathon:** ADK SequentialAgent (§3.1) runs all 4 agents in-process, serially. 7 posts × 15 seconds each = ~2 minutes wall-clock.

**Why it degrades:** Can't parallelize within ADK's SequentialAgent by definition. The entire pipeline blocks. ADK's session management is designed for single-conversation flows, not concurrent multi-user batch workloads. Context window bloats as more agents and data accumulate in the sequence.

**Migration:**
- Replace SequentialAgent with explicit orchestration: FastAPI background task calls each agent individually, stores intermediate results in Firestore
- Parallelize Content Creator: `asyncio.gather()` for all 7 posts simultaneously → generation time drops from ~2 min to ~20 seconds
- ADK context processors to trim unnecessary data between agent stages
- Consider Vertex AI Agent Engine for managed session handling at scale

**Effort:** 1-2 weeks. Parallelization alone delivers 7x speedup for calendar generation.

## 17.7 🟡 Signed URLs (7-day expiry) → CDN + Permanent URLs

**Hackathon:** Generated images served via GCS signed URLs (§7.3) that expire in 7 days.

**Why it degrades:** User returns after 2 weeks — all content images are broken links. Signed URLs aren't CDN-cacheable (unique signatures). Every image request hits GCS directly — no edge caching for distant users.

**Migration:**
- Cloud CDN in front of GCS bucket with public-read objects for generated content
- Permanent deterministic URLs: `https://cdn.amplifi.app/content/{postId}/hero.png`
- Access control at application level (API checks user owns brand before returning URL)

**Effort:** 1-2 days. Mostly configuration.

## 17.8 🟡 No Billing → Stripe Subscriptions

**Hackathon:** Free, unlimited usage funded by $100 Google Cloud credit. Shared global budget.

**Why it degrades:** $100 runs out. One heavy user burns the entire budget. No revenue model.

**Migration:**
- Stripe integration: subscription billing + usage-based metering
- Tiered plans: Free (5 posts/week, no video), Pro ($19/mo, unlimited + 10 videos), Business ($49/mo, team features)
- Per-user budget isolation in Firestore
- Stripe webhook → update user's generation allowance

**Effort:** 1-2 weeks.

## 17.9 🟢 No Social Publishing

**Hackathon:** Generate → download. No scheduling, no publishing, no calendar sync.

**Why this is debt:** Amplispark generates a 7-day calendar but can't schedule posts. Users manually copy captions and upload images to each platform — defeating the "AI creative director" promise.

**Migration:**
- Social media API integrations: Instagram Graph API, X API v2, LinkedIn Marketing API, TikTok API
- Each requires OAuth 2.0 per user per platform + media upload + content policy compliance
- Cloud Scheduler cron job publishes due posts every 15 minutes
- Instagram requires Facebook Page + Business Account; X requires paid API tier for posting

**Effort:** 3-4 weeks for 2-3 platforms (~1 week per platform due to OAuth + media upload quirks).

**Buffer Integration (Planned):** Buffer is currently in closed beta for their new API and not accepting new developer applications. We plan to integrate Buffer for scheduled publishing once API access becomes available. Full design is documented in `docs/buffer-notion-integration-plan.md` (OAuth flow, channel selection, publish endpoints, rate limits).

## 17.10 🟢 No Analytics / Feedback Loop

**Hackathon:** Generate and forget. AI never learns what works for a specific brand.

**Why this is debt:** Strategy Agent makes identical recommendations regardless of past performance. No engagement data = no improvement over time.

**Migration:**
- Pull engagement metrics from social media APIs (requires §17.9)
- Store per-post metrics in Firestore: impressions, likes, comments, shares
- Feedback loop: top-performing posts become few-shot examples in Strategy Agent prompts
- Dashboard: engagement charts, best-performing content types, optimal posting times

**Effort:** 2-3 weeks (after social integrations are complete).

## 17.11 🟢 No Content Library / Asset Management

**Hackathon:** Generated images stored in flat GCS paths. No tagging, search, or reuse.

**Why this is debt:** After 4 weeks, a brand has ~28 images. Users can't search "coffee image from 2 weeks ago" or reuse a high-performing image with a new caption.

**Migration:**
- Firestore media collection with auto-tags (Gemini image analysis), dimensions, performance
- Search endpoint: `GET /api/media?tags=coffee,morning&sort=engagement`
- "Use existing image" option in calendar alongside "Generate new" and "Upload photo"

**Effort:** 1 week.

## 17.12 Migration Priority

| Priority | Item | Effort | Why First |
|---|---|---|---|
| **Week 1** | §17.3 Persistent Budget | 0.5 days | Prevents overspend. Trivial fix. |
| **Week 1** | §17.4 Auth + Multi-Tenant | 1 week | Can't have multiple users without it. |
| **Week 2** | §17.2 Rate Limit Queuing | 1-2 weeks | 10th user gets 429 without it. |
| **Week 2** | §17.7 CDN + Permanent URLs | 1-2 days | Images break after 7 days. |
| **Week 3-4** | §17.1 Microservices Split | 2-3 weeks | Unblocks scaling past ~20 concurrent users. |
| **Week 3-4** | §17.6 Parallel Generation | 1-2 weeks | 7x speedup for core UX. |
| **Week 5-6** | §17.5 Job Polling | 3-4 days | Resilient generation. |
| **Week 5-6** | §17.8 Billing | 1-2 weeks | Revenue. |
| **Month 3+** | §17.9 Social Publishing | 3-4 weeks | Makes this a real product. |
| **Month 3+** | §17.10 Analytics | 2-3 weeks | Makes this a sticky product. |
| **Month 3+** | §17.11 Asset Library | 1 week | Power user quality-of-life. |

**Total estimated effort:** 8-12 weeks to production-ready.

**Key insight:** The core logic survives intact — agent prompts, interleaved output parsing, brand analysis pipeline, Veo integration, BYOP photo flow, pillar-based repurposing. The migration wraps this core in production infrastructure (auth, queuing, billing, CDN, microservices). No rewrites, only re-wiring.

---

*Document created: February 21, 2026*
*Updated: March 2, 2026 (v1.3 — Platform Registry, Brand Assets, Notion/Calendar integrations, calibrated scoring, social proof tiers, voice coach strategy)*
*Companion PRD: PRD.md v1.3*
*Hackathon deadline: March 16, 2026*