import { useCallback } from 'react'
import { api } from '../api/client'
import type { BrandProfile } from '../types'
import { useFetch } from './useFetch'

export type { BrandProfile, SocialVoiceAnalysis } from '../types'

export function useBrandProfile(brandId: string | undefined) {
  const { data: brand, loading, error, refresh: refetch } = useFetch<BrandProfile>(
    brandId ? () => api.getBrand(brandId).then(res => res.brand_profile) : null,
    [brandId],
    {
      pollMs: 3000,
      pollWhen: (data) => data?.analysis_status === 'analyzing',
    }
  )

  const updateBrand = useCallback(async (data: Partial<BrandProfile>) => {
    if (!brandId) return
    await api.updateBrand(brandId, data)
    refetch()
  }, [brandId, refetch])

  return { brand, loading, error: error || null, refetch, updateBrand }
}
