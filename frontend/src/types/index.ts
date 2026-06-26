export interface SocialVoiceAnalysis {
  voice_characteristics: string[]
  common_phrases: string[]
  emoji_usage: string
  average_post_length: string
  successful_patterns: string[]
  tone_adjectives: string[]
}

export interface BrandProfile {
  brand_id: string
  business_name: string
  business_type: string
  description?: string
  website_url?: string
  industry: string
  tone: string
  colors: string[]
  target_audience: string
  visual_style: string
  image_style_directive: string
  caption_style_directive: string
  content_themes: string[]
  competitors: string[]
  logo_url?: string | null
  uploaded_assets?: { filename: string; url: string; type: string }[]
  analysis_status: string
  ui_preferences?: { show_competitors?: boolean }
  connected_platforms?: string[]
  selected_platforms?: string[]
  platform_mode?: 'ai' | 'manual'
  social_voice_analyses?: Record<string, SocialVoiceAnalysis>
  social_voice_analysis?: SocialVoiceAnalysis
  social_voice_platform?: string
  default_image_style?: string
  integrations?: {
    notion?: {
      access_token?: string
      workspace_name?: string
      database_id?: string
      database_name?: string
      connected_at?: string
    }
    buffer?: {
      access_token?: string
      connected_at?: string
      channels?: { id: string; service: string; name: string }[]
    }
  }
}

export interface Post {
  post_id: string
  plan_id: string | null
  day_index: number | null
  brief_index?: number
  status: 'draft' | 'generating' | 'complete' | 'failed' | 'approved'
  caption?: string
  hashtags?: string[]
  image_url?: string
  video?: { url: string }
  platform?: string
  pillar?: string
  derivative_type?: string
  created_at?: string
  is_quick_post?: boolean
}

export interface Plan {
  plan_id: string
  days: DayBrief[]
  num_days?: number
  status?: string
  created_at?: string
  trend_summary?: TrendSummary
}

export interface TrendSummary {
  researched_at: string
  platform_trends: Record<string, Record<string, unknown>>
  visual_trends: Record<string, unknown> | null
  video_trends: Record<string, unknown> | null
}

export interface DayBrief {
  day_index: number
  platform: string
  pillar: string
  pillar_id?: string
  content_theme: string
  caption_hook: string
  key_message: string
  image_prompt: string
  hashtags: string[]
  derivative_type?: string
  event_anchor?: string | null
  custom_photo_url?: string | null
  suggested_time?: string
}

export type NotificationType = 'processing' | 'complete' | 'failed'

export interface AppNotification {
  notification_id: string
  uid: string
  type: NotificationType
  title: string
  body: string
  brand_id: string
  post_id: string
  plan_id: string
  day_index: number | null
  read: boolean
  created_at?: string
}
