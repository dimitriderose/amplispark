import { renderHook, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('../../api/client', () => import('../mocks/client'))

import { useContentPlan } from '../../hooks/useContentPlan'
import { api } from '../../api/client'

const mockPlan = {
  plan_id: 'plan-001',
  days: [{ day_index: 0, theme: 'Intro', platform: 'instagram' }],
  num_days: 7,
  status: 'complete',
  created_at: '2026-01-01',
}

describe('useContentPlan', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads plan on mount when brandId is provided', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(api.listPlans).toHaveBeenCalledWith('brand-123')
    expect(result.current.plan).not.toBeNull()
    expect(result.current.plan?.plan_id).toBe('plan-001')
  })

  it('returns null plan when no plans are returned', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.plan).toBeNull()
  })

  it('does not fetch when brandId is empty', async () => {
    const { result } = renderHook(() => useContentPlan(''))

    await new Promise(r => setTimeout(r, 20))

    expect(api.listPlans).not.toHaveBeenCalled()
    expect(result.current.plan).toBeNull()
  })

  it('generatePlan calls api.createPlan and updates state', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [] } as never)
    vi.mocked(api.createPlan).mockResolvedValue({
      plan_id: 'plan-new',
      days: [],
      num_days: 7,
      status: 'complete',
    } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.generatePlan(7)
    })

    expect(api.createPlan).toHaveBeenCalledWith('brand-123', 7, undefined, undefined)
    expect(result.current.plan).not.toBeNull()
    expect(result.current.plan?.plan_id).toBe('plan-new')
  })

  it('exposes error when generatePlan fails', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [] } as never)
    vi.mocked(api.createPlan).mockRejectedValue(new Error('Generation failed'))

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.generatePlan(7)
    })

    expect(result.current.error).toBe('Generation failed')
  })

  it('generatePlan passes numDays, businessEvents, and platforms', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [] } as never)
    vi.mocked(api.createPlan).mockResolvedValue({
      plan_id: 'plan-xyz',
      days: [],
      num_days: 5,
      status: 'complete',
    } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.generatePlan(5, 'Grand opening', ['instagram', 'linkedin'])
    })

    expect(api.createPlan).toHaveBeenCalledWith('brand-123', 5, 'Grand opening', ['instagram', 'linkedin'])
    expect(result.current.plan?.plan_id).toBe('plan-xyz')
  })

  it('updateDay calls api.updateDay and then api.getPlan to refresh', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)
    vi.mocked(api.updateDay).mockResolvedValue({} as never)
    vi.mocked(api.getPlan).mockResolvedValue({
      plan_profile: { ...mockPlan, days: [{ day_index: 0, theme: 'Updated' }] },
    } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.updateDay('plan-001', 0, { theme: 'Updated' })
    })

    expect(api.updateDay).toHaveBeenCalledWith('brand-123', 'plan-001', 0, { theme: 'Updated' })
    expect(api.getPlan).toHaveBeenCalledWith('brand-123', 'plan-001')
  })

  it('updateDay exposes error when api.updateDay fails', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)
    vi.mocked(api.updateDay).mockRejectedValue(new Error('Update failed'))

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.updateDay('plan-001', 0, { theme: 'Bad' })
    })

    expect(result.current.error).toBe('Update failed')
  })

  it('setDayCustomPhoto updates the photo URL for the target day', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => {
      result.current.setDayCustomPhoto('plan-001', 0, 'https://example.com/photo.jpg')
    })

    expect(result.current.plan?.days[0].custom_photo_url).toBe('https://example.com/photo.jpg')
  })

  it('setDayCustomPhoto ignores mismatched planId', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    const planBefore = result.current.plan

    act(() => {
      result.current.setDayCustomPhoto('wrong-plan', 0, 'https://example.com/photo.jpg')
    })

    // Plan should be unchanged since planId doesn't match
    expect(result.current.plan).toBe(planBefore)
  })

  it('clearPlan resets plan to null', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.plan).not.toBeNull())

    act(() => {
      result.current.clearPlan()
    })

    expect(result.current.plan).toBeNull()
  })

  it('exposes error when listPlans fails', async () => {
    vi.mocked(api.listPlans).mockRejectedValue(new Error('Failed to load plan'))

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.error).toContain('Failed to load')
  })

  it('normalizePlan handles missing days field (null coalescing)', async () => {
    const planNoDays = {
      plan_id: 'plan-nodys',
      // no days field — tests the ?? [] branch
      num_days: 3,
      status: 'complete',
      created_at: '2026-01-01',
    }
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [planNoDays] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.plan?.plan_id).toBe('plan-nodys')
    expect(result.current.plan?.days).toEqual([])
  })

  it('normalizePlan handles trend_summary field being present', async () => {
    const planWithTrend = {
      ...mockPlan,
      trend_summary: { summary: 'Trending topics', source: 'social' },
    }
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [planWithTrend] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.plan?.trend_summary).toBeDefined()
  })

  it('updateDay handles missing plan_profile in response', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)
    vi.mocked(api.updateDay).mockResolvedValue({} as never)
    // getPlan returns something without plan_profile
    vi.mocked(api.getPlan).mockResolvedValue({} as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    const planBefore = result.current.plan

    await act(async () => {
      await result.current.updateDay('plan-001', 0, { theme: 'Test' })
    })

    // Plan should remain unchanged since no plan_profile in response
    expect(result.current.plan?.plan_id).toBe(planBefore?.plan_id)
  })

  it('exposes generic error message when listPlans throws non-Error', async () => {
    vi.mocked(api.listPlans).mockRejectedValue('plain string error')

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.error).toBe('Failed to load your saved plan. You can generate a new one below.')
  })

  it('exposes generic error when generatePlan throws non-Error', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [] } as never)
    vi.mocked(api.createPlan).mockRejectedValue('plain string')

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.generatePlan(7)
    })

    expect(result.current.error).toBe('Failed to generate plan')
  })

  it('exposes generic error when updateDay throws non-Error', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)
    vi.mocked(api.updateDay).mockRejectedValue('string error')

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.updateDay('plan-001', 0, {})
    })

    expect(result.current.error).toBe('Failed to update day')
  })

  it('setDayCustomPhoto does not fail when dayIndex is out of bounds', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [mockPlan] } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    // dayIndex 99 is out of bounds — should be a no-op on that index
    act(() => {
      result.current.setDayCustomPhoto('plan-001', 99, 'https://example.com/photo.jpg')
    })

    // Plan days should remain unchanged
    expect(result.current.plan?.days.length).toBe(1)
    expect(result.current.plan?.days[0].custom_photo_url).toBeUndefined()
  })

  it('normalizePlan handles null listPlans response gracefully', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: null } as never)

    const { result } = renderHook(() => useContentPlan('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    // plans || [] means null becomes [] so no plan set
    expect(result.current.plan).toBeNull()
  })

  it('generatePlan clears previous error on retry', async () => {
    vi.mocked(api.listPlans).mockResolvedValue({ plans: [] } as never)
    vi.mocked(api.createPlan).mockRejectedValue(new Error('First error'))

    const { result } = renderHook(() => useContentPlan('brand-123'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.generatePlan(7)
    })
    expect(result.current.error).toBe('First error')

    // Retry with success
    vi.mocked(api.createPlan).mockResolvedValue({ plan_id: 'plan-retry', days: [], num_days: 7, status: 'complete' } as never)
    await act(async () => {
      await result.current.generatePlan(7)
    })

    expect(result.current.error).toBe('')
    expect(result.current.plan?.plan_id).toBe('plan-retry')
  })
})
