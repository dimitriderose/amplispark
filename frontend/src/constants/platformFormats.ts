import {
  MdOutlineImage,
  MdOutlineViewCarousel,
  MdOutlinePlayCircle,
  MdOutlineTimer,
  MdOutlineFormatListNumbered,
  MdOutlineArticle,
  MdOutlinePushPin,
} from 'react-icons/md'
import type { IconType } from 'react-icons'

export const PLATFORM_FORMATS: Record<string, string[]> = {
  instagram:      ['original', 'carousel', 'video_first', 'story'],
  linkedin:       ['original', 'carousel', 'video_first', 'blog_snippet'],
  x:              ['original', 'thread_hook', 'video_first'],
  tiktok:         ['video_first', 'carousel'],
  facebook:       ['original', 'carousel', 'video_first', 'story'],
  threads:        ['original', 'thread_hook'],
  pinterest:      ['pin', 'video_first'],
  youtube_shorts: ['video_first'],
  mastodon:       ['original'],
  bluesky:        ['original', 'thread_hook'],
}

export const FORMAT_LABELS: Record<string, { label: string; icon: IconType }> = {
  original:     { label: 'Photo',     icon: MdOutlineImage },
  carousel:     { label: 'Carousel',  icon: MdOutlineViewCarousel },
  video_first:  { label: 'Video',     icon: MdOutlinePlayCircle },
  story:        { label: 'Story',     icon: MdOutlineTimer },
  thread_hook:  { label: 'Thread',    icon: MdOutlineFormatListNumbered },
  blog_snippet: { label: 'Blog Clip', icon: MdOutlineArticle },
  pin:          { label: 'Pin',       icon: MdOutlinePushPin },
}
