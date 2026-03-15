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
  // Social voice analysis fields (populated after connecting a social account)
  connected_platforms?: string[]
  selected_platforms?: string[]
  platform_mode?: 'ai' | 'manual'
  social_voice_analyses?: Record<string, SocialVoiceAnalysis>
  social_voice_analysis?: SocialVoiceAnalysis
  social_voice_platform?: string
  default_image_style?: string
  // Integrations (Notion, Buffer, etc.)
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
  plan_id: string
  day_index: number
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
}

export interface Plan {
  plan_id: string
  days: any[]
  num_days?: number
  status?: string
  created_at?: string
  trend_summary?: TrendSummary
}

export interface TrendSummary {
  researched_at: string
  platform_trends: Record<string, any>
  visual_trends: Record<string, any> | null
  video_trends: Record<string, any> | null
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
