import { useState, useEffect } from 'react'
import { api } from '../api/client'

interface Plan {
  plan_id: string
  days: any[]
  num_days?: number
  status?: string
  created_at?: string
  trend_summary?: {
    researched_at: string
    platform_trends: Record<string, any>
    visual_trends: Record<string, any> | null
    video_trends: Record<string, any> | null
  }
}

function normalizePlan(raw: any): Plan {
  return {
    plan_id: raw.plan_id,
    days: raw.days ?? [],
    num_days: raw.num_days,
    status: raw.status,
    created_at: raw.created_at,
    trend_summary: raw.trend_summary ?? undefined,
  }
}

export function useContentPlan(brandId: string) {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  // Load the most recent plan on mount (so page refresh restores the calendar)
  useEffect(() => {
    if (!brandId) return
    setLoading(true)
    api.listPlans(brandId)
      .then((res: any) => {
        const plans: any[] = res.plans || []
        if (plans.length > 0) setPlan(normalizePlan(plans[0]))
      })
      .catch((err: any) => {
        setError(err.message || 'Failed to load your saved plan. You can generate a new one below.')
      })
      .finally(() => setLoading(false))
  }, [brandId])

  const generatePlan = async (numDays = 7, businessEvents?: string, platforms?: string[]) => {
    setGenerating(true)
    setError('')
    try {
      const result = await api.createPlan(brandId, numDays, businessEvents, platforms) as any
      setPlan(normalizePlan(result))
    } catch (err: any) {
      setError(err.message || 'Failed to generate plan')
    } finally {
      setGenerating(false)
    }
  }

  const updateDay = async (planId: string, dayIndex: number, data: any) => {
    setLoading(true)
    try {
      await api.updateDay(brandId, planId, dayIndex, data)
      // Refresh plan after updating a day
      const updated = await api.getPlan(brandId, planId) as any
      if (updated?.plan_profile) {
        setPlan(normalizePlan({ plan_id: planId, ...updated.plan_profile }))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to update day')
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
