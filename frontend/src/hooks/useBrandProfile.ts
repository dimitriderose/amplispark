import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

interface SocialVoiceAnalysis {
  voice_characteristics: string[]
  common_phrases: string[]
  emoji_usage: string
  average_post_length: string
  successful_patterns: string[]
  tone_adjectives: string[]
}

interface BrandProfile {
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
  social_voice_analyses?: Record<string, SocialVoiceAnalysis>
  social_voice_analysis?: SocialVoiceAnalysis
  social_voice_platform?: string
}

export type { BrandProfile, SocialVoiceAnalysis }

export function useBrandProfile(brandId: string | undefined) {
  const [brand, setBrand] = useState<BrandProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchBrand = useCallback(async () => {
    if (!brandId) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.getBrand(brandId) as { brand_profile: BrandProfile }
      setBrand(res.brand_profile)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load brand')
    } finally {
      setLoading(false)
    }
  }, [brandId])

  useEffect(() => {
    fetchBrand()
  }, [fetchBrand])

  // Poll while analyzing
  useEffect(() => {
    if (!brand || brand.analysis_status !== 'analyzing') return
    const interval = setInterval(fetchBrand, 3000)
    return () => clearInterval(interval)
  }, [brand, fetchBrand])

  const updateBrand = useCallback(async (data: Partial<BrandProfile>) => {
    if (!brandId) return
    await api.updateBrand(brandId, data)
    await fetchBrand()
  }, [brandId, fetchBrand])

  return { brand, loading, error, refetch: fetchBrand, updateBrand }
}
