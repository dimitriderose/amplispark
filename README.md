# ✨ Amplifi

**Your AI creative director. One brand. Infinite content.**

An AI-powered creative director that analyzes your brand and produces complete, ready-to-post social media content packages — captions, images, hashtags, and posting schedules — all generated together in a single interleaved output stream.

## What is this?

Amplifi uses Gemini's interleaved text + image output to generate copy and visuals together in one coherent stream. Paste your website URL (or just describe your business), and get a full week of social media content tailored to your brand, across every platform.

- 🎨 **Brand-aware AI** — extracts your colors, tone, audience, and style automatically with deterministic analysis (temperature 0.15). Brand reference images (logo, product shots, style ref) are injected into every generation call for visual consistency.
- 📅 **Full weekly calendar** — 7 days of content with pillar-based strategy, event integration, and social proof tier awareness (education-first for new brands, data-forward for established ones)
- 🖼️ **Interleaved generation** — captions and matching images born together via Gemini, with automatic fallback if interleaved mode fails to produce an image
- 📱 **10-platform support** — Instagram, LinkedIn, X, TikTok, Facebook, Threads, Pinterest, YouTube Shorts, Mastodon, and Bluesky via a unified Platform Registry with per-platform character limits, hashtag caps, fold positions, and voice directives
- 📸 **Bring your own photos** — upload product shots, get tailored captions
- 🎠 **Instagram carousels** — 3-slide carousel posts with parallel image generation per slide
- 🎬 **AI video** — generate Reels/TikTok clips via Veo 3.1 (image-to-video or text-to-video for video_first posts); viewable on saved posts (collapses for text-first platforms)
- 🗣️ **Voice coach** — multi-turn Gemini Live sessions with auto-reconnect, graceful close, and tier-aware strategy context (explains why your calendar is structured the way it is)
- 🔐 **Anonymous auth** — Firebase Anonymous Auth links brands to a persistent UID across sessions
- 📋 **Full export** — "Copy All" clipboard, per-post ZIP download (image + video + caption), bulk plan ZIP, Notion database export, and .ics calendar download/email
- 🔍 **Auto-review** — calibrated 1-10 scoring across 5 engagement dimensions (hook strength, relevance, CTA effectiveness, platform fit, teaching depth), platform-specific checks, engagement prediction (low/medium/high/viral), and auto-cleaned hashtags
- 🎯 **Platform previews** — live character counts, "see more" fold indicators, and platform-specific formatting
- ✏️ **Edit Brand page** — full brand profile editor with asset management (upload/delete photos, set/clear logo)
- 🔗 **Notion integration** — full OAuth flow to export your content calendar directly to a Notion database

## How it works

1. **Paste your URL** — Amplifi crawls your site and extracts your brand DNA. No website? Just describe your business.
2. **AI builds your brand** — Colors, tone, audience, competitors, style directives — all editable.
3. **Get your week** — Watch as a 7-day content calendar streams in live, post by post.

## Tech Stack

- **AI Engine:** Google Gemini 2.5 Flash (interleaved text + image output)
- **Voice:** Gemini Live API (BidiGenerateContent) for multi-turn voice coaching
- **Agent Framework:** Google ADK (Agent Development Kit)
- **Backend:** FastAPI on Cloud Run
- **Auth:** Firebase Anonymous Auth (persistent UID, zero-friction)
- **Database:** Cloud Firestore
- **Storage:** Cloud Storage (generated images, videos + uploads)
- **Video:** Veo 3.1 (AI-generated Reels/TikTok clips)
- **Email:** Resend API (calendar invite delivery)
- **Integrations:** Notion API (OAuth + calendar export)
- **Frontend:** React 19 + TypeScript + Vite 7
- **Deployment:** Terraform + Cloud Build (CI/CD)

## Architecture

```
User Browser (React 19) ←REST + SSE→ Cloud Run (FastAPI)
                                       ├── ADK Sequential Pipeline
                                       │   ├── Brand Analyst Agent (temp 0.15)
                                       │   ├── Strategy Agent (social proof tiers)
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
                                       ├── Firebase Anonymous Auth (persistent UID)
                                       ├── Gemini API (generateContent)
                                       │   └── responseModalities: ["TEXT", "IMAGE"]
                                       ├── Cloud Firestore (brands, plans, posts)
                                       └── Cloud Storage (images, videos, assets)
```

See the full [architecture diagram](docs/architecture.mermaid) for agent interactions and data flows.

## Documentation

| Document | Description |
|---|---|
| [Product Requirements (PRD)](docs/PRD.md) | v1.3 — Full product spec with all P0/P1 shipped, P2 features (Platform Registry, Notion, Edit Brand, calendar export) shipped, social proof tier system, Buffer roadmap |
| [Technical Design (TDD)](docs/TDD.md) | v1.3 — Implementation spec covering Platform Registry, Brand Assets Service, Notion/calendar integrations, calibrated review scoring, education-first strategy, voice coach awareness |
| [Architecture Diagram](docs/architecture.mermaid) | Mermaid diagram — full agent pipeline, Platform Registry, Brand Assets, Notion/Email services, GCP data flows |
| [UI Mockup](docs/amplifi-ui.jsx) | Interactive React prototype — 6 screens (Landing, Onboard, Brand, Calendar, Content, Dashboard) |
| [Integration Plan](docs/buffer-notion-integration-plan.md) | Buffer + Notion integration design — OAuth flows, database export, .ics calendar, email delivery. Buffer planned once API exits closed beta. |

## Roadmap

- **Buffer integration** — Buffer is currently in closed beta for their new API and not accepting new developer applications. We plan to integrate Buffer for scheduled publishing once API access becomes available. Full design is documented in [buffer-notion-integration-plan.md](docs/buffer-notion-integration-plan.md).

## Hackathon

Built for the **Gemini Live Agent Challenge** hackathon ($80K prize pool, Google DeepMind / Devpost).

- **Category:** ✍️ Creative Storyteller
- **Deadline:** March 16, 2026 at 5:00 PM PDT
- **Prize Target:** $10K (category) + $5K (subcategory)

## License

MIT
