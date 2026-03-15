import { A } from '../theme'
import type { Cutout } from '../hooks/useTooltipPlacement'

const OVERLAY_Z = 10000

interface Props {
  cutout: Cutout
  maskId: string
  visible: boolean
  transitioning: boolean
  onClick: () => void
}

export default function TourOverlay({ cutout, maskId, visible, transitioning, onClick }: Props) {
  if (!visible) return null

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
          transition: 'opacity 0.25s ease',
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
              style={{
                transition: 'x 0.3s ease, y 0.3s ease, width 0.3s ease, height 0.3s ease',
              }}
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

      {/* Click blocker — pointer-events:none lets touch/scroll through,
          SVG overlay handles the visual dimming */}

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
          willChange: 'left, top, width, height, opacity',
          transition: 'left 0.3s ease, top 0.3s ease, width 0.3s ease, height 0.3s ease, opacity 0.25s ease',
          opacity: transitioning ? 0 : 1,
        }}
      />
    </>
  )
}
