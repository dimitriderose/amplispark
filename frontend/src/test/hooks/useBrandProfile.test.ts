import { renderHook, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('../../api/client', () => import('../mocks/client'))

import { useBrandProfile } from '../../hooks/useBrandProfile'
import { api } from '../../api/client'

const mockBrandProfile = {
  brand_id: 'brand-abc',
  business_name: 'Acme Corp',
  business_type: 'SaaS',
  industry: 'Technology',
  tone: 'Professional',
  colors: ['#5B5FF6'],
  target_audience: 'Developers',
  visual_style: 'Minimal',
  image_style_directive: 'Clean shots',
  caption_style_directive: 'Short and punchy',
  content_themes: ['Education'],
  competitors: [],
  analysis_status: 'complete',
}

describe('useBrandProfile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches brand on mount when brandId is provided', async () => {
    vi.mocked(api.getBrand).mockResolvedValue({ brand_profile: mockBrandProfile } as never)

    const { result } = renderHook(() => useBrandProfile('brand-abc'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(api.getBrand).toHaveBeenCalledWith('brand-abc')
    expect(result.current.brand).toEqual(mockBrandProfile)
    expect(result.current.error).toBeNull()
  })

  it('returns null brand when brandId is undefined', async () => {
    const { result } = renderHook(() => useBrandProfile(undefined))

    await new Promise(r => setTimeout(r, 20))

    expect(result.current.brand).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(api.getBrand).not.toHaveBeenCalled()
  })

  it('returns null brand when brandId is empty string', async () => {
    const { result } = renderHook(() => useBrandProfile(''))

    await new Promise(r => setTimeout(r, 20))

    expect(result.current.brand).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(api.getBrand).not.toHaveBeenCalled()
  })

  it('exposes error state when fetch fails', async () => {
    vi.mocked(api.getBrand).mockRejectedValue(new Error('Not Found'))

    const { result } = renderHook(() => useBrandProfile('missing-brand'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Not Found')
    expect(result.current.brand).toBeNull()
  })

  it('exposes loading=true while fetch is in flight', async () => {
    // Use a never-resolving promise
    vi.mocked(api.getBrand).mockReturnValue(new Promise(() => {}) as never)

    const { result } = renderHook(() => useBrandProfile('brand-abc'))

    await waitFor(() => {
      expect(result.current.loading).toBe(true)
    })
  })

  it('updateBrand calls api.updateBrand and triggers refetch', async () => {
    vi.mocked(api.getBrand).mockResolvedValue({ brand_profile: mockBrandProfile } as never)
    vi.mocked(api.updateBrand).mockResolvedValue({} as never)

    const { result } = renderHook(() => useBrandProfile('brand-abc'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.updateBrand({ industry: 'Updated Industry' })
    })

    expect(api.updateBrand).toHaveBeenCalledWith('brand-abc', { industry: 'Updated Industry' })
    // refetch triggers a second getBrand call
    expect(api.getBrand).toHaveBeenCalledTimes(2)
  })

  it('updateBrand does nothing when brandId is undefined', async () => {
    const { result } = renderHook(() => useBrandProfile(undefined))

    await act(async () => {
      await result.current.updateBrand({ industry: 'Should not update' })
    })

    expect(api.updateBrand).not.toHaveBeenCalled()
  })

  it('returns brand with analyzing status (pollWhen condition is exercised)', async () => {
    const analyzingBrand = { ...mockBrandProfile, analysis_status: 'analyzing' }
    vi.mocked(api.getBrand).mockResolvedValue({ brand_profile: analyzingBrand } as never)

    const { result } = renderHook(() => useBrandProfile('brand-abc'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.brand?.analysis_status).toBe('analyzing')
  })

  it('polls when analysis_status is analyzing (exercises pollWhen callback)', async () => {
    vi.useFakeTimers()
    const analyzingBrand = { ...mockBrandProfile, analysis_status: 'analyzing' }
    vi.mocked(api.getBrand).mockResolvedValue({ brand_profile: analyzingBrand } as never)

    renderHook(() => useBrandProfile('brand-abc'))

    await act(async () => {
      await Promise.resolve()
    })

    const callCountBefore = vi.mocked(api.getBrand).mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(4000)
      await Promise.resolve()
    })

    // pollWhen returns true (analyzing), so another fetch should have happened
    expect(vi.mocked(api.getBrand).mock.calls.length).toBeGreaterThan(callCountBefore)

    vi.useRealTimers()
  })
})
