import { A } from '../../theme'

interface Props {
  message: string
  onDismiss?: () => void
}

export default function ErrorBanner({ message, onDismiss }: Props) {
  return (
    <div style={{
      marginBottom: 16,
      padding: '10px 16px',
      borderRadius: 8,
      background: '#FFF0F0',
      border: `1px solid ${A.coral}30`,
      color: A.coral,
      fontSize: 13,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 8,
    }}>
      <span>{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          style={{
            background: 'none',
            border: 'none',
            color: A.coral,
            cursor: 'pointer',
            fontSize: 16,
            lineHeight: 1,
            padding: 0,
            flexShrink: 0,
          }}
        >
          x
        </button>
      )}
    </div>
  )
}
