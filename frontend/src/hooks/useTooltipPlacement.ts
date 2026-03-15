import { A } from '../theme'

export type Placement = 'top' | 'bottom' | 'left' | 'right'

const ARROW_SIZE = 8
const TOOLTIP_GAP = 12
const OVERLAY_Z = 10000

export interface Cutout {
  x: number
  y: number
  w: number
  h: number
  r: number
}

export function computePlacement(rect: DOMRect, isSmallScreen: boolean): Placement {
  const spaceBelow = window.innerHeight - rect.bottom
  const spaceAbove = rect.top
  const spaceRight = window.innerWidth - rect.right
  const spaceLeft = rect.left

  // Large elements (taller than half the viewport) — always use top so tooltip
  // appears above the fold rather than a giant element
  const isLargeElement = rect.height > window.innerHeight * 0.4
  if (isLargeElement && spaceAbove >= 120) return 'top'

  // Phones (<=640px): top/bottom only — no room for side placement
  if (isSmallScreen && window.innerWidth <= 640) {
    return rect.bottom + 200 > window.innerHeight ? 'top' : 'bottom'
  }

  // Tablets + desktop: full 4-direction placement
  if (spaceBelow >= 200) return 'bottom'
  if (spaceAbove >= 200) return 'top'
  if (spaceRight >= 280) return 'right'
  if (spaceLeft >= 280) return 'left'
  return 'bottom'
}

export function getTooltipStyle(
  placement: Placement,
  cutout: Cutout,
  isSmallScreen: boolean,
  transitioning: boolean,
): React.CSSProperties {
  const style: React.CSSProperties = {
    position: 'fixed',
    zIndex: OVERLAY_Z + 2,
    width: isSmallScreen ? 'min(calc(100vw - 32px), 420px)' : 320,
    maxWidth: isSmallScreen ? 'min(calc(100vw - 32px), 420px)' : 360,
    opacity: transitioning ? 0 : 1,
    willChange: 'top, bottom, left, right, opacity',
    transition: 'opacity 0.25s ease, top 0.3s ease, bottom 0.3s ease, left 0.3s ease, right 0.3s ease',
  }

  if (isSmallScreen) {
    if (window.innerWidth > 640) {
      // Tablet: anchor to target but clamp within viewport (like Popper.js/React Joyride)
      const tw = Math.min(window.innerWidth - 32, 420)
      const idealLeft = cutout.x + cutout.w / 2 - tw / 2
      style.left = Math.max(16, Math.min(idealLeft, window.innerWidth - tw - 16))
    } else {
      // Phone: full-width, left-aligned
      style.left = 16
    }
    if (placement === 'top') {
      // Clamp: tooltip bottom can't exceed viewport height - 16px margin
      const bottomValue = window.innerHeight - cutout.y + TOOLTIP_GAP
      style.bottom = Math.min(bottomValue, window.innerHeight - 16)
      // Fallback: if target is near top and tooltip would go off-screen, use fixed top
      if (cutout.y < 200) {
        delete style.bottom
        style.top = 16
      }
    } else {
      // Clamp: tooltip top can't go below viewport
      const topValue = cutout.y + cutout.h + TOOLTIP_GAP
      style.top = Math.min(topValue, window.innerHeight - 200)
    }
  } else {
    switch (placement) {
      case 'bottom':
        style.top = cutout.y + cutout.h + TOOLTIP_GAP
        style.left = Math.max(16, Math.min(cutout.x, window.innerWidth - 340))
        break
      case 'top':
        style.bottom = window.innerHeight - cutout.y + TOOLTIP_GAP
        style.left = Math.max(16, Math.min(cutout.x, window.innerWidth - 340))
        break
      case 'right':
        style.top = Math.max(16, cutout.y)
        style.left = cutout.x + cutout.w + TOOLTIP_GAP
        break
      case 'left':
        style.top = Math.max(16, cutout.y)
        style.right = window.innerWidth - cutout.x + TOOLTIP_GAP
        break
    }
  }

  return style
}

export function getArrowStyle(placement: Placement, cutout: Cutout, isSmallScreen = false): React.CSSProperties {
  const style: React.CSSProperties = {
    position: 'absolute',
    width: 0,
    height: 0,
    border: `${ARROW_SIZE}px solid transparent`,
    transition: 'left 0.3s ease, top 0.3s ease, bottom 0.3s ease, right 0.3s ease',
  }

  // Compute arrow position so it points at the target element's center
  const targetCenterX = cutout.x + cutout.w / 2

  // Calculate tooltipLeft matching getTooltipStyle logic
  let tooltipLeft: number
  if (isSmallScreen && window.innerWidth > 640) {
    // Tablet: anchored to target, clamped
    const tw = Math.min(window.innerWidth - 32, 420)
    const idealLeft = cutout.x + cutout.w / 2 - tw / 2
    tooltipLeft = Math.max(16, Math.min(idealLeft, window.innerWidth - tw - 16))
  } else if (isSmallScreen) {
    tooltipLeft = 16
  } else {
    // Desktop: use same logic as getTooltipStyle
    const desktopWidth = 320
    tooltipLeft = Math.max(16, Math.min(cutout.x, window.innerWidth - desktopWidth - 20))
  }

  const tooltipWidth = isSmallScreen ? Math.min(window.innerWidth - 32, 420) : 320
  const arrowLeft = Math.max(16, Math.min(targetCenterX - tooltipLeft - ARROW_SIZE, tooltipWidth - 32))

  switch (placement) {
    case 'bottom':
      // Tooltip is below target — arrow at top of tooltip pointing UP at target
      style.top = -ARROW_SIZE * 2
      style.left = arrowLeft
      style.borderTopColor = 'transparent'
      style.borderBottomColor = A.surface
      style.borderLeftColor = 'transparent'
      style.borderRightColor = 'transparent'
      break
    case 'top':
      // Tooltip is above target — arrow at bottom of tooltip pointing DOWN at target
      style.bottom = -ARROW_SIZE * 2
      style.left = arrowLeft
      style.borderTopColor = A.surface
      style.borderBottomColor = 'transparent'
      style.borderLeftColor = 'transparent'
      style.borderRightColor = 'transparent'
      break
    case 'right':
      style.top = 20
      style.left = -ARROW_SIZE * 2
      style.borderRightColor = A.surface
      break
    case 'left':
      style.top = 20
      style.right = -ARROW_SIZE * 2
      style.borderLeftColor = A.surface
      break
  }

  return style
}
