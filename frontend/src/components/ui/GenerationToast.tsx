import { A } from '../../theme'

interface Props {
  onDismiss: () => void
}

export default function GenerationToast({ onDismiss }: Props) {
  return (
    <div
      onClick={onDismiss}
      style={{
        position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)',
        background: A.indigo, color: '#fff',
        padding: '12px 20px', borderRadius: 10,
        fontSize: 13, fontWeight: 500,
        boxShadow: '0 4px 20px rgba(91,95,246,0.35)',
        cursor: 'pointer', zIndex: 1100,
        display: 'flex', alignItems: 'center', gap: 8,
        whiteSpace: 'nowrap',
      }}
    >
      <span>✓</span>
      <span>You can leave — we'll notify you when it's done</span>
    </div>
  )
}
