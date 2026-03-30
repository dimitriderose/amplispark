# Amplispark — Playtest Personas

## Overview

Two small business personas reviewed the Amplispark codebase and UI across 5 rounds, followed by a specialist review from a professional Social Media Content Specialist. The panel evaluated UX fixes incrementally as they were merged to `main`, reviewed live AI-generated output in Round 3, watched a full live website recording in Round 4, then navigated the full live website hands-on in Round 5 — covering Notion OAuth integration, Export & Share dropdown, Video Repurposing tab, Edit Brand page, and dedicated Export page. The specialist review (Priya) assessed Amplispark from a professional content operations perspective.

| Round | Composite | Delta | HEAD Commit |
|-------|-----------|-------|-------------|
| Round 1 (21+ Fixes: DK/H/M/L tiers) | 8.25/10 | — | `2b6642e` |
| Round 2 (3 Flag Fixes) | 9.25/10 | +1.0 | `b738285` |
| Round 3 (Live Output Review) | 9.4375/10 | +0.1875 | `a9e544d` |
| Round 4 (Live Website Recording) | 9.625/10 | +0.1875 | `a9e544d` |
| Round 5 (Live Website Demo — 10 Screens) | 9.8125/10 | +0.1875 | `7a706ed` |

**Final Verdict:** Ship it. 9.8125 two-persona composite after 5 rounds (+1.5625 total). 9.125 three-persona composite (with Priya specialist review). Voice Coach remains the sleeper differentiator. All prior flags resolved. Buffer integration is the only remaining wish — accepted as deferred (closed beta). Notion connected, 4 export paths live, Edit Brand + Content Strategy operational.

---

## Persona Profiles

### 🧑‍🍳 Maria — The Small Business Owner

| Attribute | Detail |
|-----------|--------|
| Age | 37 |
| Business | Verde Kitchen — farm-to-table restaurant, Brooklyn |
| Team Size | 12 employees |
| Social Media Habit | Does social media Sunday nights in a batch session |
| Primary Platform | Instagram (food photography, stories) |
| Secondary Platform | Facebook (events, community) |
| Tech Comfort | Uses iPhone for photos, has never used AI tools |
| Content Style | Warm, artisanal, community-focused. Own photography. |
| Key Constraint | Time. Sunday night is the only window. Every extra tap is a reason to give up and post nothing. |

### 💼 Jason — The Solopreneur Coach

| Attribute | Detail |
|-----------|--------|
| Age | 42 |
| Business | Executive leadership coaching (Austin) |
| Background | Former VP Engineering at a mid-size tech company |
| Primary Platform | LinkedIn (8K followers — CTOs, VPs, engineering leaders) |
| Secondary Platform | X/Twitter (shorter-form thought leadership) |
| Posting Frequency | 3–4x/week |
| Writing Standards | High. Posts in Notion first, schedules via Buffer. Reads every word before publishing. |
| Content Style | Authoritative, no-emoji, long-form for LinkedIn. Punchy hot-takes for X. |
| Key Constraint | Quality. If AI content reads like generic LinkedIn engagement bait, he's out immediately. |

### 📱 Priya — The Social Media Content Specialist

| Attribute | Detail |
|-----------|--------|
| Age | 31 |
| Role | Head of Social at a 40-person B2B SaaS company (Series A, $8M ARR) |
| Background | 6 years agency-side (ran social for 12+ brands simultaneously), 2 years in-house |
| Primary Platforms | LinkedIn (company + exec ghostwriting), Instagram (brand), X (product updates), TikTok (emerging) |
| Team | 2 direct reports (designer + community manager), freelance video editor |
| Tools Currently Using | Sprout Social ($249/mo), Canva Pro, Notion for editorial calendar, ChatGPT for first drafts, CapCut for video |
| Weekly Output | 25-30 posts across 4 platforms for 1 brand + 3 executive accounts |
| Content Style | Data-driven. Every post ties to a campaign brief. Tracks UTM links, engagement rate per platform, conversion attribution. |
| Key Constraint | Scalability. She doesn't need help writing *one* caption. She needs a system that maintains brand consistency across 25+ posts/week while she manages a team, reports to a CMO, and executes campaigns with measurable KPIs. |
| Evaluator Bias | Skeptical of AI content tools. Has tried Jasper, Copy.ai, Lately, and Hootsuite's AI features. All produced generic output that required more editing than writing from scratch. "If I have to rewrite every caption, the AI isn't saving me time — it's wasting it." |

**Why Priya matters:** Maria and Jason are end users — small business owners doing their own social media. Priya is the professional who does this for a living. She manages content at scale, reports on performance metrics, and has tried every AI content tool on the market. Her assessment reveals whether Amplispark is a toy for solopreneurs or a tool that can serve working content professionals.

---

## Round 1 — Baseline Review (21+ Fixes Merged)

**Codebase state:** All DK-1 through DK-5 (demo-killers), H-1 through H-8 (high-priority), M-1 through M-8 and L-1 through L-8 (polish) fixes merged. ~172KB across 17 files.

### Maria's Review — 8.5/10

| Screen | Score | Key Feedback |
|--------|-------|--------------|
| Landing | 9/10 | "No sign-up, no credit card" is the difference between trying and closing the tab. "Describe your business" over "Paste your URL" (L-1 fix) is smarter — Verde Kitchen doesn't have a marketing-ready website. |
| Onboard | 8.5/10 | Pulsing "Finalizing..." animation prevents confusion during brand analysis. Animated 6-step plan generation is educational — "I can see it building my strategy." |
| Dashboard | 9/10 | EventsInput analysis lock (DK-1) prevents silent failure. Animated plan generation turns loading into education. BrandProfileCard is editable with async save feedback. |
| Generate | 8.5/10 | Human-readable subtitle with day/platform/theme context (H-2). Back button always goes to dashboard (H-1). Caption-only mode (M-3) essential — "I use my own photos, I just need the words." |
| Review | 9/10 | Auto-review on mount (DK-3) saves a click on every post. Copy button with timer cleanup. "Next Day →" CTA (L-8) creates the Sunday night batch workflow. |
| Export | 8.5/10 | Approved-only ZIP filter (M-8) is correct. But Maria really wants clipboard-per-post, not a ZIP download. |
| Video | 7/10 | Grayed out on non-video platforms is better than hidden, but adds visual noise when she's only making Instagram caption posts. |
| Voice Coach | 7.5/10 | Tooltip helps explain the feature. Demo voice data button is nice for first-time exploration. |
| **Overall** | **8.5/10** | |

**Maria's biggest concern:** "Need to see content *look* like Verde Kitchen content. AI-generated image quality and brand consistency is everything. UI workflow is exactly right for Sunday night batch, but can't judge output quality from code alone."

### Jason's Review — 8/10

| Screen | Score | Key Feedback |
|--------|-------|--------------|
| Landing | 7.5/10 | Value prop is clear but generic. Platform list (Instagram, TikTok, Facebook) suggests visual-first bias. LinkedIn should be more prominent for B2B users. |
| Onboard | 8.5/10 | Animated 6-step progress feels premium. "Describe your business" is the right CTA. |
| Dashboard | 8/10 | BrandProfileCard editing is critical for voice verification — "I need to see what the AI thinks my voice sounds like and correct it." ContentCalendar pillar-based strategy maps to his workflow. |
| Generate | 9/10 | Caption-only mode is *essential* for text-first creators. Grid switching to full-width caption when `captionOnly=true` is exactly right. |
| Review | 8/10 | Auto-review saves a click. Brand alignment score is what matters most. `revised_caption` field means Review Agent rewrites — this is where the tool wins or loses. Quality depends entirely on prompt engineering behind the agent. |
| Export | 7.5/10 | Wants Buffer-compatible CSV, not ZIP. His workflow is: generate → review → export to Notion → schedule in Buffer. ZIP adds friction. |
| Video | 6/10 | Grayed out is better than hidden, but adds visual noise for text-first creators. "I never use video on LinkedIn. This section shouldn't take up screen real estate when I'm writing captions." |
| Voice Coach | 8/10 | Conceptually sound for maintaining brand voice. But demo voice data is Instagram-only — his business runs on LinkedIn. Sample should match platform. |
| **Overall** | **8/10** | |

**Jason's biggest concern:** "ReviewPanel has `revised_caption` field, meaning the Review Agent rewrites. The tool either wins or loses here. If revised caption reads like generic LinkedIn engagement bait, I'm out. If it reads like something I'd actually write, I'm in. Can't evaluate output quality from codebase. Architecture is right, but prompt engineering behind Review Agent is what matters."

### Unanimous Wins (Round 1)

1. **No sign-up / no credit card** — single biggest conversion factor for both personas
2. **"Describe your business" over "Paste your URL"** (L-1) — URL-first is a barrier for small businesses
3. **Caption-only mode** (M-3) — essential for both use cases (own photos for Maria, text-first for Jason)
4. **Auto-review on mount** (DK-3) — removes a step from every post
5. **"Next Day →" CTA** (L-8) — creates batch workflow
6. **Animated plan generation** (DK-2) — turns loading into education
7. **Analysis lock on EventsInput** (DK-1) — prevents silent failure

### Flags (Round 1)

| # | Flag | Maria | Jason | Severity |
|---|------|-------|-------|----------|
| 1 | Demo voice data is Instagram-only (DK-4) | Neutral (Instagram is her platform) | 7.5/10 — "My business runs on LinkedIn, sample should match platform" | High |
| 2 | Export format is ZIP-only | 8.5/10 — Wants clipboard-per-post | 7.5/10 — Wants Buffer-compatible CSV | High |
| 3 | Video section noise for text-first users (H-6) | 7/10 — Adds noise when making caption posts | 6/10 — "I never use video on LinkedIn" | Medium |
| 4 | Output quality unknowable from code | Both flagged as make-or-break | Both flagged as make-or-break | Expected (requires live demo) |

---

## Round 2 — 3 Flag Fix Branches + MUST FIX Follow-ups

**Fixes merged:** 3 new feature branches directly addressing Round 1 flags.

### Feature 1: Per-Platform Demo Voice Data

**Commits:** `85e5b0a` + `8b86867` fix + `13e5421` merge

- Replaced single Instagram-only demo button with per-platform "try demo" links on each platform card
- **LinkedIn demo:** B2B executive coaching persona — no emoji, long-form, authoritative
- **Instagram demo:** Warm artisanal food/lifestyle (existing data kept)
- **X/Twitter demo:** Punchy, opinionated, short-form hot-take style
- Global "Try with sample voice data" button removed; demo links live inline on each card
- Fix: `type="button"` prevents form submit, `hasAnyActive` covers all 4 voice-analysis data sources, click target padding increased

### Feature 2: Video Collapse for Text-First Platforms

**Commits:** `c2924cb` + `c407a27` fix + `4006a61` fix + `71db2ac` merge

- TEXT_PLATFORMS set: LinkedIn, X, Twitter, Facebook
- Text-first platforms show collapsed pill: "🎬 Video Clip (not typical for this platform) ›"
- Click to expand, "‹ collapse" to restore
- State resets to collapsed on every new post/day switch
- Video platforms (Instagram, TikTok, Reels) unchanged — fully expanded
- Fixes: pill visibility (font 11→12, border/background/hover tint for interactivity), 'x' added to PLATFORM_ICONS to prevent silent 📱 fallback

### Feature 3: Clipboard-First Export

**Commits:** `3fb7f4a` + `f49c1d2` fix + `b738285` merge

- "📋 Copy All" button in PostLibrary header row (between Refresh and Export)
- Structured clipboard format:
  ```
  [1] Instagram · Day 1
  caption text
  #hashtag1 #hashtag2

  ---

  [2] LinkedIn · Day 2
  ...
  ```
- "✓ Copied N" confirmation flash for 1.5s
- Count snapshotted at click time via ref (not re-derived at render) to avoid drift during polling refresh
- Timer cleaned up on unmount
- ExportPage subtitle updated: "Copy captions to clipboard" as primary path before ZIP download

### Maria's Review — 9/10 (+0.5)

| Screen | R1 | R2 | Key Feedback |
|--------|----|----|--------------| 
| Landing | 9 | 9 | No change. |
| Onboard | 8.5 | 8.5 | No change. |
| Dashboard | 9 | 9.5 | Per-platform demo data on Instagram card shows warm artisanal food/lifestyle voice — "the tool understands what restaurant content sounds like." |
| Generate | 8.5 | 8.5 | No change. |
| Review | 9 | 9 | No change. |
| Export | 8.5 | **9.5** | "Copy All is exactly what I wanted. Sunday night at 11pm, I don't want to download a ZIP. I want to tap one button, open Instagram, paste." Structured format with `[1] Instagram · Day 1` headers lets her scan and find the right day. "✓ Copied 7" confirmation tells her everything is in clipboard. |
| Video | 7 | 7 | Doesn't affect her much — Instagram-primary with own videos. Neutral. |
| Voice Coach | 7.5 | 7.5 | No change. |
| **Overall** | **8.5** | **9** | |

**Maria's remaining concern:** "Same as before — need to see actual generated content quality. The workflow is now nearly frictionless. If the AI writes captions that sound like Verde Kitchen and not generic food content, this is a 10."

### Jason's Review — 9.5/10 (+1.5)

| Screen | R1 | R2 | Key Feedback |
|--------|----|----|--------------| 
| Landing | 7.5 | 7.5 | No change. |
| Onboard | 8.5 | 8.5 | No change. |
| Dashboard | 8 | **9** | Per-platform demo: LinkedIn shows B2B executive coaching persona — "no emoji, long-form, authoritative. That's my voice." This is the difference between "this tool is for restaurants" and "this tool understands professional thought leadership." `hasAnyActive` fix means stored analyses persist correctly across sessions. |
| Generate | 9 | **9.5** | Video collapse for LinkedIn: collapsed pill "🎬 Video Clip (not typical for this platform) ›" — "I don't have to scroll past a grayed-out video section that's irrelevant to my workflow." One tap to expand if needed. State resets per-post. |
| Review | 8 | 8.5 | Per-platform demo data gives confidence the team understands voice differentiation. If demo data is this thoughtful, prompt engineering is probably solid too. |
| Export | 7.5 | **9** | "Copy All solves my Buffer workflow better than CSV would. I copy all 7 captions, paste into Notion, do final edits, schedule in Buffer." Structured format with `[1] LinkedIn · Day 1` headers lets him parse which post goes where. Snapshotted count prevents confusion during polling refresh. |
| Video | 6 | **9** | Collapsed pill is exactly what he asked for. "The pill has visible weight — border, background, hover state signal interactivity without competing with the caption section." |
| Voice Coach | 8 | 8 | No change. |
| **Overall** | **8** | **9.5** | |

**Jason's remaining concern:** "Output quality is still unknowable from code. But the per-platform demo data gives me confidence the team understands voice differentiation across platforms. If they put that care into demo data, the prompt engineering behind the Review Agent is probably solid too. Seeing a generated LinkedIn post that reads like something I'd write is the only remaining gate."

### Flag Resolution Status (Round 2)

| # | Flag | R1 Status | R2 Resolution | Resolved? |
|---|------|-----------|---------------|-----------|
| 1 | Demo voice data Instagram-only | Jason 7.5/10 | Per-platform demos: LinkedIn B2B, Instagram artisanal, X punchy | **Yes** |
| 2 | Export format ZIP-only | Jason 7.5, Maria "just paste" | "Copy All" clipboard-first + structured format | **Yes** |
| 3 | Video section noise for text-first | Jason 6/10 | Collapsed pill on LinkedIn/X/Facebook, expandable on click | **Yes** |
| 4 | Output quality unknowable from code | Both flagged | Still unknowable — requires live demo | **Open (expected)** |

---

## Round 3 — Live Output Review (AI-Generated Content)

**Context:** Both personas watched a screen recording of Amplispark generating real content for a CPA firm (Derose & Associates). This is the first time either persona has seen actual AI-generated output — captions, images, video, and brand review — not just the UI shell.

**What the recording shows:**
1. Instagram post: "Essential Tax Season Checklist for Businesses" — full caption mentioning Derose & Associates, NYC and Long Island, tax deadlines
2. AI-generated image — professional styled tax checklist with coffee cup, on-brand
3. Hashtags — #TaxSeason, #BusinessTax, #TaxPreparation, #SmallBusiness, #DeroseAndAssociates, #TaxReady, plus junk hashtags (#Here's, #an, #image, #for, #your, #post:)
4. Veo 3 video clip — 8-second animated version of the checklist image
5. AI Brand Review — Score 9/10 "STRONG BRAND ALIGNMENT", auto-approved, engagement predictions (Hook: 9, Relevance: 10, CTA: 9, Platform Fit: 8), strengths, suggested improvements
6. "Next Day → Day 2" CTA for batch workflow

### Maria's Review — 9.25/10 (+0.25)

| Screen | R2 | R3 | Delta | Notes |
|--------|----|----|-------|-------|
| Landing | 9 | 9 | — | |
| Onboard | 8.5 | 8.5 | — | |
| Dashboard | 9.5 | 9.5 | — | |
| Generate | 8.5 | **9.5** | +1.0 | Caption reads like a real business wrote it — mentions firm by name, references NYC and Long Island, has a clear dual CTA. Image looks like a styled stock photo shoot. Veo 3 clip is usable as a Reel intro. |
| Review | 9 | **9.5** | +0.5 | Brand review caught hashtag pollution, engagement prediction bars are useful, auto-approved at 9/10 is well-calibrated. |
| Export | 9.5 | 9.5 | — | |
| Video | 7 | **8.5** | +1.5 | "That 8-second animated checklist is actually usable as a Reel intro. My Sunday night workflow just got a video option I didn't expect." |
| Voice Coach | 7.5 | 7.5 | — | |
| **Overall** | **9.0** | **9.25** | **+0.25** | |

**Maria's key quotes:**
- Caption: "It reads like a real business wrote it, not an AI. The tone is professional but approachable — warm without being corny."
- Image: "That image looks like something from a real accounting firm's Instagram. The coffee cup, the professional lighting, the checklist with checkmarks — it doesn't look AI-generated in the 'melted fingers' way."
- Hashtags: "The first 8 hashtags are great. The last 5 (`#Here's #an #image #for #your #post:`) are garbage. The Review Agent caught it — but it should have auto-fixed it, not just flagged it."

**Maria's remaining flag:** Hashtag pollution needs to be auto-cleaned, not just flagged. That's the only thing stopping her from hitting Copy All and pasting straight into Instagram without editing.

### Jason's Review — 9.625/10 (+0.125)

| Screen | R2 | R3 | Delta | Notes |
|--------|----|----|-------|-------|
| Landing | 7.5 | 7.5 | — | |
| Onboard | 8.5 | 8.5 | — | |
| Dashboard | 9 | 9 | — | |
| Generate | 9.5 | **10** | +0.5 | "This caption opens with a benefit-driven hook, establishes urgency, then provides structured value. The CTA is dual-track. For Instagram, this is well-structured." Output quality matches UX quality — the gate is cleared. |
| Review | 8.5 | **10** | +1.5 | "This is where the tool differentiates itself from every other AI content tool. Score 9/10 with specific engagement predictions, actionable strengths, and improvement suggestions. The Review Agent caught the hashtag pollution before I did." |
| Export | 9 | 9 | — | |
| Video | 9 | 9 | — | |
| Voice Coach | 8 | 8 | — | |
| **Overall** | **9.5** | **9.625** | **+0.125** | |

**Jason's key quotes:**
- Caption: "The fact that this Instagram post reads like a professional accountant talking to small business owners — not like generic AI slop — tells me the Brand Analyst and Content Creator agents are working."
- Brand Review: "Score 9/10 with specific engagement predictions, actionable strengths, and improvement suggestions. The Review Agent caught the hashtag pollution before I did. That's the kind of quality control that makes me trust the system."
- Architecture: "The per-platform demo data gave me confidence the team understands voice differentiation. The live output confirms it. The architecture delivers."

**Jason's verdict:** "Flag 4 is resolved. The output quality matches the UX quality. The one remaining issue — hashtag auto-cleaning — is a P1 bug, not an architecture problem. The Review Agent already identifies the issue; it just needs to execute the fix instead of only flagging it. Ship it."

---

## Round 4 — Live Website Recording Review

**Context:** Both personas watched a 2:55 screen recording of the live Amplispark website running end-to-end in a browser. This is the first time they've seen the complete app flow — landing page, dashboard with live data, content generation, Voice Coach live conversation, Veo 3.1 video, and AI Brand Review — as a continuous real-time experience.

**What the recording shows (timestamp map):**

| Time | Screen | Content |
|------|--------|---------|
| 0:00 | Landing Page | "Your entire week of content. One click." + platform badges (Instagram, LinkedIn, Twitter/X, Facebook) + "How it works: From zero to a week of brand-consistent content in under 3 minutes" |
| 0:09 | Dashboard | Full Brand Profile (Derose & Associates) + 7-Day Content Calendar — Mon/Tue approved (9/10, 7/10), Wed approved, Thu-Sun with Generate buttons. Pillar color-coding (education/blue, promotion/red, inspiration/purple, behind scenes/green, user generated/orange). Voice Coach widget open. |
| 0:15 | Generate Post | LinkedIn Day 3 "Advanced Tax Strategies for Small Businesses" — live streaming caption + image generation with progress indicators |
| 0:20 | Post Complete | Full LinkedIn caption with Copy button, AI-generated professional image, "HOW THIS LOOKS ON LINKEDIN" platform preview, clean hashtags (#SmallBusinessTax, #TaxStrategy, #FinancialPlanning, #BusinessGrowth, #TaxTips) |
| 0:30 | Dashboard + Voice Coach | Voice Coach widget: "Listening... Continuing conversation..." — multi-turn brand-contextualized dialogue |
| 0:50 | Voice Coach Active | "*Acknowledging the Appreciation* I'm feeling positive after the expressed gratitude! As Derose & Associates' AI brand strategist..." |
| 1:10 | Voice Coach Speaking | "*Resuming Facebook Strategy* I'm ready to dive back into our Facebook strategy discussion for Derose & Associates. Following..." |
| 1:40 | Veo 3.1 Video Clip | "Video Clip (Veo 3.1)" — 8-second animated notebook/coffee/hand-writing clip |
| 2:00 | AI Brand Review | Score 9/10 "STRONG BRAND ALIGNMENT", Auto-approved. Engagement Predictions: Hook 9, Relevance 9, CTA 8, Platform Fit 9. Strengths (3 items), Suggested Improvements (direct link/DM CTA). "Done — Go to Dashboard" + "Re-review" buttons. |
| 2:30 | Dashboard + Voice Coach | "*Defining the Approach* I'm now zeroing in on Facebook advertising strategies. My focus is laser-targeted for Derose &..." |
| 2:55 | End | |

### Maria's Review — 9.5/10 (+0.25)

| Screen | R3 | R4 | Delta | Notes |
|--------|----|----|-------|-------|
| Landing | 9 | **9.5** | +0.5 | "Seeing it live changes everything. The landing page with Derose & Associates already listed under YOUR BRANDS with a green 'Ready' badge — it's not just a promise, the brand is already loaded. 'How it works' section below the fold is new to me." |
| Onboard | 8.5 | 8.5 | — | Not shown in recording |
| Dashboard | 9.5 | **10** | +0.5 | "The calendar is alive. Mon and Tue show 'Approved 9/10' with green badges. Wed shows 'Approved 7/10'. The rest have Generate buttons. I can see the batch workflow happening — three posts already done, four to go. The Voice Coach is just there, floating in the corner, having a conversation about Facebook strategy while I'm looking at the calendar. It's like having a marketing intern on a call in the background." |
| Generate | 9.5 | 9.5 | — | "Watching it stream the LinkedIn caption in real-time while simultaneously generating the image — that's satisfying. The progress indicators tell me what it's doing at every step." |
| Review | 9.5 | **10** | +0.5 | "The LinkedIn post review is even cleaner than the Instagram one from Round 3. Hashtags are all professional — no junk hashtags this time! Engagement predictions are slightly different per platform. The Suggested Improvements actually suggests adding a direct link or 'DM us to learn more' CTA. That's specific and actionable." |
| Export | 9.5 | 9.5 | — | Not shown in recording |
| Video | 8.5 | **9** | +0.5 | "Video Clip labeled '(Veo 3.1)' — collapsed as '(not typical for this platform)' on LinkedIn. Exactly what Jason asked for. Expands to show the notebook/coffee clip." |
| Voice Coach | 7.5 | **9** | +1.5 | "THIS is the feature I didn't understand from code. The Voice Coach is having a real conversation — acknowledging what Dimitri said, then pivoting to Facebook strategy with specific recommendations for the CPA firm. It remembers the brand context across the whole conversation. That's not a chatbot, that's a strategist." |
| **Overall** | **9.25** | **9.5** | **+0.25** | |

**Maria's key quote:** "The Voice Coach sold me. In the code review it was just a floating button with a tooltip. Watching it actually have a multi-turn brand strategy conversation while the dashboard is right there — I can picture myself using this on Sunday night. Generate my posts, then ask the Voice Coach 'what should I post about this week's farm delivery?' and get back a real answer in my brand voice."

### Jason's Review — 9.75/10 (+0.125)

| Screen | R3 | R4 | Delta | Notes |
|--------|----|----|-------|-------|
| Landing | 7.5 | **8.5** | +1.0 | "The landing page with a real brand loaded changes the pitch entirely. 'Derose & Associates — Accounting & Financial Services' with platform badges. This isn't a mockup. 'From zero to a week of brand-consistent content in under 3 minutes' — that's the claim, and the recording proves it." |
| Onboard | 8.5 | 8.5 | — | Not shown |
| Dashboard | 9 | **10** | +1.0 | "The 7-Day Content Calendar with live status is everything. Mon/Tue approved at 9/10 and 7/10. Color-coded pillar tags. Mixed formats across days. 9 Content Themes visible. This is a content strategist's dashboard, not a content spinner's dashboard." |
| Generate | 10 | 10 | — | "LinkedIn caption streams in real-time. Professional tone, benefit-driven hook, structured value. Confirmed what I saw in Round 3." |
| Review | 10 | 10 | — | "Clean hashtags on LinkedIn post. Engagement predictions consistent. Review Agent suggestions are platform-specific. Architecture continues to deliver." |
| Export | 9 | 9 | — | Not shown |
| Video | 9 | 9 | — | "Collapsed pill on LinkedIn confirmed live. Works exactly as designed." |
| Voice Coach | 8 | **9.5** | +1.5 | "The Voice Coach is the sleeper feature. Watching it maintain brand context across a multi-turn conversation about Facebook strategy for a CPA firm — '*Resuming Facebook Strategy* I'm ready to dive back into our Facebook strategy discussion for Derose & Associates.' It remembered the topic from earlier in the conversation. '*Defining the Approach* I'm now zeroing in on Facebook advertising strategies...' — that's Gemini Live Audio doing real work, not a chatbot parlor trick. For a B2B coach like me, being able to talk through content strategy while looking at my calendar is a workflow multiplier." |
| **Overall** | **9.625** | **9.75** | **+0.125** | |

**Jason's key quote:** "Two things changed my mind in this recording. First, the calendar with live approval badges — seeing 3 of 7 posts already at 9/10 and 7/10 tells me the batch workflow actually works at scale, not just for one demo post. Second, the Voice Coach. That's the Gemini Live Audio integration that differentiates this from every Buffer/Hootsuite/Jasper clone. It's not generating content — it's having a strategic conversation about my content while I'm looking at my content calendar. That's a fundamentally different product category."

### Key Round 4 Observations

| # | Observation | Maria | Jason | Impact |
|---|------------|-------|-------|--------|
| 5a | Hashtag pollution appears fixed on LinkedIn | ✅ Clean hashtags observed | ✅ Confirmed clean | P1 may be resolved |
| 6 | Voice Coach is the sleeper differentiator | +1.5 score jump (7.5→9) | +1.5 score jump (8→9.5) | Both personas upgraded after seeing live conversation |
| 7 | Calendar with live approval badges validates batch workflow | "Three done, four to go" | "Works at scale, not just one demo" | Dashboard is the anchor screen |

---

## Round 5 — Live Website Demo Review (10 Screens)

**Context:** Both personas navigated the full live Amplispark website running on localhost — every screen, every interaction, every feature. This is the first time they've explored the complete app hands-on rather than watching a recording. New since Round 4: Notion OAuth integration (live and connected), Export & Share dropdown with 4 export paths, Video Repurposing tab, full Edit Brand page with Content Strategy section, and dedicated Export page.

**What the demo covers (10 screens):**

| # | Screen | Key Content |
|---|--------|-------------|
| 1 | Landing Page | Hero, hackathon badge, YOUR BRANDS with green "Ready" badge, platform pills, How it Works, 6 capability cards |
| 2 | Onboarding | "Tell us about your brand" — description, brand assets upload, website URL expander, Build My Brand Profile CTA |
| 3 | Dashboard/Calendar | Brand header with ✓ Notion badge, 7-Day Content Calendar with AI images, brand scores 7-8/10, pillar color-coding, Voice Coach |
| 4 | Edit Brand | Brand Identity, Visual Identity (colors, style, image/caption directives), Brand Assets (logo + upload), Content Strategy (8 themes, 3 competitors), Save/Re-Analyze/Cancel |
| 5 | Posts Library | 7 post cards with Copy/Export/Approve per card, Copy All button, Export & Share dropdown |
| 6 | Export & Share Dropdown | DOWNLOAD (ZIP with media, Calendar .ics), PUBLISH (Export to Notion), SHARE (Email calendar) |
| 7 | Post Detail | Caption editor, carousel image viewer (1/3), Instagram platform preview, 5/5 hashtags, 455/2200 char count, Regenerate |
| 8 | AI Brand Review | Score 8/10 "STRONG BRAND ALIGNMENT", Auto-approved, Engagement Prediction (Hook 9, CTA 8, Relevance 9, Platform Fit 8), Strengths, Suggested Improvements, Next Day → Day 2 |
| 9 | Connections Tab | Social Voice Analysis (LinkedIn/Instagram/X with try demo + Connect), Publish & Export (Notion ✓ Connected to "Dimitri DeRose's Notion" workspace) |
| 10 | Video Tab | Video Repurposing — upload mp4/mov up to 500MB → extract 2-3 platform-ready short clips |
| 11 | Export Page | Dedicated export page with ZIP download, Approved filter, Export & Share dropdown |

### Maria's Review — 9.75/10 (+0.25)

| Screen | R4 | R5 | Delta | Notes |
|--------|----|----|-------|-------|
| Landing | 9.5 | **10** | +0.5 | "Welcome back — pick up where you left off" banner with a direct 'Open Derose & Associates →' button. I don't even have to scroll. The returning user experience is a separate flow from the first-time flow. That's product polish." |
| Onboard | 8.5 | **9** | +0.5 | "Seeing the actual onboarding page live — 'Tell us about your brand' with the bakery example as placeholder text, drag-and-drop for brand assets, and 'Have a website? Paste it for even better results' as an expandable section rather than a required field. That respects how small businesses actually work. Not everyone has a marketing-ready website." |
| Dashboard | 10 | 10 | — | "Still a 10. The ✓ Notion badge next to the tone tags is the new detail I noticed. It's not buried in settings — it's right in the brand header where I can see my connection status at a glance." |
| Generate | 9.5 | 9.5 | — | |
| Review | 10 | 10 | — | "Engagement Prediction bars with actual numbers — Hook 9, CTA 8, Relevance 9, Platform Fit 8. Strengths with green checkmarks calling out specific things like the De Minimis Safe Harbor strategy. Suggested Improvements telling me to add a relatable example. This is an AI explaining its own work and critiquing it. That's trust-building." |
| Export | 9.5 | **10** | +0.5 | "The Export & Share dropdown is everything. Four paths: ZIP with media for when I want to save everything offline, .ics Calendar for Google/Apple/Outlook, Export to Notion for my planning system, and Email calendar to send the schedule to my business partner. I don't have to choose one workflow — I can use all of them depending on the situation." |
| Video | 9 | **9.5** | +0.5 | "Video Repurposing as its own tab — upload a raw video and get 2-3 platform-ready clips. That's different from the Veo 3 generation on individual posts. This is for repurposing my existing content. Upload my farm delivery video, get an Instagram Reel and a TikTok out of it. Sunday night just got even more efficient." |
| Voice Coach | 9 | 9 | — | |
| Connections | — | **10** | NEW | "This is the screen that changes the product. Left side: connect my real LinkedIn, Instagram, X accounts so Amplispark can match my writing style. Right side: Notion already connected to 'Dimitri DeRose's Notion' with a selected database and a 'change' option. The 'try demo' links next to each social account lower the barrier — I can see what voice analysis looks like before connecting my real accounts." |
| Edit Brand | — | **9.5** | NEW | "Eight content themes the AI generated — tax planning, IRS resolution, year-round bookkeeping, financial consulting for entrepreneurs, payroll, local success stories, tax law updates, financial audits. Plus three competitors identified: KPMG local branch, H&R Block, Local CPA Firms NYC. All removable with X buttons, all editable with Add fields. And the Re-Analyze Brand button means if I change my description, the AI rebuilds everything. This isn't a static profile — it's a living brand analysis." |
| **Overall** | **9.5** | **9.75** | **+0.25** | |

**Maria's key quote:** "The Connections tab is the feature I've been waiting for without knowing it. Connecting my Instagram so Amplispark learns how I actually write — not how a generic restaurant writes, but how *Verde Kitchen* writes — that closes the last gap between AI-generated and Maria-generated content. And the fact that Notion is already connected with one click, not buried behind API keys or developer docs, means Jason's workflow is now my workflow too. Generate, review, export to Notion, done."

**Maria's remaining flag:** "No Buffer integration yet, but honestly? With Notion connected and Copy All still there, I have two solid export paths. Buffer can wait."

### Jason's Review — 9.875/10 (+0.125)

| Screen | R4 | R5 | Delta | Notes |
|--------|----|----|-------|-------|
| Landing | 8.5 | **9** | +0.5 | "The welcome-back banner is a smart returning user optimization. First-time visitors see the hero and 'How it works' — returning users get a one-click shortcut to their brand. That's two separate UX paths handled with one simple banner. Clean." |
| Onboard | 8.5 | **9** | +0.5 | "The onboarding form is minimal — describe your business, optionally upload brand assets, optionally paste a website. Three inputs. That's the right level of friction for a tool that promises content in under 2 minutes. The 'Build My Brand Profile →' CTA is the only button. No distractions." |
| Dashboard | 10 | 10 | — | |
| Generate | 10 | 10 | — | |
| Review | 10 | 10 | — | "Still a 10. The Suggested Improvements on the Day 1 post — 'the transition in Slide 3 from the specific rule to proactive year-round planning could be more explicitly tied to identifying opportunities like the De Minimis election' — that's not generic AI feedback. That's a content strategist who read the caption and understands the logical flow of the argument. This is what differentiates Amplispark from every 'AI caption generator' on the market." |
| Export | 9 | **10** | +1.0 | "Four export paths in one dropdown. This is the feature that turns Amplispark from a content generator into a content operations platform. ZIP with media for archival. .ics Calendar for scheduling visibility across Google/Outlook. Export to Notion for my editing workflow. Email calendar for team coordination. The per-post Copy/Export/Approve buttons on every card in the Posts Library mean I can also handle individual posts without going to the detail view. Batch and granular — both supported." |
| Video | 9 | 9 | — | |
| Voice Coach | 9.5 | 9.5 | — | |
| Connections | — | **10** | NEW | "This is the architecture I've been evaluating since Round 1. Social Voice Analysis: connect LinkedIn, and Amplispark learns my actual writing patterns — no emoji, long-form, authoritative. That's the Brand Analyst agent ingesting real data instead of relying solely on my description. The 'try demo' links prove the team already built per-platform demo data (the Round 2 fix). And on the right: Notion ✓ Connected to my actual workspace with a selected database and a 'change' option. My workflow is now: generate → review → one click Export to Notion → edit in Notion → schedule in Buffer when that API launches. The clipboard step is eliminated." |
| Edit Brand | — | **10** | NEW | "The Content Strategy section is what an enterprise content tool charges $500/month for. Eight AI-generated content themes specific to a CPA firm — not generic 'share tips and tricks' but 'Navigating IRS resolution and tax relief' and 'Local NYC/Long Island business financial success stories.' Three competitors auto-identified: KPMG local branch, H&R Block business services, Local CPA Firms NYC. All editable. The Image Style Directive and Caption Style Directive give me control over the AI's creative direction without needing to understand prompt engineering. And the Re-Analyze Brand button means I can iterate — change my description, hit re-analyze, and the entire strategy rebuilds. This is brand intelligence, not a form." |
| **Overall** | **9.75** | **9.875** | **+0.125** | |

**Jason's key quote:** "Three things moved the needle in this walkthrough. First, the Connections tab proves the Notion integration is real — not a mockup, not a spec, it's connected to my actual workspace with my actual database selected. Second, the Export & Share dropdown gives me four export paths where Round 1 had one (ZIP). Third, the Edit Brand page with Content Strategy, image/caption directives, and Re-Analyze Brand turns the brand profile from a static form into an iterative intelligence layer. This is now a content operations platform that happens to use AI, not an AI tool that happens to generate content."

**Jason's remaining flag:** "Buffer integration is the last piece. When their new API launches, Amplispark should be first in line. The architecture is ready — Connections tab already has the Publish & Export section. Adding a Buffer card next to Notion is a one-sprint feature. Until then, the Notion → Buffer manual workflow is acceptable."

### New Features Assessed (Round 5)

| Feature | Maria | Jason | Verdict |
|---------|-------|-------|---------|
| ✓ Notion badge in brand header | "Glanceable connection status" | "Proves integration is live, not mocked" | Ship as-is |
| Export & Share dropdown (4 paths) | 10 — "covers every workflow" | 10 — "content operations platform" | Ship as-is |
| Connections tab (Social Voice Analysis + Notion) | 10 — "the feature I was waiting for" | 10 — "architecture I've been evaluating since R1" | Ship as-is |
| Edit Brand (Content Strategy + Re-Analyze) | 9.5 — "living brand analysis" | 10 — "brand intelligence, not a form" | Ship as-is |
| Video Repurposing tab | 9.5 — "repurpose my existing video content" | 9 — "correct placement as separate tab" | Ship as-is |
| Per-post Copy/Export/Approve buttons | Implicit in 10 export score | "Batch and granular — both supported" | Ship as-is |
| Onboarding page (live) | 9 — "respects how small businesses work" | 9 — "right level of friction" | Ship as-is |
| Dedicated Export page | Implicit | "Approved-only filter is correct" | Ship as-is |

### Key Round 5 Observations

| # | Observation | Maria | Jason | Impact |
|---|------------|-------|-------|--------|
| 8 | Connections tab is the breakthrough screen | 10 — "feature I was waiting for" | 10 — "architecture I've been evaluating since R1" | Both personas' highest-rated new screen |
| 9 | Export & Share dropdown completes the content ops story | 10 — "covers every workflow" | 10 — "content operations platform" | Both upgraded Export from 9-9.5 to 10 |
| 10 | Edit Brand with Content Strategy is brand intelligence | 9.5 — "living brand analysis" | 10 — "brand intelligence, not a form" | Differentiates from static profile tools |
| 11 | Buffer is the only remaining wish | Accepted — "Buffer can wait" | Accepted — "one-sprint feature when API launches" | Not a blocker |

---

## Specialist Review — Priya (Cold Assessment of Round 5 Demo)

**Context:** Priya reviewed the same 10-screen live demo that Maria and Jason evaluated in Round 5. She has no prior context from Rounds 1-4. This is a cold assessment from a working professional who evaluates tools like this every quarter.

### Post-Review Corrections

Three of Priya's original criticisms were based on incorrect assumptions. These corrections were identified by the developer after the initial review.

**Correction 1: Multi-Brand Architecture Already Exists**

Priya's original claim: "One brand, one dashboard, one calendar. That's a solopreneur workflow." Reality: The landing page shows YOUR BRANDS (plural) with a green "Ready" badge and an onboarding flow to add new brands. Firebase Anonymous Auth ties brands to a persistent UID, meaning one account can have multiple brands. Priya assumed single-brand from the hero tagline ("One brand. Infinite content.") — that's a **marketing messaging issue, not an architecture limitation.** Score impact: Landing revised from 7 → **8**.

**Correction 2: Social Connections Are Demo Data By Design**

Priya's original claim: "Social connections are vaporware." Reality: This is a hackathon demo — the OAuth flows for LinkedIn, Instagram, and X aren't wired up to real platform APIs yet. The "try demo" links exist to prove per-platform voice differentiation (validated by Jason in Round 2). **Notion OAuth is live and real**, which is the more important integration. Score impact: No change — Priya's production standard is fair even if the hackathon context explains it.

**Correction 3: Buffer Scheduling Metadata Is Architecturally Ready**

Priya's original claim: "Content without timing is just drafts." Reality: Amplispark already has everything for Buffer integration except `suggested_publish_time`. The Strategy Agent adding platform-optimal publish times is a small feature addition, not an architecture change. Score impact: No change — the gap is real, but small.

### Priya's Updated Screen-by-Screen Assessment — 7.875/10 (was 7.75)

| Screen | Original | Updated | Delta | Correction Applied |
|--------|----------|---------|-------|--------------------|
| Landing | 7/10 | **8/10** | +1.0 | Multi-brand exists; hero tagline is misleading |
| Onboard | 7.5/10 | 7.5/10 | — | |
| Dashboard/Calendar | 8.5/10 | 8.5/10 | — | |
| Edit Brand | 9/10 | 9/10 | — | |
| Posts Library | 7.5/10 | 7.5/10 | — | |
| Export & Share | 8.5/10 | 8.5/10 | — | |
| Post Detail | 8/10 | 8/10 | — | |
| AI Brand Review | 9/10 | 9/10 | — | |
| Connections | 7/10 | 7/10 | — | Demo data acknowledged as hackathon-appropriate |
| Video | 6.5/10 | 6.5/10 | — | |
| Export Page | 7/10 | 7/10 | — | Buffer metadata gap is small, not architectural |
| **Overall** | **7.75/10** | **7.875/10** | **+0.125** | |

### What Priya Loves (The "Ship It" Features)

**1. AI Brand Review — "The actual differentiator"**

"I've used Jasper, Copy.ai, Lately, and ChatGPT for content generation. None of them review their own work. They all produce output and leave the quality assessment entirely to me. Amplispark's Review Agent with engagement prediction scores and specific improvement suggestions is a fundamentally different architecture. It's not just generating content — it's quality-checking content against my brand and telling me *why* a post scores 8 instead of 10. That feedback loop is what makes AI useful at scale. Without it, AI content generation is just a more expensive way to produce first drafts I'm going to rewrite anyway."

**2. Edit Brand with Content Strategy — "Finally, brand intelligence"**

"The Content Strategy section with AI-generated themes, competitor identification, and style directives is the closest thing I've seen to an AI that understands content strategy rather than just content creation. The Re-Analyze Brand button makes it living strategy. Every other tool I've used treats the brand profile as a static form you fill out once and forget. Amplispark treats it as an intelligence layer that evolves."

**3. Notion Export — "The right integration choice"**

"Every content professional I know uses Notion for editorial planning. Not Airtable, not Monday, not Asana — Notion. Shipping a native Notion OAuth integration that pushes a structured database is a better strategic decision than trying to build direct-publish to Instagram or LinkedIn, which are API nightmares with constantly changing policies. Let Notion be the staging ground, let me edit there, and I'll publish through Sprout or Buffer. Amplispark made the right integration choice."

**4. Pillar-Based Calendar — "Thinks like a strategist"**

"Color-coded content pillars on the calendar — education, promotion, inspiration, behind the scenes — map to how content strategists actually plan. This isn't 'Monday: motivational quote, Tuesday: product photo.' It's a strategic distribution model. That tells me the team behind Amplispark understands content marketing, not just content creation."

### What Priya Would Kill (The Brutal Assessment — Updated)

**~~1. Single-brand architecture~~ → RESOLVED.** Multi-brand is already built. The hero tagline ("One brand. Infinite content.") is a marketing copy issue, not a product limitation.

**2. Seven-day horizon is a toy limitation — "I plan in months, not weeks" (VALID).** "No professional content operation runs on a 7-day cycle. My editorial calendar is 30 days minimum, with tentpole content planned 90 days out. This is the single biggest limitation for professional adoption."

**3. No A/B caption variants — "I never publish the first draft" (VALID).** "The Post Detail screen shows one caption with a Regenerate button. That's serial. I need parallel — show me three hooks for the same post and let me pick."

**4. No campaign layer — "Content themes are not campaigns" (VALID).** "The Edit Brand page has eight content themes — those are always-on pillars. But where's the campaign? Content themes are the foundation; campaigns are the structure."

**5. No analytics feedback loop — "Generate and forget?" (VALID).** "The AI Brand Review predicts engagement. Where's the actuals? Post A predicted Hook 9, actual Hook was a 6 — the AI should learn from that."

**6. Social connections are demo data (ACKNOWLEDGED — Hackathon Context).** Architecture is built; API wiring is the remaining work.

**7. No scheduling metadata (PARTIALLY ADDRESSED).** Strategy Agent needs `suggested_publish_time` field; Buffer readiness otherwise complete.

### Priya's Professional Criteria Scores

| Criterion | Original | Updated | Notes |
|-----------|----------|---------|-------|
| Content Quality | 8.5/10 | 8.5/10 | Brand-aligned output with specific, actionable review feedback. Above Jasper/Copy.ai. |
| Brand Consistency | 8/10 | **8.5/10** | Multi-brand exists (correction). Content Strategy + directives + Re-Analyze is strong. |
| Workflow Efficiency | 7/10 | 7/10 | Good for batch generation. Still needs 30-day horizon and A/B variants for pro scale. |
| Integration Ecosystem | 7.5/10 | 7.5/10 | Notion is the right first integration. Needs CSV, Sprout/Hootsuite import, Google Sheets. |
| Scalability | 5/10 | **6/10** | Multi-brand exists (correction). Still needs 30-day generation, campaign layer, filters. |
| Platform Intelligence | 7.5/10 | 7.5/10 | Platform previews, character counts, pillar-based strategy are smart. Missing TikTok, timing. |
| AI Differentiation | 9/10 | 9/10 | Review Agent with engagement predictions is best-in-class. Voice Coach is genuine innovation. |
| Production Readiness | 6.5/10 | 6.5/10 | Social connections aren't live. Video extraction logic is opaque. No A/B variants. |

### Priya's Verdict

**"Amplispark is the most architecturally intelligent AI content tool I've evaluated. The Review Agent alone makes it worth watching. Multi-brand support being already built changes the story — this isn't locked into solopreneur mode. The remaining gaps are professional workflow features, not fundamental architecture problems."**

**Updated upgrade roadmap (with corrections):**

| # | Item | Status | Impact |
|---|------|--------|--------|
| ~~1~~ | ~~Multi-brand dashboard~~ | ✅ ALREADY BUILT | Hero copy needs update |
| 2 | 30-day generation | ❌ Not built | Biggest pro adoption blocker |
| 3 | A/B caption variants | ❌ Not built | Standard professional workflow |
| 4 | Campaign layer | ❌ Not built | Unlocks enterprise use cases |
| 5 | Analytics feedback loop | ❌ Not built | Closes prediction → actuals gap |
| 6 | Live social connections | 🟡 Architecture built, APIs not wired | Post-hackathon roadmap |
| 7 | Scheduling metadata | 🟡 Small gap — Strategy Agent add | Ready when Buffer API launches |

**"Get items 2-3 and I'm a paying customer at $99/month. Get all seven and I'm replacing Sprout Social."**

*Specialist review conducted March 2, 2026. Corrections applied March 12, 2026.*

---

## Score Progression Summary (All Rounds)

```
          R1      R2      R3      R4      R5
Maria    8.5 ──→ 9.0 ──→ 9.25 ──→ 9.5  ──→ 9.75    (+1.25 total)
Jason    8.0 ──→ 9.5 ──→ 9.625──→ 9.75 ──→ 9.875   (+1.875 total)
──────────────────────────────────────────────────────────────────
2-Persona AVG   8.25    9.25    9.4375   9.625    9.8125   (+1.5625 total)

Priya (Specialist — cold R5 review only):            7.875

3-Persona AVG (with Priya):                          9.125
```

**The 3-persona average of 9.125 is the most honest assessment.** Exceptional solopreneur/SMB tool (9.8125) with a clear path to professional adoption (7.875 from Priya). For the Creative Storyteller hackathon category targeting small businesses, the 9.8125 is the relevant score.

---

## Per-Screen Score Comparison (All Rounds + Specialist)

| Screen | Maria R1 | Maria R2 | Maria R3 | Maria R4 | Maria R5 | Jason R1 | Jason R2 | Jason R3 | Jason R4 | Jason R5 | Priya |
|--------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|-------|
| Landing | 9 | 9 | 9 | 9.5 | 10 | 7.5 | 7.5 | 7.5 | 8.5 | 9 | 8 |
| Onboard | 8.5 | 8.5 | 8.5 | 8.5 | 9 | 8.5 | 8.5 | 8.5 | 8.5 | 9 | 7.5 |
| Dashboard | 9 | 9.5 | 9.5 | 10 | 10 | 8 | 9 | 9 | 10 | 10 | 8.5 |
| Generate | 8.5 | 8.5 | 9.5 | 9.5 | 9.5 | 9 | 9.5 | 10 | 10 | 10 | 8 |
| Review | 9 | 9 | 9.5 | 10 | 10 | 8 | 8.5 | 10 | 10 | 10 | 9 |
| Export | 8.5 | 9.5 | 9.5 | 9.5 | 10 | 7.5 | 9 | 9 | 9 | 10 | 8.5 |
| Video | 7 | 7 | 8.5 | 9 | 9.5 | 6 | 9 | 9 | 9 | 9 | 6.5 |
| Voice Coach | 7.5 | 7.5 | 7.5 | 9 | 9 | 8 | 8 | 8 | 9.5 | 9.5 | — |
| Connections | — | — | — | — | 10 | — | — | — | — | 10 | 7 |
| Edit Brand | — | — | — | — | 9.5 | — | — | — | — | 10 | 9 |
| Posts Library | — | — | — | — | — | — | — | — | — | — | 7.5 |
| Export Page | — | — | — | — | — | — | — | — | — | — | 7 |

---

## Flag Resolution — Final (All Rounds + Specialist)

| # | Flag | R1 | R2 | R3 | R4 | R5 | Status |
|---|------|----|----|-----|-----|-----|--------|
| 1 | Demo voice data Instagram-only | Open | ✅ | ✅ | ✅ | ✅ | Per-platform demos confirmed on Connections tab |
| 2 | Export format ZIP-only | Open | ✅ | ✅ | ✅ | ✅ | 4 export paths: ZIP, .ics, Notion, Email |
| 3 | Video noise for text-first | Open | ✅ | ✅ | ✅ | ✅ | Video Repurposing in separate tab now |
| 4 | Output quality unknowable | Open | Open | ✅ | ✅ | ✅ | Confirmed across multiple posts and platforms |
| 5 | Hashtag pollution | — | — | 🟡 P1 | 🟢 Likely fixed | ✅ | Clean hashtags confirmed: 5/5 on Instagram post, all professional |
| 6 | Voice Coach undervalued from code | — | — | — | ✅ | ✅ | Remains top differentiator |
| 7 | No Buffer integration | — | — | — | — | 🟡 **Accepted** | Buffer API closed Oct 2019, new API in early access waitlist. Notion + Copy All cover gap. Architecture ready. |
| 8 | Notion integration needed | — | — | — | — | ✅ **Resolved** | OAuth live, connected to real workspace, Export to Notion in dropdown |
| 9 | Single-brand assumption (Priya) | — | — | — | — | ✅ **Corrected** | Multi-brand architecture exists; hero tagline is misleading |
| 10 | Social connections vaporware (Priya) | — | — | — | — | 🟡 **Acknowledged** | Hackathon-appropriate demo data; Notion OAuth is live; architecture built |
| 11 | No scheduling metadata (Priya) | — | — | — | — | 🟡 **Small gap** | Strategy Agent needs `suggested_publish_time` field; Buffer readiness otherwise complete |

---

## What Each Persona Would Tell a Friend (Updated — Round 5)

**Maria:** "Remember that AI content tool I told you about? It just got better. I connected my Notion workspace with one click — no API keys, no developer stuff. Now I generate a week of posts, click 'Export to Notion,' and my entire content calendar appears as a database I can edit. The Voice Coach is still the killer feature — I asked it about promoting our farm delivery special and it gave me a full strategy in my brand voice while I was looking at my calendar. But the new thing is the Connections tab. When I connect my real Instagram account, it'll learn how *I* actually write, not just what I described. For Sunday night batch sessions, this is now a 20-minute job instead of 2 hours. And if my business partner needs the schedule, I can email them a calendar invite directly from the app."

**Jason:** "Amplispark isn't a content generator anymore — it's a content operations platform. Here's what changed: Notion OAuth integration is live. I connect my workspace, click 'Export to Notion,' and all 7 days of content land in a database with columns for platform, caption, hashtags, image URL, brand score, and approval status. I edit in Notion, schedule in Buffer when their API launches. The Edit Brand page shows me the AI's content strategy — eight specific themes like 'Navigating IRS resolution and tax relief,' three competitors it identified, image style directives, caption style directives — and I can re-analyze the whole thing if I change my positioning. The Export & Share dropdown gives me four paths: ZIP, calendar invite, Notion sync, or email. And the Connections tab is ready for LinkedIn voice analysis — when I connect, the AI learns my actual writing patterns. This is the tool I'd pay $50/month for. The only missing piece is Buffer direct-publish, and the architecture is already there waiting for their API."

**Priya:** "If you're a solopreneur or SMB owner, stop what you're doing and try Amplispark. The AI Brand Review alone differentiates it from every Jasper and Copy.ai clone I've tested — it doesn't just generate content, it quality-checks against your brand and tells you why a post scores 8 instead of 10. The Notion integration is the right call — export your calendar, edit in Notion, publish through whatever scheduler you use. For professionals running multi-brand operations at scale, it's not there yet — I need 30-day calendars, A/B caption variants, and a campaign layer before I'm replacing Sprout Social. But the architecture is smart, the Review Agent is best-in-class, and the Content Strategy section on the Edit Brand page is the closest thing I've seen to AI that thinks like a strategist. Get items 2-3 on their roadmap and I'm a paying customer at $99/month."
