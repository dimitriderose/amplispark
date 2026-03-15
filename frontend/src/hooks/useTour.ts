import { useState, useEffect, useCallback, useRef } from 'react'

const STORAGE_PREFIX = 'amplifi_tour_completed_'

export interface UseTourReturn {
  isActive: boolean
  currentStep: number
  totalSteps: number
  start: () => void
  next: () => void
  prev: () => void
  skip: () => void
  reset: () => void
}

/**
 * Hook to manage the guided tour state.
 * Tracks completion per brand in localStorage.
 * Auto-starts on first mount if not completed and `ready` is true.
 */
export function useTour(brandId: string | undefined, totalSteps: number, ready: boolean): UseTourReturn {
  const [isActive, setIsActive] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const autoStarted = useRef(false)

  // Reset auto-start flag when brand changes
  useEffect(() => { autoStarted.current = false }, [brandId])

  const storageKey = brandId ? `${STORAGE_PREFIX}${brandId}` : null

  const isCompleted = useCallback((): boolean => {
    if (!storageKey) return true
    return localStorage.getItem(storageKey) === 'true'
  }, [storageKey])

  const markCompleted = useCallback(() => {
    if (storageKey) localStorage.setItem(storageKey, 'true')
  }, [storageKey])

  // Auto-start on first mount if not completed and ready
  useEffect(() => {
    if (ready && !autoStarted.current && !isCompleted()) {
      autoStarted.current = true
      // Small delay to let DOM elements render
      const timer = setTimeout(() => {
        setIsActive(true)
        setCurrentStep(0)
      }, 800)
      return () => clearTimeout(timer)
    }
  }, [ready, isCompleted])

  const start = useCallback(() => {
    setCurrentStep(0)
    setIsActive(true)
  }, [])

  const next = useCallback(() => {
    setCurrentStep(prev => {
      if (prev >= totalSteps - 1) {
        setIsActive(false)
        markCompleted()
        return prev
      }
      return prev + 1
    })
  }, [totalSteps, markCompleted])

  const prev = useCallback(() => {
    setCurrentStep(p => Math.max(0, p - 1))
  }, [])

  const skip = useCallback(() => {
    setIsActive(false)
    markCompleted()
  }, [markCompleted])

  const reset = useCallback(() => {
    if (storageKey) localStorage.removeItem(storageKey)
    autoStarted.current = false
  }, [storageKey])

  return { isActive, currentStep, totalSteps, start, next, prev, skip, reset }
}
