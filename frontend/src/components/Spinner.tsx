import { A } from '../theme'

// Inject keyframes once globally
if (typeof document !== 'undefined' && !document.getElementById('amp-spin-style')) {
  const style = document.createElement('style')
  style.id = 'amp-spin-style'
  style.textContent = '@keyframes amp-spin { to { transform: rotate(360deg); } }'
  document.head.appendChild(style)
}

interface Props {
  size?: number
  color?: string
  style?: React.CSSProperties
}

export default function Spinner({ size = 20, color = A.indigo, style }: Props) {
  return (
    <span
      role="status"
      aria-label="Loading"
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        borderRadius: '50%',
        border: `${Math.max(2, Math.round(size / 8))}px solid ${color}33`,
        borderTopColor: color,
        animation: 'amp-spin 0.8s linear infinite',
        flexShrink: 0,
        ...style,
      }}
    />
  )
}
