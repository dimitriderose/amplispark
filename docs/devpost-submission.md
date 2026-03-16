# Amplifi — Devpost Submission

**Category:** Creative Storyteller
**Live Demo:** https://amplifi-seimyaykpa-uc.a.run.app
**Repository:** https://github.com/dimitriderose/amplifi-hackaton

---

## Inspiration

The idea for Amplifi came from a real problem. While building a financial education and research website, I needed to promote it on social media — and quickly realized how fragmented and time-consuming the process was. Writing captions in one tool, generating images in another, reformatting for each platform, trying to keep a consistent brand voice across all of them. It shouldn't take hours to produce a week of content for one brand.

Beyond my own experience, I noticed that AI is enabling more people than ever to build their own applications, websites, and businesses — but promotion is still the bottleneck. Solopreneurs and small businesses that don't have a social media presence (or a marketing team) need a tool that handles the entire content creation workflow for them, not just one piece of it. That's what Amplifi is — a creative director for everyone who can't afford one.

## What It Does

Amplifi takes a brand website URL and produces a complete, ready-to-publish social media content package in minutes. After a 3-step onboarding wizard that extracts brand voice, tone, and identity directly from the live site, it generates a 7-day content calendar with AI-researched platform-specific posting frequencies across 11 platforms — Instagram, LinkedIn, X, TikTok, Facebook, Threads, Pinterest, YouTube Shorts, Mastodon, Bluesky, and more.

Each content piece is generated via a single interleaved Gemini stream: captions and images emerge together, not sequentially, so the image actually reflects what the caption says rather than being retrofitted. Image generation is platform-aware — each prompt is tailored to the platform's aspect ratio, visual conventions, and audience expectations, with 35 visual styles to choose from and brand color/logo integration. Instagram carousels generate all slides in parallel, each slide producing its own interleaved caption + image stream.

For video-first platforms like TikTok and Reels, Amplifi generates short-form video clips via Veo 3.1 directly from the post's hero image or a text prompt. Users can also repurpose any existing post into a video clip with pillar-aware scene direction. Every generated image and video is editable through a natural language media editor — describe the change you want ("make the lighting warmer", "add motion to the background") and the AI applies it.

A real-time Voice Strategy Coach powered by Gemini Live API lets users have a live conversation with an AI that knows their brand, calendar, and performance context. Content is scored on a 5-dimension multiplicative rubric with platform-specific weights, and can be exported to Notion, email, or bulk downloaded as a ZIP.

## How We Built It

The backend is a FastAPI service on Cloud Run, orchestrated with Google ADK agents and secured with Firebase Auth and Fernet-encrypted credential storage in Firestore. Brand assets live in Cloud Storage. The pipeline starts with the Brand Analyst Agent — it scrapes the user's website URL and uses Gemini at temperature 0.15 to extract a full brand DNA: colors, tone of voice, target audience, visual style, industry positioning, and competitive landscape. This brand profile becomes the foundation that every downstream agent builds on — the strategy, the captions, the image prompts, and the voice coach all reference it.

The Strategy Agent then uses Google Search grounding to research optimal posting frequency per platform, identifies content pillars (education, inspiration, promotion, behind-the-scenes, user-generated), and builds a 7-day calendar with social proof tier awareness (new brands get education-first strategy, established brands get data-forward positioning).

The interleaved generation pipeline streams from Gemini 3.1 Flash Image Preview, capturing alternating text and image parts in a single response stream and assembling them into a structured content object on the fly — the frontend renders caption and image as they arrive via SSE.

Image generation uses a dedicated image prompt builder that constructs platform-specific prompts — incorporating brand colors, logo placement, aspect ratios, and one of 35 visual styles (from "editorial minimalist" to "bold graphic"). Instagram carousel slides are dispatched in parallel coroutines, each producing its own interleaved stream, so a 5-slide carousel generates in roughly the time of one slide. Safety validation catches and retries failed image generations with automatic fallback to image-only mode if interleaved output fails.

Video generation uses Veo 3.1 with asynchronous polling — the content creator generates a caption-first pass, then auto-triggers video generation from the hero image. The video repurpose agent takes existing posts and generates clips with pillar-aware scene direction (education posts get explainer-style motion, promotional posts get product showcase dynamics). All generated media is stored in Cloud Storage with GCS URI tracking for downstream editing and export.

The Voice Strategy Coach uses Gemini 2.5 Flash Native Audio via the Live API, with a context payload injected at session start containing the brand profile, the current calendar state, and performance scores so the coach has genuine situational awareness.

The frontend is React 19 + TypeScript on Vite 7, with a custom 11-step guided tour featuring spotlight overlays and tablet/mobile-adaptive tooltip positioning. Infrastructure is fully Terraform-managed with Cloud Build CI/CD.

## Challenges We Ran Into

Getting reliable interleaved output from the streaming API was the hardest technical problem — the model sometimes front-loads all text before emitting images, defeating the purpose of interleaving. We had to tune prompts to explicitly signal the interleaved structure and build a stream parser that handles both orderings gracefully so the UI never breaks regardless of how the model chooses to sequence parts.

Calibrating the multiplicative scoring system was surprisingly subtle: a 5-dimension product amplifies small biases, so a slightly mis-weighted platform rubric would tank otherwise good content. We ran dozens of calibration passes across real brand examples before the scores felt trustworthy.

Image generation required extensive prompt engineering per platform — an Instagram carousel slide needs a different composition, aspect ratio, and visual density than a LinkedIn thought leadership post or a Pinterest pin. Early image prompts produced generic stock-photo results that didn't reflect the brand. We built a dedicated image prompt builder with 35 visual style mappings and brand-aware prompt construction (injecting colors, logo placement, audience context) to get images that actually feel on-brand. Safety validation was another challenge — image generation can silently fail or return blocked content, so we added retry logic with automatic fallback to image-only mode when interleaved output fails.

Video generation with Veo 3.1 had its own calibration issues — scene descriptions that work for static images don't translate well to motion. We built a video repurpose agent with pillar-aware scene direction so education posts get explainer-style motion while promotional posts get product showcase dynamics. Video file sizes also needed management — early generations produced oversized clips that exceeded storage thresholds.

Making the 11-step guided tour work across desktop, tablet, and mobile required a custom spotlight overlay system with dynamic tooltip positioning that recalculates anchor targets on every resize and orientation change. The Voice Strategy Coach required careful context injection design — Gemini Live sessions are stateless, so we had to serialize the relevant brand and calendar state into a compact context payload at connection time without exceeding token budget.

We wanted to implement direct publishing through Buffer, but they're currently not accepting new developer applications until their new API launches. Rather than wait, we pivoted and built three alternative export methods — Notion database sync, .ics calendar email delivery, and bulk ZIP download — so users still have a complete workflow from generation to distribution.

## Accomplishments That We're Proud Of

The interleaved stream pipeline is genuinely novel UX — watching a caption and its matching image appear together in a single generation stream, knowing both came from one model call reasoning about them jointly, feels qualitatively different from any existing tool we've seen. The parallel carousel architecture means a 5-slide Instagram carousel with full captions and images completes in roughly the same wall-clock time as a single post. The image prompt builder produces visuals that actually look like they belong to the brand — not generic stock imagery, but images with the brand's color palette, visual style, and audience context baked into every prompt. Video generation via Veo 3.1 means a complete post — caption, image, and video clip — can be produced from a single generation trigger.

The Brand Analyst Agent can take any website URL and produce a complete brand identity — colors, tone, audience, visual style, competitive positioning — without the user filling in a single field. That zero-config onboarding means a user can go from "here's my URL" to a full week of brand-consistent content in minutes, not hours.

We shipped a full production deployment on Cloud Run with Firebase Auth, Fernet-encrypted secrets, Firestore, Cloud Storage, and Terraform IaC — not a prototype, a real multi-tenant system where multiple brands per account are fully isolated. The voice coach actually knows your brand: it can discuss your pending Tuesday LinkedIn post by name because we engineered the context injection to include the live calendar state.

## What We Learned

Gemini's interleaved output is a creative primitive that changes the design space — when caption and image are co-generated, you get semantic coherence you can't achieve by chaining separate model calls, but you have to explicitly prompt for the interleaved structure or the model will serialize the outputs. Working with the Live API taught us that stateless sessions require disciplined context serialization: everything the voice agent needs to be useful must be packed into the session-open payload, which forces you to think carefully about what "context" actually means for a creative workflow.

On the image side, we learned that generic image prompts produce generic results — the difference between a forgettable stock-photo look and a brand-consistent visual comes down to injecting the right context (colors, style, audience, platform conventions) into every prompt. Platform matters too: what looks great as a square Instagram post falls apart as a vertical Pinterest pin if you don't adapt composition and density per format.

For video, we learned that Veo 3.1 responds very differently to scene descriptions written for static images versus ones written for motion. A prompt that produces a beautiful still image can generate an awkward, static-feeling video. We had to develop pillar-aware scene direction — giving the model motion-specific language like "slow pan" or "dynamic zoom" tuned to the content type — to get clips that actually feel like short-form social video.

We also learned that giving creators the ability to edit generated images, videos, and captions in natural language is just as important as the initial generation. The first output is rarely the final output — creators need to tweak, refine, and put their own stamp on it. Building the AI media editor turned out to be one of the most powerful features because it keeps the creator in control without breaking them out of the workflow.

Multiplicative scoring systems are more fragile than additive ones during calibration, but produce more meaningful differentiation at the top end — the math punishes inconsistency in a way that matches how audiences actually respond to off-brand content.

## What's Next for Amplifi

Direct publishing via Buffer is at the top of the list — once their new API opens to developers, we'll add one-click scheduling to all 11 platforms. We're also building out a social voice feature that lets the Voice Strategy Coach not just advise on content but help craft your brand's social voice over time through ongoing conversation. An analytics dashboard is next — connecting platform performance data so Amplifi can see which types of posts drive the most engagement and feed those insights back into future content generation, making each week's calendar smarter than the last. A/B testing (generating two variants per post and tracking which performs better), team collaboration with role-based access (strategist, designer, approver), and pushing interleaved generation to video — scripts + Veo clips in a single stream — are all on the roadmap.

## Built With

Gemini 3 Flash, Gemini 3.1 Flash Image Preview, Gemini 2.5 Flash Native Audio, Veo 3.1, Google ADK, Google GenAI SDK, FastAPI, Python, Google Cloud Run, Cloud Firestore, Cloud Storage, Cloud Build, Artifact Registry, Firebase Auth, Terraform, React 19, TypeScript, Vite 7, Notion API, Resend API

---

## Try It Out

- **Live App:** https://amplifi-seimyaykpa-uc.a.run.app
- **GitHub:** https://github.com/dimitriderose/amplifi-hackaton
- **Demo Video:** *(YouTube link — add after upload)*
