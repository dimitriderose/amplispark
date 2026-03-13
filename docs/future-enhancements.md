# Future Enhancements — Platform & Content Pipeline

Items identified during the Agent Quality Overhaul (Feb 2026) and Multi-Platform Enhancement (March 2026). Organized by priority.

---

## High Priority

### Audio / Sound Layer for Video
- **Problem**: Veo generates silent video. TikTok, IG Reels, YT Shorts, FB Reels all penalize silent video in their algorithms.
- **Options**:
  - FFmpeg post-processing with royalty-free music library
  - Veo audio capabilities (if available in future API versions)
  - Integrate a music API (e.g., Epidemic Sound, Artlist)
  - Generate "caption-style" text overlays on video frames
- **Interim**: `audio_note` field tells user to add audio manually before publishing

---

## Medium Priority

### Mastodon Alt Text Pipeline
- **Problem**: Prompt tells AI to write alt text but our image pipeline has no `alt_text` output field
- **Fix**: Add `alt_text` field to Post model. Either parse from Gemini generation output or make a separate Gemini Vision call to describe the generated image
- **Why it matters**: Mastodon culture expects alt text on every image — without it, brands get called out

### Instagram Interactive Stories
- **Problem**: Our "story" derivative generates static image + ≤50 words — not a real Story
- **What real Stories use**: Polls, quizzes, countdown stickers, question boxes, sliders
- **Fix**: Story builder UI or structured JSON output that maps to Story sticker types
- **Note**: Likely out of scope for AI generation — may be better as a manual creation tool

### Instagram Collaborative Posts
- **Problem**: Collab posts (two accounts co-authoring) are one of the highest-reach formats on IG
- **Constraint**: Requires both accounts to approve — can't be auto-generated
- **Fix**: Strategy agent could suggest "collab with [partner type]" in day brief, user handles the invite

### Facebook Group vs Page Content
- **Problem**: Facebook in 2026 is Group-centric — Page posts vs Group posts need different strategies
- **Fix**: Add `facebook_context: "page" | "group"` to brand profile, adjust prompt accordingly
- **Difference**: Group posts are more conversational, Page posts are more polished

### TikTok Text-on-Screen Overlays
- **Problem**: Most TikToks have on-screen text overlays — different from the caption
- **Fix**: Generate structured output with `overlay_text` field. Veo or FFmpeg burns text onto video frames
- **Impact**: Text overlays are critical for TikTok accessibility and engagement

---

## Low Priority

### Instagram Broadcast Channels
- One-to-many messaging format, different from feed posts
- Fix: New content type in strategy agent + content creator

### TikTok Shop Integration
- TikTok Shop is massive for product-based brands
- Fix: Add product catalog awareness to strategy agent for e-commerce brands

### Pinterest Rich Pins
- Recipe Pins, Article Pins, Product Pins auto-pull metadata
- Fix: Add `pin_type` field to derivative instructions, generate structured metadata

### Pinterest Trends API
- Pinterest has a Trends tool showing what's being searched
- Fix: Integrate Pinterest Trends API or scrape trending data via Google Search grounding

### X Communities
- Niche discovery mechanism on X — communities have their own feeds
- Fix: Strategy agent could recommend relevant X Communities for the brand's industry

### Bluesky Starter Packs
- Curated lists of accounts to follow — #1 growth mechanism on Bluesky
- Fix: Growth strategy recommendation (not a content generation concern)

### Bluesky Custom Domain Handles
- Bluesky lets brands use their domain as handle (e.g., @derose.com)
- Fix: Onboarding recommendation (not a content generation concern)

### LinkedIn Newsletters & Articles
- Long-form LinkedIn formats that drive subscriber growth
- Fix: New content type with article-length generation (1000-2000 words)

### Mastodon Instance-Specific Norms
- Different Mastodon instances have different rules and cultures
- Fix: Would need instance metadata in brand profile — likely overkill

### "Should This Brand Be on Mastodon?"
- Mastodon culture is explicitly anti-corporate
- Fix: Add cultural fit check to `_research_best_platforms()` — flag platforms where brand presence may backfire

---

## Quick Fixes (Next Sprint)

### LinkedIn `_FORMAT_GUIDE` Stat Update
- Strategy agent `_FORMAT_GUIDE` still references "596% more engagement" for document posts
- This stat is from 2023 — LinkedIn has shifted toward personal narrative content
- Fix: Update stat or remove specific number, shift guidance toward narrative-first

### YouTube Shorts 3-Minute Duration
- YouTube Shorts now supports up to 3 minutes, not just 60 seconds
- Fix: Add note to YouTube Shorts prompt about extended duration option

---

## Completed (v1.5)

### Cross-Platform Repurposing
- **Shipped**: Multi-platform calendar now generates coordinated briefs across platforms with shared pillar IDs. Day briefs on the same day share a thematic angle but differ in format, tone, and hook per platform.
- Previously listed under Medium Priority as "Cross-Platform Repurposing (Threads <-> Instagram)" — the implementation is broader than the original scope.

### Platform-Specific Posting Frequency
- **Shipped**: AI-researched posting frequency via Gemini + Google Search grounding determines the optimal posts/week per platform for each business type. Not hardcoded — dynamically researched and cached per brand.

### Best Posting Times
- **Shipped**: Each brief includes a `suggested_time` field derived from AI-researched best posting times per platform. Calendar cards display and sort by suggested time.
