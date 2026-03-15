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

export function computePlacement(rect: DOMRect, isMobile: boolean): Placement {
  if (isMobile) {
    return rect.bottom + 200 > window.innerHeight ? 'top' : 'bottom'
  }
  const spaceBelow = window.innerHeight - rect.bottom
  const spaceAbove = rect.top
  const spaceRight = window.innerWidth - rect.right
  const spaceLeft = rect.left

  if (spaceBelow >= 180) return 'bottom'
  if (spaceAbove >= 180) return 'top'
  if (spaceRight >= 280) return 'right'
  if (spaceLeft >= 280) return 'left'
  return 'bottom'
}

export function getTooltipStyle(
  placement: Placement,
  cutout: Cutout,
  isMobile: boolean,
  transitioning: boolean,
): React.CSSProperties {
  const style: React.CSSProperties = {
    position: 'fixed',
    zIndex: OVERLAY_Z + 2,
    width: isMobile ? 'calc(100vw - 32px)' : 320,
    maxWidth: isMobile ? 'calc(100vw - 32px)' : 360,
    opacity: transitioning ? 0 : 1,
    transition: 'opacity 0.2s ease',
  }

  if (isMobile) {
    style.left = 16
    if (placement === 'top') {
      style.bottom = window.innerHeight - cutout.y + TOOLTIP_GAP
    } else {
      style.top = cutout.y + cutout.h + TOOLTIP_GAP
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

export function getArrowStyle(placement: Placement, cutout: Cutout): React.CSSProperties {
  const style: React.CSSProperties = {
    position: 'absolute',
    width: 0,
    height: 0,
    border: `${ARROW_SIZE}px solid transparent`,
  }

  switch (placement) {
    case 'bottom':
      style.top = -ARROW_SIZE * 2
      style.left = Math.min(32, cutout.w / 2)
      style.borderBottomColor = A.surface
      break
    case 'top':
      style.bottom = -ARROW_SIZE * 2
      style.left = Math.min(32, cutout.w / 2)
      style.borderTopColor = A.surface
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
