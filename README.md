# Amplifi

**Your AI creative director. One brand. Infinite content.**

**Live Demo:** [https://amplifi-seimyaykpa-uc.a.run.app](https://amplifi-seimyaykpa-uc.a.run.app)

**Demo Video:** [https://youtu.be/kteHRZ9_N-w](https://youtu.be/kteHRZ9_N-w)

**Behind the Build:** [https://youtu.be/2XBBnFbplWo](https://youtu.be/2XBBnFbplWo)

An AI-powered creative director that analyzes your brand and produces complete, ready-to-post social media content packages — captions, images, hashtags, and posting schedules — all generated together in a single interleaved output stream.

## What is this?

Amplifi uses Gemini's interleaved text + image output to generate copy and visuals together in one coherent stream. Describe your business (or paste your website URL for deeper analysis), and get a full week of social media content tailored to your brand, across every platform.

- **3-step onboarding wizard** — a guided wizard replaces the old single-form onboarding. Step 1: business name, description, website URL, industry. Step 2: tone, audience, colors, logo upload (skippable). Step 3: platform selection (AI or manual). SessionStorage persistence survives refresh; brand creation is deferred to the final step.
- **Interactive guided tour** — an 11-step tooltip tour with spotlight overlay on first dashboard visit. Covers brand summary, edit brand, calendar, generate, style picker, new plan, tabs, posts, connections, video, and voice coach. Auto-switches tabs, supports Back/Next/Skip and Escape key. Re-accessible via "Take a tour" button in the brand summary bar.
- **Smart brand analysis** — describe your business or paste your website URL. Amplifi extracts your colors, tone, audience, visual style, and competitive positioning automatically.
- **Weekly content calendar** — a full 7-day content plan with AI-researched posting frequency, optimal posting times, and pillar-based strategy (education-first for new brands, data-forward for established ones).
- **11 platforms** — Instagram, LinkedIn, X, TikTok, Facebook, Threads, Pinterest, YouTube Shorts, Mastodon, Bluesky, and more. Each post is tailored to the platform's format, character limits, hashtag conventions, and algorithm preferences.
- **Captions and images generated together** — text and matching visuals are created in a single AI pass, ensuring they complement each other. Automatic fallback if image generation fails.
- **Instagram carousels** — multi-slide carousel posts with parallel image generation per slide, open-loop swipe drivers, and named technique headlines.
- **AI video clips** — generate Reels and TikTok clips from your post's hero image or from text prompts via Veo 3.1.
- **AI media editor** — edit generated images and videos with natural language ("make the background warmer", "add more contrast"). Trend-researched style suggestions and 35 visual styles to choose from.
- **Bring your own photos** — upload your own product shots or brand photos. Amplifi writes captions tailored to your images.
- **Voice strategy coach** — talk to your AI creative director in real time. Discusses your content calendar, explains strategy decisions, advises on specific days, and coaches on caption writing — all in a live voice conversation.
- **Intelligent content scoring** — every post is scored across 5 dimensions (hook strength, relevance, CTA effectiveness, platform fit, teaching depth) with platform-specific weighting. Structural issues reduce the score proportionally, never catastrophically.
- **Multiple brands** — manage multiple brands from one account. Each brand has its own profile, calendar, and content library.
- **Full export suite** — copy captions to clipboard, download individual posts as ZIP (image + video + caption), bulk-export entire plans, sync to Notion, or email a calendar invite.
- **Post library and history** — search, filter, and browse all generated content across plans. Filter by status, platform, or content pillar.
- **Live platform previews** — see how your post will look on each platform with character counts, "see more" fold indicators, and platform-specific formatting.
- **Notion integration** — connect your Notion workspace via OAuth and export your content calendar directly to a Notion database.
- **Responsive design** — works on desktop, tablet, and mobile with dedicated breakpoints and touch-friendly controls.
- **Secure by default** — Google Sign-In with server-side token verification, encrypted OAuth tokens, and per-brand access control.

## How it works

1. **Sign in with Google** — one-click Google Sign-In to link your brands to your account.
2. **Complete the onboarding wizard** — a 3-step wizard collects your business info, brand preferences, and platform selection. Skip what you want; finalize with "Create My Brand."
3. **AI builds your brand** — colors, tone, audience, competitors, style directives — all editable. A guided tour walks you through the dashboard on your first visit.
4. **Get your week** — watch as a multi-platform 7-day content calendar streams in live, with AI-researched posting frequency and suggested posting times per platform.
5. **Review and export** — approve posts, download ZIPs, export to Notion, or copy all captions to clipboard.

## Tech Stack

- **AI Engine:** Gemini 3 Flash (text/captions/reviews), Gemini 3.1 Flash Image Preview (image generation), Gemini 2.5 Flash Native Audio (voice coaching), Veo 3.1 (video generation)
- **Voice:** Gemini Live API (BidiGenerateContent) for multi-turn voice coaching
- **Agent Framework:** Google ADK (Agent Development Kit)
- **Backend:** FastAPI on Cloud Run (port 8080), modular router architecture
- **Auth:** Firebase Google Sign-In (persistent UID, account dropdown with profile photo) + firebase-admin server-side token verification
- **Security:** Fernet encryption (cryptography library) for stored OAuth tokens, path traversal prevention
- **Database:** Cloud Firestore
- **Storage:** Cloud Storage (generated images, videos + uploads)
- **Video:** Veo 3.1 (AI-generated Reels/TikTok clips)
- **Email:** Resend API (calendar invite delivery)
- **Integrations:** Notion API (OAuth + calendar export)
- **Frontend:** React 19 + TypeScript + Vite 7
- **CI/CD:** Cloud Build pipeline (`cloudbuild.yaml` + `scripts/deploy.sh`) — one-command deploy
- **Infrastructure:** Terraform IaC provisions all GCP resources (APIs, Firestore, GCS, Artifact Registry, Cloud Run, CORS auto-config)

## Architecture

```
User Browser (React 19 + Firebase Google Auth)
    ←REST + SSE→ Cloud Run (FastAPI :8080)
                    ├── Auth Middleware (Firebase token verification + brand ownership)
                    ├── Routers (modular API — brands, plans, posts, generation, media, voice, integrations)
                    ├── ADK Sequential Pipeline
                    │   ├── Brand Analyst Agent (temp 0.15)
                    │   ├── Strategy Agent (social proof tiers, Google Search grounding for frequency + platform research)
                    │   ├── Content Creator Agent (interleaved output)
                    │   │   ├── Carousel: 3-slide parallel image gen (safety validation)
                    │   │   ├── video_first: caption-only → auto-Veo
                    │   │   └── Fallback: image-only retry on failure
                    │   └── Review Agent (multiplicative scoring, platform checks, video topic awareness)
                    ├── AI Media Editor (trend research + platform-optimized prompts + text overlays)
                    ├── Voice Coach (Gemini Live — tier-aware strategy + calendar context)
                    ├── Video Creator (Veo 3.1)
                    ├── Platform Registry (11 platforms — single source of truth)
                    ├── Brand Assets Service (logo + product photo cache)
                    ├── Notion Client (OAuth + Fernet-encrypted tokens)
                    ├── Email Service (Resend — .ics calendar delivery)
                    ├── Firebase Google Auth (persistent UID + server-side verification)
                    ├── Gemini API (generateContent)
                    │   └── responseModalities: ["TEXT", "IMAGE"]
                    ├── Cloud Firestore (brands, plans, posts)
                    └── Cloud Storage (images, videos, assets)

CI/CD:  deploy.sh → Cloud Build → Docker build → Artifact Registry → Cloud Run
IaC:    terraform apply provisions all GCP resources in one command
```

See the [architecture diagram](docs/architecture-simple.mermaid) for the high-level overview, or the [complete architecture](docs/architecture-complete.mermaid) for the full system with all sub-modules and data flows.

## Quick Start

1. **Go to** [https://amplifi-seimyaykpa-uc.a.run.app](https://amplifi-seimyaykpa-uc.a.run.app)
2. **Sign in** with Google (one-click)
3. **Complete the onboarding wizard** — enter your business name, description, and optionally paste your website URL for automatic brand analysis
4. **Choose your platforms** — select which social media platforms you want content for
5. **Create a plan** — click "New Plan" on the dashboard, select a visual style, and hit "Create Plan." The AI researches optimal posting frequency per platform and builds a 7-day content calendar with time slots and content pillars
6. **Generate content** — click the "Generate" button on any day in the calendar. Captions and images stream in together via Gemini's interleaved output — you'll see the text and matching visuals appear in real time
7. **Review and edit** — click any post to see its score breakdown, edit the caption, regenerate images, or generate a video clip
7. **Talk to your Voice Coach** — click the microphone to have a live conversation about your content strategy
8. **Export** — sync to Notion, email the calendar, or bulk-download as ZIP

For local development and deployment instructions, see the [Deployment Guide](docs/DEPLOYMENT.md).

## Documentation

| Document | Description |
|---|---|
| [Product Requirements (PRD)](docs/PRD.md) | v1.7 — Full product spec with 3-step onboarding wizard, guided tour, security hardening, multiplicative scoring, responsive design, modular architecture, AI media editor |
| [Technical Design (TDD)](docs/TDD.md) | v1.6 — Implementation spec covering Cloud Build CI/CD, SPA routing, Google Sign-In, Brands page, Platform Registry, integrations, calibrated review scoring |
| [Deployment Guide](docs/DEPLOYMENT.md) | Complete deployment guide — local dev, Cloud Build CI/CD (`deploy.sh`), manual Cloud Run deploy, Terraform IaC, environment variables, troubleshooting |
| [Architecture Diagram](docs/architecture-simple.mermaid) | High-level system architecture — ADK pipeline, Gemini APIs, GCP services |
| [Architecture (Complete)](docs/architecture-complete.mermaid) | Full detailed diagram — all sub-modules, routers, services, data flows |
| [UI Mockup](docs/amplifi-ui.jsx) | Interactive React prototype — 6 screens (Landing, Onboard, Brand, Calendar, Content, Dashboard) |
| [Integration Plan](docs/buffer-notion-integration-plan.md) | Buffer + Notion integration design — OAuth flows, database export, .ics calendar, email delivery |

## Hackathon

Built for the **Gemini Live Agent Challenge** hackathon ($80K prize pool, Google DeepMind / Devpost).

- **Category:** Creative Storyteller
- **Deadline:** March 16, 2026 at 5:00 PM PDT
- **Prize Target:** $10K (category) + $5K (subcategory)