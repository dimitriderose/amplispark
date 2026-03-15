import React, { useEffect, useState, useCallback, useRef } from 'react'
import { A } from '../theme'
import { useIsMobile } from '../hooks/useIsMobile'

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

type Placement = 'top' | 'bottom' | 'left' | 'right'

const PADDING = 8
const ARROW_SIZE = 8
const TOOLTIP_GAP = 12
const OVERLAY_Z = 10000

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

  const computePlacement = useCallback((rect: DOMRect): Placement => {
    if (isMobile) {
      // On mobile, prefer bottom unless near the bottom of the viewport
      return rect.bottom + 200 > window.innerHeight ? 'top' : 'bottom'
    }
    const spaceBelow = window.innerHeight - rect.bottom
    const spaceAbove = rect.top
    const spaceRight = window.innerWidth - rect.right
    const spaceLeft = rect.left

    // Prefer bottom, then top, then right, then left
    if (spaceBelow >= 180) return 'bottom'
    if (spaceAbove >= 180) return 'top'
    if (spaceRight >= 280) return 'right'
    if (spaceLeft >= 280) return 'left'
    return 'bottom'
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
    setPlacement(computePlacement(rect))

    // Scroll target into view if needed
    const inViewport = rect.top >= 0 && rect.bottom <= window.innerHeight
    if (!inViewport) {
      el.scrollIntoView({ behavior: 'instant', block: 'center' })
      // Re-measure after scroll
      requestAnimationFrame(() => {
        const newRect = el.getBoundingClientRect()
        setTargetRect(newRect)
        setPlacement(computePlacement(newRect))
      })
    }
  }, [findTarget, computePlacement])

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
  const cutout = {
    x: targetRect.left - PADDING,
    y: targetRect.top - PADDING,
    w: targetRect.width + PADDING * 2,
    h: targetRect.height + PADDING * 2,
    r: 8,
  }

  // Tooltip positioning
  const tooltipStyle: React.CSSProperties = {
    position: 'fixed',
    zIndex: OVERLAY_Z + 2,
    width: isMobile ? 'calc(100vw - 32px)' : 320,
    maxWidth: isMobile ? 'calc(100vw - 32px)' : 360,
    opacity: transitioning ? 0 : 1,
    transition: 'opacity 0.2s ease',
  }

  if (isMobile) {
    // Center horizontally on mobile
    tooltipStyle.left = 16
    if (placement === 'top') {
      tooltipStyle.bottom = window.innerHeight - cutout.y + TOOLTIP_GAP
    } else {
      tooltipStyle.top = cutout.y + cutout.h + TOOLTIP_GAP
    }
  } else {
    switch (placement) {
      case 'bottom':
        tooltipStyle.top = cutout.y + cutout.h + TOOLTIP_GAP
        tooltipStyle.left = Math.max(16, Math.min(cutout.x, window.innerWidth - 340))
        break
      case 'top':
        tooltipStyle.bottom = window.innerHeight - cutout.y + TOOLTIP_GAP
        tooltipStyle.left = Math.max(16, Math.min(cutout.x, window.innerWidth - 340))
        break
      case 'right':
        tooltipStyle.top = Math.max(16, cutout.y)
        tooltipStyle.left = cutout.x + cutout.w + TOOLTIP_GAP
        break
      case 'left':
        tooltipStyle.top = Math.max(16, cutout.y)
        tooltipStyle.right = window.innerWidth - cutout.x + TOOLTIP_GAP
        break
    }
  }

  // Arrow positioning
  const arrowStyle: React.CSSProperties = {
    position: 'absolute',
    width: 0,
    height: 0,
    border: `${ARROW_SIZE}px solid transparent`,
  }

  switch (placement) {
    case 'bottom':
      arrowStyle.top = -ARROW_SIZE * 2
      arrowStyle.left = Math.min(32, cutout.w / 2)
      arrowStyle.borderBottomColor = A.surface
      break
    case 'top':
      arrowStyle.bottom = -ARROW_SIZE * 2
      arrowStyle.left = Math.min(32, cutout.w / 2)
      arrowStyle.borderTopColor = A.surface
      break
    case 'right':
      arrowStyle.top = 20
      arrowStyle.left = -ARROW_SIZE * 2
      arrowStyle.borderRightColor = A.surface
      break
    case 'left':
      arrowStyle.top = 20
      arrowStyle.right = -ARROW_SIZE * 2
      arrowStyle.borderLeftColor = A.surface
      break
  }

  return (
    <>
      {/* Dark overlay with spotlight cutout */}
      <svg
        style={{
          position: 'fixed',
          inset: 0,
          width: '100vw',
          height: '100vh',
          zIndex: OVERLAY_Z,
          pointerEvents: 'none',
          transition: 'opacity 0.2s ease',
          opacity: transitioning ? 0 : 1,
        }}
      >
        <defs>
          <mask id={maskId}>
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            <rect
              x={cutout.x}
              y={cutout.y}
              width={cutout.w}
              height={cutout.h}
              rx={cutout.r}
              ry={cutout.r}
              fill="black"
            />
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          fill="rgba(0,0,0,0.5)"
          mask={`url(#${maskId})`}
        />
      </svg>

      {/* Click blocker on overlay area (but not on cutout) */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: OVERLAY_Z + 1,
          cursor: 'default',
        }}
        onClick={onSkip}
      />

      {/* Spotlight border ring */}
      <div
        style={{
          position: 'fixed',
          left: cutout.x,
          top: cutout.y,
          width: cutout.w,
          height: cutout.h,
          borderRadius: cutout.r,
          border: `2px solid ${A.indigo}`,
          boxShadow: `0 0 0 4px ${A.indigo}22`,
          zIndex: OVERLAY_Z + 1,
          pointerEvents: 'none',
          transition: 'all 0.3s ease',
          opacity: transitioning ? 0 : 1,
        }}
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
