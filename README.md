# Amplifi

**Your AI creative director. One brand. Infinite content.**

**Live Demo:** [https://amplifi-seimyaykpa-uc.a.run.app](https://amplifi-seimyaykpa-uc.a.run.app)

An AI-powered creative director that analyzes your brand and produces complete, ready-to-post social media content packages — captions, images, hashtags, and posting schedules — all generated together in a single interleaved output stream.

## What is this?

Amplifi uses Gemini's interleaved text + image output to generate copy and visuals together in one coherent stream. Describe your business (or paste your website URL for deeper analysis), and get a full week of social media content tailored to your brand, across every platform.

- **Brand-aware AI** — extracts your colors, tone, audience, and style automatically with deterministic analysis (temperature 0.15). Brand reference images (logo, product shots, style ref) are injected into every generation call for visual consistency.
- **Multi-platform calendars with AI-researched posting frequency** — Gemini + Google Search grounding researches optimal posting frequency (posts/week) and best posting times per platform, tailored to each business type and industry. A 7-day plan produces 19-30+ briefs with variable stacking per day column. Cached in Firestore (7-day TTL).
- **Suggested posting times** — each calendar card shows the AI-researched best time to post (e.g., "9:00 AM"), sorted within each day column by time
- **Full weekly calendar** — 7 days of content with pillar-based strategy, event integration, and social proof tier awareness (education-first for new brands, data-forward for established ones)
- **Interleaved generation** — captions and matching images born together via Gemini, with automatic fallback if interleaved mode fails to produce an image
- **10-platform support** — Instagram, LinkedIn, X, TikTok, Facebook, Threads, Pinterest, YouTube Shorts, Mastodon, and Bluesky via a unified Platform Registry with per-platform character limits, hashtag caps, fold positions, and voice directives
- **Bring your own photos** — upload product shots, get tailored captions
- **Instagram carousels** — 3-slide carousel posts with parallel image generation per slide
- **AI video** — generate Reels/TikTok clips via Veo 3.1 (image-to-video or text-to-video for video_first posts); viewable on saved posts (collapses for text-first platforms)
- **Voice coach** — multi-turn Gemini Live sessions with auto-reconnect, graceful close, and tier-aware strategy context (explains why your calendar is structured the way it is)
- **Google Sign-In** — Firebase Google Auth with persistent UID, account dropdown with profile photo, and per-user brand isolation
- **Brand management** — dedicated Brands page with paginated brand list (5 per page), "Create Your Brand" CTA, and one-click navigation to any brand's dashboard
- **Full export** — "Copy All" clipboard, per-post ZIP download (image + video + caption), bulk plan ZIP, Notion database export, and .ics calendar download/email
- **Auto-review** — calibrated 1-10 scoring across 5 engagement dimensions (hook strength, relevance, CTA effectiveness, platform fit, teaching depth), platform-specific checks, engagement prediction (low/medium/high/viral), and auto-cleaned hashtags
- **Platform previews** — live character counts, "see more" fold indicators, and platform-specific formatting
- **Post History page** — searchable, filterable view of all generated posts across all content plans. Filters by status (approved/ready), platform, and pillar. Paginated with week headers.
- **Edit Brand page** — full brand profile editor with asset management (upload/delete photos, set/clear logo), platform selector (AI-recommended or manual selection)
- **Notion integration** — full OAuth flow to export your content calendar directly to a Notion database

## How it works

1. **Sign in with Google** — one-click Google Sign-In to link your brands to your account.
2. **Describe your brand** — tell us about your business in a few sentences. Optionally add your website URL for deeper analysis.
3. **AI builds your brand** — colors, tone, audience, competitors, style directives — all editable.
4. **Get your week** — watch as a multi-platform 7-day content calendar streams in live, with AI-researched posting frequency and suggested posting times per platform.
5. **Review and export** — approve posts, download ZIPs, export to Notion, or copy all captions to clipboard.

## Tech Stack

- **AI Engine:** Google Gemini 2.5 Flash (interleaved text + image output)
- **Voice:** Gemini Live API (BidiGenerateContent) for multi-turn voice coaching
- **Agent Framework:** Google ADK (Agent Development Kit)
- **Backend:** FastAPI on Cloud Run (port 8080)
- **Auth:** Firebase Google Sign-In (persistent UID, account dropdown with profile photo)
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
                    ├── ADK Sequential Pipeline
                    │   ├── Brand Analyst Agent (temp 0.15)
                    │   ├── Strategy Agent (social proof tiers, Google Search grounding for frequency + platform research)
                    │   ├── Content Creator Agent (interleaved output)
                    │   │   ├── Carousel: 3-slide parallel image gen
                    │   │   ├── video_first: caption-only → auto-Veo
                    │   │   └── Fallback: image-only retry on failure
                    │   └── Review Agent (calibrated 1-10, platform checks)
                    ├── Voice Coach (Gemini Live — tier-aware strategy)
                    ├── Video Creator (Veo 3.1)
                    ├── Platform Registry (10 platforms — single source of truth)
                    ├── Brand Assets Service (logo + product photo cache)
                    ├── Notion Client (OAuth + database export)
                    ├── Email Service (Resend — .ics calendar delivery)
                    ├── Firebase Google Auth (persistent UID)
                    ├── Gemini API (generateContent)
                    │   └── responseModalities: ["TEXT", "IMAGE"]
                    ├── Cloud Firestore (brands, plans, posts)
                    └── Cloud Storage (images, videos, assets)

CI/CD:  deploy.sh → Cloud Build → Docker build → Artifact Registry → Cloud Run
IaC:    terraform apply provisions all GCP resources in one command
```

See the full [architecture diagram](docs/architecture.mermaid) for agent interactions and data flows.

## Documentation

| Document | Description |
|---|---|
| [Product Requirements (PRD)](docs/PRD.md) | v1.5 — Full product spec with Google Sign-In, Brands page, all P0/P1/P2 features shipped, social proof tier system |
| [Technical Design (TDD)](docs/TDD.md) | v1.6 — Implementation spec covering Cloud Build CI/CD, SPA routing, Google Sign-In, Brands page, Platform Registry, integrations, calibrated review scoring |
| [Deployment Guide](docs/DEPLOYMENT.md) | Complete deployment guide — local dev, Cloud Build CI/CD (`deploy.sh`), manual Cloud Run deploy, Terraform IaC, environment variables, troubleshooting |
| [Architecture Diagram](docs/architecture.mermaid) | Mermaid diagram — full agent pipeline, CI/CD infrastructure, Google Auth, Brands page, Notion/Email services, GCP data flows |
| [UI Mockup](docs/amplifi-ui.jsx) | Interactive React prototype — 6 screens (Landing, Onboard, Brand, Calendar, Content, Dashboard) |
| [Integration Plan](docs/buffer-notion-integration-plan.md) | Buffer + Notion integration design — OAuth flows, database export, .ics calendar, email delivery |

## Roadmap

- **Buffer integration** — Buffer is currently in closed beta for their new API and not accepting new developer applications. We plan to integrate Buffer for scheduled publishing once API access becomes available. Full design is documented in [buffer-notion-integration-plan.md](docs/buffer-notion-integration-plan.md).

## Hackathon

Built for the **Gemini Live Agent Challenge** hackathon ($80K prize pool, Google DeepMind / Devpost).

- **Category:** Creative Storyteller
- **Deadline:** March 16, 2026 at 5:00 PM PDT
- **Prize Target:** $10K (category) + $5K (subcategory)

## License

MIT
