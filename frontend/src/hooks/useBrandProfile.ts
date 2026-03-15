import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type { BrandProfile } from '../types'

export type { BrandProfile, SocialVoiceAnalysis } from '../types'

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
