import { MdOutlinePostAdd, MdOutlineCalendarMonth } from 'react-icons/md'
import { A } from '../theme'

interface Props {
  onCreatePost: () => void
  onPlanWeek: () => void
}

export default function CreateTab({ onCreatePost, onPlanWeek }: Props) {
  return (
    <div style={{ padding: '8px 0' }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: A.text, margin: '0 0 20px' }}>
        What would you like to create?
      </h2>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{
          background: A.surface,
          border: `1px solid ${A.border}`,
          borderRadius: 12,
          padding: 28,
          flex: 1,
          minWidth: 240,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          <MdOutlinePostAdd size={32} color={A.indigo} />
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: A.text, margin: '0 0 6px' }}>
              Quick Post
            </h3>
            <p style={{ fontSize: 13, color: A.textSoft, margin: 0, lineHeight: 1.5 }}>
              Generate one post now for any topic or idea
            </p>
          </div>
          <button
            onClick={onCreatePost}
            style={{
              padding: '9px 0', borderRadius: 8, border: 'none',
              background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
              color: 'white', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              marginTop: 'auto',
            }}
          >
            Create Post
          </button>
        </div>

        <div style={{
          background: A.surface,
          border: `1px solid ${A.border}`,
          borderRadius: 12,
          padding: 28,
          flex: 1,
          minWidth: 240,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          <MdOutlineCalendarMonth size={32} color={A.violet} />
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: A.text, margin: '0 0 6px' }}>
              Weekly Plan
            </h3>
            <p style={{ fontSize: 13, color: A.textSoft, margin: 0, lineHeight: 1.5 }}>
              Plan 7 days of content with an AI calendar
            </p>
          </div>
          <button
            onClick={onPlanWeek}
            style={{
              padding: '9px 0', borderRadius: 8,
              border: `1px solid ${A.border}`,
              background: 'transparent',
              color: A.textSoft, fontSize: 13, fontWeight: 500, cursor: 'pointer',
              marginTop: 'auto',
            }}
          >
            Plan My Week
          </button>
        </div>
      </div>
    </div>
  )
}
