import { A } from '../theme'
import { useState } from 'react'
import { useIsMobile } from '../hooks/useIsMobile'

const PLAN_STEPS = [
  { label: 'Understanding your brand...', icon: '🎨' },
  { label: 'Mapping your weekly events', icon: '📅' },
  { label: 'Building content pillars', icon: '🏛️' },
  { label: 'Scheduling platform mix', icon: '📱' },
  { label: 'Crafting repurposing chains', icon: '♻️' },
  { label: 'Finalising your calendar', icon: '✨' },
]

interface Props {
  onGenerate: (events: string) => void
  generating: boolean
  /** Brand analysis_status — calendar is locked while 'analyzing' */
  analysisStatus?: string
}

export default function EventsInput({ onGenerate, generating, analysisStatus }: Props) {
  const isMobile = useIsMobile()
  const [events, setEvents] = useState('')

  const isBrandBuilding = analysisStatus === 'analyzing'
  const canGenerate = !generating && !isBrandBuilding

  return (
    <div>
      <style>{`
        @keyframes ei-spin { to { transform: rotate(360deg); } }
        @keyframes ei-fadein { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      <h3 style={{ fontSize: 16, fontWeight: 600, color: A.text, marginBottom: 4 }}>
        Content Calendar
      </h3>
      <p style={{ fontSize: 13, color: A.textSoft, marginBottom: 16 }}>
        Generate a personalised 7-day content plan tailored to your brand.
      </p>

      {/* Events input */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: A.textSoft, textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
          What's happening this week? <span style={{ color: A.textMuted, fontWeight: 400, textTransform: 'none' }}>(optional)</span>
        </label>
        <textarea
          value={events}
          onChange={e => setEvents(e.target.value)}
          placeholder={isMobile ? "e.g. Product launch Tue, market Sat" : "e.g. Launching lavender croissant Tuesday, farmer's market booth Saturday, staff birthday Wednesday"}
          rows={2}
          style={{
            width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13, lineHeight: 1.5,
            border: `1px solid ${A.border}`, background: A.surfaceAlt, color: A.text,
            resize: 'none', boxSizing: 'border-box',
          }}
        />
        <p style={{ fontSize: 11, color: A.textMuted, marginTop: 4 }}>
          Real events become content pillars — launches, markets, specials, milestones.
        </p>
      </div>

      {/* DK-1: Brand still analyzing — lock the calendar with a contextual message */}
      {isBrandBuilding && !generating && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, marginBottom: 12,
          background: A.indigoLight, border: `1px solid ${A.indigo}30`,
          fontSize: 12, color: A.indigo, display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <div style={{
            width: 12, height: 12, borderRadius: '50%', flexShrink: 0,
            border: `2px solid ${A.indigo}44`, borderTopColor: A.indigo,
            animation: 'ei-spin 0.8s linear infinite',
          }} />
          Your brand profile is being built — calendar will unlock in a moment.
        </div>
      )}

      {/* DK-2: Step-by-step animated progress instead of plain spinner */}
      {generating ? (
        <div style={{
          padding: '20px 16px', background: A.surfaceAlt,
          borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <div style={{
              width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
              border: `3px solid ${A.indigoLight}`, borderTopColor: A.indigo,
              animation: 'ei-spin 0.8s linear infinite',
            }} />
            <p style={{ fontSize: 14, fontWeight: 600, color: A.text, margin: 0 }}>
              Building your content plan...
            </p>
          </div>
          {PLAN_STEPS.map((step, i) => (
            <div
              key={i}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px 10px', borderRadius: 6,
                background: A.surface, border: `1px solid ${A.borderLight}`,
                animation: 'ei-fadein 0.4s ease both',
                animationDelay: `${i * 0.9}s`,
                opacity: 0,
              }}
            >
              <span style={{ fontSize: 13 }}>{step.icon}</span>
              <span style={{ fontSize: 12, color: A.textSoft }}>{step.label}</span>
            </div>
          ))}
        </div>
      ) : (
        <button
          onClick={() => canGenerate && onGenerate(events)}
          disabled={!canGenerate}
          style={{
            padding: '10px 24px', borderRadius: 8, border: 'none',
            cursor: canGenerate ? 'pointer' : 'not-allowed',
            background: canGenerate
              ? `linear-gradient(135deg, ${A.indigo}, ${A.violet})`
              : A.surfaceAlt,
            color: canGenerate ? 'white' : A.textMuted,
            fontSize: 14, fontWeight: 600,
          }}
        >
          {isBrandBuilding ? 'Building brand first...' : 'Generate Content Calendar ✨'}
        </button>
      )}
    </div>
  )
}
