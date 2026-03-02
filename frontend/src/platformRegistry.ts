/**
 * Platform Registry — frontend source of truth for platform UI config.
 *
 * All components import from here instead of maintaining local platform dicts.
 * Adding a new platform = add ONE entry here + one in backend/platforms.py.
 */

import type { IconType } from 'react-icons'
import {
  SiInstagram,
  SiLinkedin,
  SiX,
  SiTiktok,
  SiFacebook,
  SiThreads,
  SiPinterest,
  SiYoutube,
  SiMastodon,
  SiBluesky,
} from 'react-icons/si'

export interface PlatformSpec {
  key: string
  displayName: string
  icon: IconType
  color: string
  captionMax: number
  hashtagMax: number
  foldAt: number | null
  isVideoFirst: boolean
  isPortraitVideo: boolean
}

export const PLATFORMS: Record<string, PlatformSpec> = {
  instagram: {
    key: 'instagram',
    displayName: 'Instagram',
    icon: SiInstagram,
    color: '#E1306C',
    captionMax: 2200,
    hashtagMax: 5,
    foldAt: 125,
    isVideoFirst: false,
    isPortraitVideo: true,
  },
  linkedin: {
    key: 'linkedin',
    displayName: 'LinkedIn',
    icon: SiLinkedin,
    color: '#0A66C2',
    captionMax: 3000,
    hashtagMax: 5,
    foldAt: 140,
    isVideoFirst: false,
    isPortraitVideo: false,
  },
  x: {
    key: 'x',
    displayName: 'X',
    icon: SiX,
    color: '#000000',
    captionMax: 280,
    hashtagMax: 1,
    foldAt: null,
    isVideoFirst: false,
    isPortraitVideo: false,
  },
  tiktok: {
    key: 'tiktok',
    displayName: 'TikTok',
    icon: SiTiktok,
    color: '#000000',
    captionMax: 2200,
    hashtagMax: 6,
    foldAt: null,
    isVideoFirst: true,
    isPortraitVideo: true,
  },
  facebook: {
    key: 'facebook',
    displayName: 'Facebook',
    icon: SiFacebook,
    color: '#1877F2',
    captionMax: 63206,
    hashtagMax: 3,
    foldAt: null,
    isVideoFirst: false,
    isPortraitVideo: false,
  },
  threads: {
    key: 'threads',
    displayName: 'Threads',
    icon: SiThreads,
    color: '#000000',
    captionMax: 500,
    hashtagMax: 3,
    foldAt: null,
    isVideoFirst: false,
    isPortraitVideo: true,
  },
  pinterest: {
    key: 'pinterest',
    displayName: 'Pinterest',
    icon: SiPinterest,
    color: '#E60023',
    captionMax: 500,
    hashtagMax: 0,
    foldAt: null,
    isVideoFirst: false,
    isPortraitVideo: true,
  },
  youtube_shorts: {
    key: 'youtube_shorts',
    displayName: 'YouTube Shorts',
    icon: SiYoutube,
    color: '#FF0000',
    captionMax: 5000,
    hashtagMax: 5,
    foldAt: null,
    isVideoFirst: true,
    isPortraitVideo: true,
  },
  mastodon: {
    key: 'mastodon',
    displayName: 'Mastodon',
    icon: SiMastodon,
    color: '#6364FF',
    captionMax: 500,
    hashtagMax: 5,
    foldAt: null,
    isVideoFirst: false,
    isPortraitVideo: false,
  },
  bluesky: {
    key: 'bluesky',
    displayName: 'Bluesky',
    icon: SiBluesky,
    color: '#0085FF',
    captionMax: 300,
    hashtagMax: 3,
    foldAt: null,
    isVideoFirst: false,
    isPortraitVideo: false,
  },
}

const _ALIASES: Record<string, string> = { twitter: 'x' }

export function getPlatform(key: string): PlatformSpec {
  const normalized = _ALIASES[key.toLowerCase()] ?? key.toLowerCase()
  return PLATFORMS[normalized] ?? PLATFORMS.instagram
}

export function allPlatformKeys(): string[] {
  return Object.keys(PLATFORMS)
}

/* ── Video support by platform + derivative type ── */

const NO_VIDEO: Record<string, string[]> = {
  instagram: ['original', 'carousel', 'story'],
  tiktok: ['carousel'],
  pinterest: ['original', 'pin'],
}

export type VideoSupport = 'none' | 'primary' | 'optional'

export function getVideoSupport(
  platform: string,
  derivativeType?: string,
): VideoSupport {
  if (derivativeType === 'video_first') return 'primary'
  const key = (platform || '').toLowerCase()
  const normalized = _ALIASES[key] ?? key
  if (NO_VIDEO[normalized]?.includes(derivativeType || 'original')) return 'none'
  return 'optional'
}
