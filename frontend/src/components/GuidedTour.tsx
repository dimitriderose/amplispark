import { useEffect, useState, useCallback, useRef } from 'react'
import { A } from '../theme'
import { useIsMobile } from '../hooks/useIsMobile'
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

export default function GuidedTour({ steps, isActive, currentStep, onNext, onPrev, onSkip }: Props) {
  const isMobile = useIsMobile()
  const [maskId] = useState(() => `tour-mask-${++_maskIdCounter}`)
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)
  const [placement, setPlacement] = useState<Placement>('bottom')
  const [visible, setVisible] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const prevStep = useRef(currentStep)

  const step = steps[currentStep]
  const isLastStep = currentStep === steps.length - 1

  const findTarget = useCallback((): Element | null => {
    if (!step) return null
    return document.querySelector(`[data-tour-id="${step.targetSelector}"]`)
  }, [step])

  const computePlacementCb = useCallback((rect: DOMRect): Placement => {
    return computePlacement(rect, isMobile)
  }, [isMobile])

  const skipPendingRef = useRef(false)
  const isActiveRef = useRef(isActive)
  isActiveRef.current = isActive
  const onNextRef = useRef(onNext)
  onNextRef.current = onNext
  const onSkipRef = useRef(onSkip)
  onSkipRef.current = onSkip
  const skipTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const updatePosition = useCallback(() => {
    const el = findTarget()
    if (!el) {
      // Target not in DOM — skip to next step (async to prevent cascade)
      if (isActiveRef.current && !skipPendingRef.current) {
        skipPendingRef.current = true
        // If last step target is missing, end the tour instead of looping
        const isLast = currentStep >= steps.length - 1
        skipTimerRef.current = setTimeout(() => {
          skipPendingRef.current = false
          if (!isActiveRef.current) return // tour was dismissed during timeout
          if (isLast) {
            onSkipRef.current()
          } else {
            onNextRef.current()
          }
        }, 50)
      }
      return
    }
    const rect = el.getBoundingClientRect()
    setTargetRect(rect)
    setPlacement(computePlacementCb(rect))

    // Scroll target into view if needed
    const inViewport = rect.top >= 0 && rect.bottom <= window.innerHeight
    if (!inViewport) {
      el.scrollIntoView({ behavior: 'instant', block: 'center' })
      // Re-measure after scroll
      requestAnimationFrame(() => {
        const newRect = el.getBoundingClientRect()
        setTargetRect(newRect)
        setPlacement(computePlacementCb(newRect))
      })
    }
  }, [findTarget, computePlacementCb])

  // Update position when step changes
  useEffect(() => {
    // Clean up skip timer from previous step
    if (skipTimerRef.current) { clearTimeout(skipTimerRef.current); skipTimerRef.current = null }

    if (!isActive) {
      setVisible(false)
      return
    }

    // Switch to the right tab/view immediately (before transition)
    const step = steps[currentStep]
    if (step?.onBeforeShow) step.onBeforeShow()

    // Transition effect — hide during step change to avoid stale spotlight position
    if (prevStep.current !== currentStep) {
      setVisible(false)
      setTransitioning(true)
      const timer = setTimeout(() => {
        setTransitioning(false)
        prevStep.current = currentStep
      }, 200)
      return () => clearTimeout(timer)
    }

    // Poll for target element after tab switch (replaces fixed 50ms race)
    let pollCount = 0
    const maxPolls = 20 // 20 × 50ms = 1 second max wait
    const showTimer = setInterval(() => {
      pollCount++
      const el = findTarget()
      if (el || pollCount >= maxPolls) {
        clearInterval(showTimer)
        updatePosition()
        setVisible(true)
      }
    }, 50)

    // Throttled resize/scroll listener to avoid layout thrashing
    let rafId: number | null = null
    const handleUpdate = () => {
      if (rafId !== null) return
      rafId = requestAnimationFrame(() => {
        updatePosition()
        rafId = null
      })
    }
    window.addEventListener('resize', handleUpdate)
    window.addEventListener('scroll', handleUpdate, true)
    return () => {
      clearInterval(showTimer)
      window.removeEventListener('resize', handleUpdate)
      window.removeEventListener('scroll', handleUpdate, true)
      if (rafId !== null) cancelAnimationFrame(rafId)
    }
  }, [isActive, currentStep, steps, updatePosition, transitioning])

  // Re-measure after transitioning
  useEffect(() => {
    if (isActive && !transitioning) {
      updatePosition()
    }
  }, [isActive, transitioning, updatePosition])

  // Handle Escape key (uses ref to avoid stale closure)
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

  const tooltipStyle = getTooltipStyle(placement, cutout, isMobile, transitioning)
  const arrowStyle = getArrowStyle(placement, cutout)

  return (
    <>
      <TourOverlay
        cutout={cutout}
        maskId={maskId}
        visible={visible}
        transitioning={transitioning}
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
                disabled={transitioning}
                style={{
                  padding: '6px 14px',
                  borderRadius: 7,
                  border: `1px solid ${A.border}`,
                  background: 'transparent',
                  color: A.textSoft,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: transitioning ? 'not-allowed' : 'pointer',
                  opacity: transitioning ? 0.5 : 1,
                }}
              >
                Back
              </button>
            )}
            <button
              onClick={onNext}
              disabled={transitioning}
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
