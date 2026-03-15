import React from 'react'
import { A } from '../theme'
import { useVoiceCoach } from '../hooks/useVoiceCoach'
import type { VoiceCoachStatus } from '../hooks/useVoiceCoach'

interface Props {
  brandId: string
  brandName?: string
  planId?: string
}

export default function VoiceCoach({ brandId, brandName, planId }: Props) {
  const { status, isAISpeaking, transcript, error, startSession, stopSession } = useVoiceCoach()

  const isOpen = status !== 'idle'

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 28,
        right: 28,
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: 10,
      }}
    >
      <style>{`
        @keyframes vc-pulse {
          0%, 100% { transform: scale(1); opacity: 0.9; }
          50% { transform: scale(1.18); opacity: 1; }
        }
        @keyframes vc-liveblink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @keyframes vc-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes vc-activedot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.75); }
        }
      `}</style>

      {/* Expanded panel — shown when session is open */}
      {isOpen && (
        <div
          style={{
            width: 248,
            borderRadius: 14,
            background: A.surface,
            border: `1px solid ${A.border}`,
            boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
            overflow: 'hidden',
          }}
        >
          {/* Header bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 12px',
              background: `linear-gradient(135deg, ${A.violet}, ${A.indigo})`,
            }}
          >
            {/* Coach avatar with green status dot */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ position: 'relative', flexShrink: 0 }}>
                <div style={{
                  width: 30,
                  height: 30,
                  borderRadius: '50%',
                  background: 'rgba(255,255,255,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 16,
                }}>
                  🧑‍💼
                </div>
                {status === 'active' && (
                  <span style={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    width: 9,
                    height: 9,
                    borderRadius: '50%',
                    background: '#22c55e',
                    border: '1.5px solid white',
                    animation: 'vc-activedot 2s ease-in-out infinite',
                  }} />
                )}
              </div>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'white' }}>
                {brandName || 'Brand Coach'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {/* Close button */}
              <button
                onClick={stopSession}
                style={{
                  background: 'rgba(255,255,255,0.15)',
                  border: 'none',
                  borderRadius: '50%',
                  width: 22,
                  height: 22,
                  color: 'white',
                  fontSize: 13,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  lineHeight: 1,
                }}
                title="End session"
              >
                ×
              </button>
            </div>
          </div>

          {/* Body */}
          <div style={{ padding: '16px 14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>

            {/* Connecting spinner */}
            {status === 'connecting' && (
              <>
                <div style={{
                  width: 56,
                  height: 56,
                  borderRadius: '50%',
                  border: `3px solid ${A.violetLight}`,
                  borderTopColor: A.violet,
                  animation: 'vc-spin 0.9s linear infinite',
                }} />
                <p style={{ fontSize: 12, color: A.textMuted, margin: 0 }}>Connecting...</p>
              </>
            )}

            {/* Active — breathing orb */}
            {status === 'active' && (
              <>
                <div style={{ position: 'relative', width: 72, height: 72, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {/* Outer glow ring */}
                  <div style={{
                    position: 'absolute',
                    inset: 0,
                    borderRadius: '50%',
                    background: isAISpeaking
                      ? `radial-gradient(circle, ${A.violet}30, transparent 70%)`
                      : `radial-gradient(circle, ${A.indigo}18, transparent 70%)`,
                    transition: 'background 0.3s ease',
                  }} />
                  {/* Orb */}
                  <div style={{
                    width: 52,
                    height: 52,
                    borderRadius: '50%',
                    background: isAISpeaking
                      ? `linear-gradient(135deg, ${A.violet}, ${A.indigo})`
                      : `linear-gradient(135deg, ${A.indigo}88, ${A.violet}66)`,
                    animation: isAISpeaking ? 'vc-pulse 1.2s ease-in-out infinite' : 'none',
                    transition: 'background 0.3s ease',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 22,
                  }}>
                    🎤
                  </div>
                </div>
                <p style={{ fontSize: 12, color: A.textSoft, margin: 0, fontWeight: 500 }}>
                  {isAISpeaking ? 'Speaking...' : 'Listening...'}
                </p>
                {/* Transcript — last thing AI said */}
                {transcript ? (
                  <p style={{
                    fontSize: 11, color: A.text, margin: 0, textAlign: 'center',
                    lineHeight: 1.5, fontStyle: 'italic', maxHeight: 60, overflow: 'hidden',
                    display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                  } as React.CSSProperties}>
                    "{transcript}"
                  </p>
                ) : (
                  <p style={{ fontSize: 11, color: A.textMuted, margin: 0, textAlign: 'center', lineHeight: 1.4 }}>
                    Ask anything about your brand strategy or content plan.
                  </p>
                )}
              </>
            )}

            {/* Error state */}
            {status === 'error' && (
              <>
                <div style={{
                  width: 52,
                  height: 52,
                  borderRadius: '50%',
                  background: A.coralLight,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 22,
                }}>
                  ⚠️
                </div>
                {error && (
                  <p style={{ fontSize: 11, color: A.coral, margin: 0, textAlign: 'center', lineHeight: 1.4 }}>
                    {error}
                  </p>
                )}
                <button
                  onClick={() => startSession(brandId, planId)}
                  style={{
                    padding: '7px 16px',
                    borderRadius: 8,
                    border: 'none',
                    background: `linear-gradient(135deg, ${A.violet}, ${A.indigo})`,
                    color: 'white',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Retry
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* L-2: Descriptive label shown only in idle state so users know what it does */}
      {status === 'idle' && (
        <p style={{
          fontSize: 10, color: A.textMuted, margin: 0,
          textAlign: 'center', lineHeight: 1.3,
        }}>
          Talk to your AI<br />brand strategist
        </p>
      )}

      {/* Floating pill button — always visible */}
      <VoicePill
        status={status}
        isAISpeaking={isAISpeaking}
        onStart={() => startSession(brandId, planId)}
        onStop={stopSession}
      />
    </div>
  )
}

interface PillProps {
  status: VoiceCoachStatus
  isAISpeaking: boolean
  onStart: () => void
  onStop: () => void
}

function VoicePill({ status, isAISpeaking, onStart, onStop }: PillProps) {
  if (status === 'idle') {
    return (
      <button
        onClick={onStart}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          padding: '9px 18px',
          borderRadius: 999,
          border: 'none',
          background: `linear-gradient(135deg, ${A.violet}, ${A.indigo})`,
          color: 'white',
          fontSize: 13,
          fontWeight: 600,
          cursor: 'pointer',
          boxShadow: '0 4px 16px rgba(139,92,246,0.35)',
          transition: 'transform 0.15s, box-shadow 0.15s',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.transform = 'translateY(-2px)'
          e.currentTarget.style.boxShadow = '0 6px 20px rgba(139,92,246,0.45)'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.transform = 'translateY(0)'
          e.currentTarget.style.boxShadow = '0 4px 16px rgba(139,92,246,0.35)'
        }}
        title="Start voice coaching session"
      >
        <span style={{ fontSize: 15 }}>🎤</span>
        Voice Coach
      </button>
    )
  }

  if (status === 'error') {
    return (
      <button
        onClick={onStop}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          padding: '9px 18px',
          borderRadius: 999,
          border: `1px solid ${A.coral}40`,
          background: A.coralLight,
          color: A.coral,
          fontSize: 13,
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: 15 }}>🎤</span>
        Voice Coach
      </button>
    )
  }

  // connecting or active — show an animated indicator
  return (
    <button
      onClick={onStop}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 7,
        padding: '9px 18px',
        borderRadius: 999,
        border: 'none',
        background: `linear-gradient(135deg, ${A.violet}, ${A.indigo})`,
        color: 'white',
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
        boxShadow: '0 4px 16px rgba(139,92,246,0.35)',
        opacity: isAISpeaking ? 1 : 0.85,
        animation: isAISpeaking ? 'vc-pulse 1.2s ease-in-out infinite' : 'none',
      }}
      title="Click to end session"
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: '#ff3b3b',
          display: 'inline-block',
          animation: status === 'active' ? 'vc-liveblink 1.2s ease-in-out infinite' : 'none',
          flexShrink: 0,
        }}
      />
      {status === 'connecting' ? 'Connecting...' : isAISpeaking ? 'Speaking...' : 'Listening...'}
    </button>
  )
}
