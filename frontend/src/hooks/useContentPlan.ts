import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { Plan, DayBrief } from '../types'

export type { Plan, TrendSummary } from '../types'

function normalizePlan(raw: Record<string, unknown>): Plan {
  return {
    plan_id: raw.plan_id as string,
    days: (raw.days as DayBrief[]) ?? [],
    num_days: raw.num_days as number | undefined,
    status: raw.status as string | undefined,
    created_at: raw.created_at as string | undefined,
    trend_summary: raw.trend_summary as Plan['trend_summary'] ?? undefined,
  }
}

export function useContentPlan(brandId: string) {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!brandId) return
    setLoading(true)
    api.listPlans(brandId)
      .then((res: unknown) => {
        const plans = ((res as Record<string, unknown>).plans as Record<string, unknown>[]) || []
        if (plans.length > 0) setPlan(normalizePlan(plans[0]))
      })
      .catch((err: unknown) => {
        setError((err as Error).message || 'Failed to load your saved plan. You can generate a new one below.')
      })
      .finally(() => setLoading(false))
  }, [brandId])

  const generatePlan = async (numDays = 7, businessEvents?: string, platforms?: string[]) => {
    setGenerating(true)
    setError('')
    try {
      const result = await api.createPlan(brandId, numDays, businessEvents, platforms) as unknown as Record<string, unknown>
      setPlan(normalizePlan(result))
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to generate plan')
    } finally {
      setGenerating(false)
    }
  }

  const updateDay = async (planId: string, dayIndex: number, data: Record<string, unknown>) => {
    setLoading(true)
    try {
      await api.updateDay(brandId, planId, dayIndex, data)
      const updated = await api.getPlan(brandId, planId) as unknown as Record<string, unknown>
      if (updated?.plan_profile) {
        setPlan(normalizePlan({ plan_id: planId, ...(updated.plan_profile as Record<string, unknown>) }))
      }
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to update day')
    } finally {
      setLoading(false)
    }
  }

  const setDayCustomPhoto = (planId: string, dayIndex: number, photoUrl: string | null) => {
    setPlan((prev) => {
      if (!prev || prev.plan_id !== planId) return prev
      const days = [...(prev.days || [])]
      if (days[dayIndex]) {
        days[dayIndex] = { ...days[dayIndex], custom_photo_url: photoUrl }
      }
      return { ...prev, days }
    })
  }

  return { plan, loading, generating, error, generatePlan, updateDay, setDayCustomPhoto, clearPlan: () => setPlan(null) }
}
