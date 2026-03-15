import { useEffect, useState, useCallback, useRef } from 'react'
import { A } from '../theme'
import { useIsSmallScreen } from '../hooks/useIsMobile'
import { computePlacement, getTooltipStyle, getArrowStyle } from '../hooks/useTooltipPlacement'
import type { Placement, Cutout } from '../hooks/useTooltipPlacement'
import TourOverlay from './TourOverlay'

export interface TourStep {
  targetSelector: string
  title: string
  description: string
  /** If set, called before positioning so the correct tab/view is shown */
  onBeforeShow?: () => void
}

interface Props {
  steps: TourStep[]
  isActive: boolean
  currentStep: number
  onNext: () => void
  onPrev: () => void
  onSkip: () => void
}

const PADDING = 8

let _maskIdCounter = 0

/**
 * Waits for a smooth scroll to finish by polling `scrollY` until it stabilises.
 * Resolves immediately when no scroll is needed.
 */
function waitForScrollEnd(): Promise<void> {
  return new Promise((resolve) => {
    let lastY = window.scrollY
    let sameCount = 0
    const check = () => {
      if (window.scrollY === lastY) {
        sameCount++
        // 3 consecutive unchanged frames (~50ms) = scroll done
        if (sameCount >= 3) { resolve(); return }
      } else {
        sameCount = 0
        lastY = window.scrollY
      }
      requestAnimationFrame(check)
    }
    requestAnimationFrame(check)
  })
}

/** Phases for smooth step transitions */
type TransitionPhase = 'idle' | 'fade-out' | 'scrolling' | 'fade-in'

export default function GuidedTour({ steps, isActive, currentStep, onNext, onPrev, onSkip }: Props) {
  const isSmallScreen = useIsSmallScreen()
  const [maskId] = useState(() => `tour-mask-${++_maskIdCounter}`)
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)
  const [placement, setPlacement] = useState<Placement>('bottom')
  const [visible, setVisible] = useState(false)
  const [phase, setPhase] = useState<TransitionPhase>('idle')
  const tooltipRef = useRef<HTMLDivElement>(null)
  const prevStep = useRef(currentStep)
  const phaseAbort = useRef<AbortController | null>(null)

  const step = steps[currentStep]
  const isLastStep = currentStep === steps.length - 1

  const findTarget = useCallback((): Element | null => {
    if (!step) return null
    return document.querySelector(`[data-tour-id="${step.targetSelector}"]`)
  }, [step])

  const computePlacementCb = useCallback((rect: DOMRect): Placement => {
    return computePlacement(rect, isSmallScreen)
  }, [isSmallScreen])

  const skipPendingRef = useRef(false)
  const isActiveRef = useRef(isActive)
  isActiveRef.current = isActive
  const onNextRef = useRef(onNext)
  onNextRef.current = onNext
  const onSkipRef = useRef(onSkip)
  onSkipRef.current = onSkip
  const skipTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  /** Measure target and update spotlight + tooltip position (no scrolling) */
  const measureAndUpdate = useCallback(() => {
    const el = findTarget()
    if (!el) return false
    const rect = el.getBoundingClientRect()
    setTargetRect(rect)
    setPlacement(computePlacementCb(rect))
    return true
  }, [findTarget, computePlacementCb])

  /** Scroll the target into view with smooth behaviour, then re-measure */
  const scrollToTarget = useCallback(async (signal: AbortSignal): Promise<boolean> => {
    const el = findTarget()
    if (!el) return false

    const rect = el.getBoundingClientRect()
    const margin = 120 // px above element to scroll to
    const inViewport = rect.top >= margin && rect.bottom <= window.innerHeight - 80

    if (!inViewport) {
      window.scrollTo({
        top: rect.top + window.scrollY - margin,
        behavior: 'smooth',
      })
      await waitForScrollEnd()
      if (signal.aborted) return false
    }

    // Final measurement after scroll
    const newRect = el.getBoundingClientRect()
    setTargetRect(newRect)
    setPlacement(computePlacementCb(newRect))
    return true
  }, [findTarget, computePlacementCb])

  /**
   * Orchestrate the full step transition:
   * 1. Fade out current spotlight + tooltip
   * 2. Smooth-scroll to new target
   * 3. Fade in new spotlight + tooltip
   */
  const transitionToStep = useCallback(async (signal: AbortSignal) => {
    // Phase 1: Fade out (200ms matches CSS transition)
    setPhase('fade-out')
    await new Promise((r) => setTimeout(r, 220))
    if (signal.aborted) return

    // Phase 2: Scroll to target
    setPhase('scrolling')

    // Poll for target element (may need time after tab switch)
    let el: Element | null = null
    for (let i = 0; i < 20; i++) {
      el = document.querySelector(`[data-tour-id="${steps[currentStep]?.targetSelector}"]`)
      if (el) break
      await new Promise((r) => setTimeout(r, 50))
      if (signal.aborted) return
    }

    if (!el) {
      // Target not in DOM — skip to next step
      if (isActiveRef.current && !skipPendingRef.current) {
        skipPendingRef.current = true
        const isLast = currentStep >= steps.length - 1
        setTimeout(() => {
          skipPendingRef.current = false
          if (!isActiveRef.current) return
          if (isLast) onSkipRef.current()
          else onNextRef.current()
        }, 50)
      }
      return
    }

    const scrolled = await scrollToTarget(signal)
    if (signal.aborted || !scrolled) return

    // Phase 3: Fade in
    setPhase('fade-in')
    setVisible(true)

    // Let the fade-in transition play, then go idle
    await new Promise((r) => setTimeout(r, 250))
    if (signal.aborted) return
    setPhase('idle')
  }, [currentStep, steps, scrollToTarget])

  // Handle step changes with smooth transition
  useEffect(() => {
    if (skipTimerRef.current) { clearTimeout(skipTimerRef.current); skipTimerRef.current = null }

    if (!isActive) {
      setVisible(false)
      setPhase('idle')
      return
    }

    // Switch to the right tab/view immediately
    const step = steps[currentStep]
    if (step?.onBeforeShow) step.onBeforeShow()

    // Abort any in-progress transition
    if (phaseAbort.current) phaseAbort.current.abort()
    const controller = new AbortController()
    phaseAbort.current = controller

    if (prevStep.current !== currentStep) {
      // Step changed — run full transition
      prevStep.current = currentStep
      transitionToStep(controller.signal)
    } else {
      // First mount or same step — just show immediately
      // Poll for target then show
      let pollCount = 0
      const maxPolls = 20
      const showTimer = setInterval(() => {
        pollCount++
        const el = findTarget()
        if (el || pollCount >= maxPolls) {
          clearInterval(showTimer)
          if (el) {
            const rect = el.getBoundingClientRect()
            const margin = 120
            const inViewport = rect.top >= margin && rect.bottom <= window.innerHeight - 80
            if (!inViewport) {
              window.scrollTo({
                top: rect.top + window.scrollY - margin,
                behavior: 'smooth',
              })
              waitForScrollEnd().then(() => {
                if (controller.signal.aborted) return
                measureAndUpdate()
                setVisible(true)
                setPhase('idle')
              })
            } else {
              measureAndUpdate()
              setVisible(true)
              setPhase('idle')
            }
          }
        }
      }, 50)

      return () => {
        clearInterval(showTimer)
        controller.abort()
      }
    }

    return () => { controller.abort() }
  }, [isActive, currentStep, steps, findTarget, measureAndUpdate, transitionToStep])

  // Live-track element position during scroll/resize (smooth follow)
  useEffect(() => {
    if (!isActive || !visible) return

    let rafId: number | null = null
    const handleUpdate = () => {
      if (rafId !== null) return
      rafId = requestAnimationFrame(() => {
        measureAndUpdate()
        rafId = null
      })
    }
    window.addEventListener('resize', handleUpdate)
    window.addEventListener('scroll', handleUpdate, true)
    return () => {
      window.removeEventListener('resize', handleUpdate)
      window.removeEventListener('scroll', handleUpdate, true)
      if (rafId !== null) cancelAnimationFrame(rafId)
    }
  }, [isActive, visible, measureAndUpdate])

  // Handle Escape key
  useEffect(() => {
    if (!isActive) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onSkipRef.current()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [isActive])

  if (!isActive || !targetRect || !step || !visible) return null

  // Spotlight cutout dimensions
  const cutout: Cutout = {
    x: targetRect.left - PADDING,
    y: targetRect.top - PADDING,
    w: targetRect.width + PADDING * 2,
    h: targetRect.height + PADDING * 2,
    r: 8,
  }

  const isFadedOut = phase === 'fade-out' || phase === 'scrolling'
  const tooltipStyle = getTooltipStyle(placement, cutout, isSmallScreen, isFadedOut)
  const arrowStyle = getArrowStyle(placement, cutout, isSmallScreen)

  return (
    <>
      <TourOverlay
        cutout={cutout}
        maskId={maskId}
        visible={visible}
        transitioning={isFadedOut}
        onClick={onSkip}
      />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Tour step ${currentStep + 1} of ${steps.length}: ${step.title}`}
        style={tooltipStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            position: 'relative',
            background: A.surface,
            borderRadius: 12,
            boxShadow: '0 8px 32px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.08)',
            border: `1px solid ${A.border}`,
            padding: '18px 20px 16px',
          }}
        >
          {/* Arrow */}
          <div style={arrowStyle} />

          {/* Step counter */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 10,
          }}>
            <span style={{
              fontSize: 11,
              fontWeight: 600,
              color: A.indigo,
              background: A.indigoLight,
              padding: '2px 10px',
              borderRadius: 20,
            }}>
              {currentStep + 1} of {steps.length}
            </span>
          </div>

          {/* Title */}
          <h4 style={{
            fontSize: 15,
            fontWeight: 700,
            color: A.text,
            margin: '0 0 6px',
            lineHeight: 1.3,
          }}>
            {step.title}
          </h4>

          {/* Description */}
          <p style={{
            fontSize: 13,
            color: A.textSoft,
            margin: '0 0 16px',
            lineHeight: 1.5,
          }}>
            {step.description}
          </p>

          {/* Controls */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <button
              onClick={onSkip}
              style={{
                padding: '6px 14px',
                borderRadius: 7,
                border: `1px solid ${A.border}`,
                background: 'transparent',
                color: A.textSoft,
                fontSize: 12,
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              Skip Tour
            </button>
            <div style={{ display: 'flex', gap: 6 }}>
            {currentStep > 0 && (
              <button
                onClick={onPrev}
                disabled={phase !== 'idle'}
                style={{
                  padding: '6px 14px',
                  borderRadius: 7,
                  border: `1px solid ${A.border}`,
                  background: 'transparent',
                  color: A.textSoft,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: phase !== 'idle' ? 'not-allowed' : 'pointer',
                  opacity: phase !== 'idle' ? 0.5 : 1,
                }}
              >
                Back
              </button>
            )}
            <button
              onClick={onNext}
              disabled={phase !== 'idle'}
              style={{
                padding: '6px 18px',
                borderRadius: 7,
                border: 'none',
                background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                color: 'white',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: `0 2px 8px ${A.indigo}40`,
              }}
            >
              {isLastStep ? 'Done' : 'Next'}
            </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
