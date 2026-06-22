import { describe, it, expect } from 'vitest'
import {
  PLATFORMS,
  getPlatform,
  allPlatformKeys,
  getMediaAspectRatio,
  getVideoSupport,
} from '../platformRegistry'

describe('getPlatform', () => {
  it('returns instagram spec for instagram key', () => {
    const spec = getPlatform('instagram')
    expect(spec.key).toBe('instagram')
    expect(spec.displayName).toBe('Instagram')
  })

  it('normalizes twitter alias to x', () => {
    const spec = getPlatform('twitter')
    expect(spec.key).toBe('x')
  })

  it('is case-insensitive', () => {
    const spec = getPlatform('LINKEDIN')
    expect(spec.key).toBe('linkedin')
  })

  it('falls back to instagram for unknown platform', () => {
    const spec = getPlatform('unknown_platform')
    expect(spec.key).toBe('instagram')
  })

  it('returns tiktok spec', () => {
    const spec = getPlatform('tiktok')
    expect(spec.displayName).toBe('TikTok')
    expect(spec.isVideoFirst).toBe(true)
  })

  it('returns facebook spec', () => {
    const spec = getPlatform('facebook')
    expect(spec.displayName).toBe('Facebook')
  })

  it('returns threads spec', () => {
    const spec = getPlatform('threads')
    expect(spec.displayName).toBe('Threads')
  })

  it('returns pinterest spec', () => {
    const spec = getPlatform('pinterest')
    expect(spec.displayName).toBe('Pinterest')
  })

  it('returns youtube_shorts spec', () => {
    const spec = getPlatform('youtube_shorts')
    expect(spec.displayName).toBe('YouTube Shorts')
  })

  it('returns mastodon spec', () => {
    const spec = getPlatform('mastodon')
    expect(spec.displayName).toBe('Mastodon')
  })

  it('returns bluesky spec', () => {
    const spec = getPlatform('bluesky')
    expect(spec.displayName).toBe('Bluesky')
  })
})

describe('allPlatformKeys', () => {
  it('returns all platform keys', () => {
    const keys = allPlatformKeys()
    expect(keys).toContain('instagram')
    expect(keys).toContain('linkedin')
    expect(keys).toContain('x')
    expect(keys).toContain('tiktok')
    expect(keys).toContain('facebook')
    expect(keys.length).toBe(Object.keys(PLATFORMS).length)
  })
})

describe('getMediaAspectRatio', () => {
  it('returns portrait 9/16 for video_first on portrait platform', () => {
    const ratio = getMediaAspectRatio('instagram', 'video_first')
    expect(ratio).toBe('9 / 16')
  })

  it('returns landscape 16/9 for video_first on non-portrait platform', () => {
    const ratio = getMediaAspectRatio('linkedin', 'video_first')
    expect(ratio).toBe('16 / 9')
  })

  it('returns carousel aspect for instagram carousel', () => {
    const ratio = getMediaAspectRatio('instagram', 'carousel')
    expect(ratio).toBe('4 / 5')
  })

  it('returns carousel aspect for linkedin carousel', () => {
    const ratio = getMediaAspectRatio('linkedin', 'carousel')
    expect(ratio).toBe('1 / 1')
  })

  it('returns carousel aspect for tiktok carousel', () => {
    const ratio = getMediaAspectRatio('tiktok', 'carousel')
    expect(ratio).toBe('9 / 16')
  })

  it('returns carousel spec imageAspect for unknown platform carousel', () => {
    const ratio = getMediaAspectRatio('mastodon', 'carousel')
    expect(ratio).toBe('16 / 9') // mastodon imageAspect fallback
  })

  it('returns story aspect 9/16 for story derivative', () => {
    const ratio = getMediaAspectRatio('instagram', 'story')
    expect(ratio).toBe('9 / 16')
  })

  it('returns pin aspect 2/3 for pin derivative', () => {
    const ratio = getMediaAspectRatio('pinterest', 'pin')
    expect(ratio).toBe('2 / 3')
  })

  it('returns blog_snippet aspect 1.91/1', () => {
    const ratio = getMediaAspectRatio('instagram', 'blog_snippet')
    expect(ratio).toBe('1.91 / 1')
  })

  it('returns standard post aspect for instagram without derivativeType', () => {
    const ratio = getMediaAspectRatio('instagram')
    expect(ratio).toBe('4 / 5')
  })

  it('returns standard post aspect for x without derivativeType', () => {
    const ratio = getMediaAspectRatio('x')
    expect(ratio).toBe('16 / 9')
  })

  it('returns spec imageAspect for unknown platform without derivativeType', () => {
    const ratio = getMediaAspectRatio('tiktok')
    // tiktok not in _STANDARD_POST_ASPECTS, falls back to spec.imageAspect
    expect(ratio).toBe('9 / 16')
  })

  it('normalizes twitter alias in aspect ratio', () => {
    const ratio = getMediaAspectRatio('twitter')
    expect(ratio).toBe('16 / 9') // x standard post aspect
  })
})

describe('getVideoSupport', () => {
  it('returns primary for video_first derivativeType', () => {
    expect(getVideoSupport('instagram', 'video_first')).toBe('primary')
    expect(getVideoSupport('linkedin', 'video_first')).toBe('primary')
  })

  it('returns none for instagram original', () => {
    expect(getVideoSupport('instagram', 'original')).toBe('none')
  })

  it('returns none for instagram carousel', () => {
    expect(getVideoSupport('instagram', 'carousel')).toBe('none')
  })

  it('returns none for instagram story', () => {
    expect(getVideoSupport('instagram', 'story')).toBe('none')
  })

  it('returns none for tiktok carousel', () => {
    expect(getVideoSupport('tiktok', 'carousel')).toBe('none')
  })

  it('returns none for pinterest original', () => {
    expect(getVideoSupport('pinterest', 'original')).toBe('none')
  })

  it('returns none for pinterest pin', () => {
    expect(getVideoSupport('pinterest', 'pin')).toBe('none')
  })

  it('returns optional for linkedin standard post', () => {
    expect(getVideoSupport('linkedin', 'original')).toBe('optional')
  })

  it('returns optional for unknown platform', () => {
    expect(getVideoSupport('unknown')).toBe('optional')
  })

  it('handles empty platform string', () => {
    expect(getVideoSupport('')).toBe('optional')
  })
})
