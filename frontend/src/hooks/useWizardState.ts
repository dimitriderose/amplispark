import { useState, useCallback, useEffect } from 'react'

export interface WizardData {
  // Step 1
  businessName: string
  description: string
  websiteUrl: string
  industry: string
  // Step 2
  tone: string
  targetAudience: string
  colors: string[]
  logoFile: File | null
  assets: File[]
  // Step 3
  platformMode: 'ai' | 'manual'
  selectedPlatforms: string[]
}

const INITIAL_DATA: WizardData = {
  businessName: '',
  description: '',
  websiteUrl: '',
  industry: '',
  tone: '',
  targetAudience: '',
  colors: [],
  logoFile: null,
  assets: [],
  platformMode: 'ai',
  selectedPlatforms: [],
}

const STORAGE_KEY = 'amplifi_wizard'

/** Restore serializable fields from sessionStorage (files can't be persisted). */
function loadSaved(): { step: number; data: Partial<WizardData> } | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function useWizardState() {
  const saved = loadSaved()
  const [step, setStep] = useState(saved?.step ?? 1)
  const [data, setData] = useState<WizardData>({ ...INITIAL_DATA, ...saved?.data })

  // Persist text fields to sessionStorage on change (files excluded — can't serialize)
  useEffect(() => {
    const { logoFile: _l, assets: _a, ...serializable } = data
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ step, data: serializable }))
  }, [step, data])

  const update = useCallback(<K extends keyof WizardData>(key: K, value: WizardData[K]) => {
    setData(prev => ({ ...prev, [key]: value }))
  }, [])

  const canAdvance = useCallback((s: number): boolean => {
    switch (s) {
      case 1:
        return data.businessName.trim().length > 0 && data.description.trim().length >= 20
      default:
        return true
    }
  }, [data.businessName, data.description])

  const next = useCallback(() => {
    if (step < 3 && canAdvance(step)) setStep(s => s + 1)
  }, [step, canAdvance])

  const back = useCallback(() => {
    if (step > 1) setStep(s => s - 1)
  }, [step])

  /** Clear persisted wizard data (call after successful brand creation). */
  const clear = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY)
  }, [])

  return { step, data, update, next, back, canAdvance, clear }
}
