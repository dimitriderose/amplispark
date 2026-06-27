import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import {
  MdOutlineBolt,
  MdOutlineCalendarMonth,
  MdOutlineAutoAwesome,
  MdOutlinePalette,
  MdOutlineVideocam,
  MdOutlineVerified,
} from 'react-icons/md'
import { A } from '../theme'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api/client'

const FEATURES = [
  {
    Icon: MdOutlineBolt,
    color: A.indigo,
    title: 'Brand Analysis',
    desc: 'Describe your business in a few sentences. Optionally add your website URL for even deeper analysis.',
  },
  {
    Icon: MdOutlineCalendarMonth,
    color: A.violet,
    title: 'Event-Aware Calendar',
    desc: "Tell us what's happening this week. Launches, markets, specials — they become content pillars.",
  },
  {
    Icon: MdOutlineAutoAwesome,
    color: A.indigo,
    title: 'Captions & Images Together',
    desc: 'Every caption comes with a matching image, generated at the same time — no separate steps, no back and forth.',
  },
  {
    Icon: MdOutlinePalette,
    color: A.violet,
    title: 'Consistent Visual Style',
    desc: 'Define your look once. Every image we generate follows the same style, colors, and mood.',
  },
  {
    Icon: MdOutlineVideocam,
    color: A.indigo,
    title: 'Video Generation',
    desc: '8-second Reels and TikTok clips via Veo 3, using your hero image as the first frame.',
  },
  {
    Icon: MdOutlineVerified,
    color: A.violet,
    title: 'AI Brand Review',
    desc: 'Every post gets scored for brand alignment before it reaches your feed. One-click approval.',
  },
]

const STEPS = [
  {
    n: '01',
    title: 'Describe your brand',
    desc: 'Describe your business in a few sentences and optionally add your website. Amplispark builds your brand profile in seconds.',
  },
  {
    n: '02',
    title: 'Get your strategy',
    desc: "Tell us what's happening this week — launches, promotions, anything relevant. We'll plan a 7-day content calendar around it.",
  },
  {
    n: '03',
    title: 'Watch it generate',
    desc: 'Captions and matching images stream together in real time. Review, approve, and export in one click.',
  },
]

const PREVIEW_DAYS = [
  {
    platform: 'Instagram',
    pillar: 'Promotion',
    theme: 'New menu launch',
    anchor: '📅 Lavender croissant drop',
    color: '#E1306C',
  },
  {
    platform: 'LinkedIn',
    pillar: 'Education',
    theme: 'Behind the sourdough science',
    anchor: null,
    color: '#0A66C2',
  },
  {
    platform: 'Twitter/X',
    pillar: 'Inspiration',
    theme: 'Why we source locally',
    anchor: null,
    color: '#1A1A2E',
  },
]

type FormState = 'idle' | 'submitting' | 'success' | 'error'

function WaitlistForm({ inputId }: { inputId: string }) {
  const [email, setEmail] = useState('')
  const [state, setState] = useState<FormState>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)
    setState('submitting')
    try {
      await api.joinWaitlist(email)
      setState('success')
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
      setState('error')
    }
  }

  if (state === 'success') {
    return (
      <div style={{
        padding: '14px 24px',
        borderRadius: 10,
        background: A.emeraldLight,
        border: `1px solid ${A.emerald}30`,
        color: A.emerald,
        fontSize: 15,
        fontWeight: 500,
        textAlign: 'center',
      }}>
        You're on the list! We'll be in touch.
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} style={{ width: '100%' }}>
      <div style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        justifyContent: 'center',
      }}>
        <input
          id={inputId}
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          disabled={state === 'submitting'}
          style={{
            flex: '1 1 240px',
            minWidth: 0,
            padding: '13px 16px',
            borderRadius: 10,
            border: `1px solid ${A.border}`,
            fontSize: 15,
            color: A.text,
            background: A.bg,
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={state === 'submitting'}
          style={{
            flex: '0 0 auto',
            padding: '13px 28px',
            borderRadius: 10,
            border: 'none',
            cursor: state === 'submitting' ? 'not-allowed' : 'pointer',
            background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
            color: 'white',
            fontSize: 15,
            fontWeight: 600,
            opacity: state === 'submitting' ? 0.7 : 1,
            boxShadow: `0 4px 16px ${A.indigo}40`,
            whiteSpace: 'nowrap',
          }}
        >
          {state === 'submitting' ? 'Joining...' : 'Join Waitlist →'}
        </button>
      </div>
      {state === 'error' && errorMsg && (
        <p style={{ fontSize: 13, color: A.coral, marginTop: 8, textAlign: 'center' }}>{errorMsg}</p>
      )}
    </form>
  )
}

export default function LandingPage() {
  const { loading, isSignedIn, role, betaExpired } = useAuth()

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <p style={{ color: '#888', fontSize: 14 }}>Loading...</p>
    </div>
  )

  if (isSignedIn && role !== null && !betaExpired) return <Navigate to="/brands" replace />
  if (isSignedIn && betaExpired) return <Navigate to="/waitlist" replace />
  if (isSignedIn && role === null) return <Navigate to="/waitlist" replace />

  return (
    <div style={{ minHeight: '100vh', background: A.bg }}>

      <section style={{
        maxWidth: 860,
        margin: '0 auto',
        padding: '96px 24px 80px',
        textAlign: 'center',
      }}>
        <h1 style={{
          fontSize: 'clamp(36px, 6vw, 64px)',
          fontWeight: 800,
          color: A.text,
          lineHeight: 1.08,
          letterSpacing: -1.5,
          marginBottom: 24,
        }}>
          Your entire week of content.
          <br />
          <span style={{
            background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            One click.
          </span>
        </h1>

        <p style={{
          fontSize: 18,
          color: A.textSoft,
          maxWidth: 520,
          margin: '0 auto 40px',
          lineHeight: 1.65,
        }}>
          Amplispark learns your brand, builds your weekly content strategy, and generates captions and images together — ready to post in minutes.
        </p>

        <div style={{ maxWidth: 520, margin: '0 auto 20px' }}>
          <WaitlistForm inputId="hero-email" />
        </div>

        <button
          onClick={() => {
            document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })
          }}
          style={{
            padding: '14px 24px',
            borderRadius: 10,
            cursor: 'pointer',
            border: `1px solid ${A.border}`,
            background: 'transparent',
            color: A.textSoft,
            fontSize: 15,
          }}
        >
          See how it works ↓
        </button>
      </section>

      <section style={{
        borderTop: `1px solid ${A.border}`,
        borderBottom: `1px solid ${A.border}`,
        padding: '16px 24px',
      }}>
        <div style={{
          maxWidth: 700,
          margin: '0 auto',
          display: 'flex',
          justifyContent: 'center',
          gap: 32,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}>
          <span style={{
            fontSize: 12,
            color: A.textMuted,
            fontWeight: 500,
            letterSpacing: 0.5,
            textTransform: 'uppercase',
          }}>
            Generates content for
          </span>
          {[
            { label: 'Instagram', color: '#E1306C' },
            { label: 'LinkedIn', color: '#0A66C2' },
            { label: 'Twitter / X', color: '#1A1A2E' },
            { label: 'Facebook', color: '#1877F2' },
          ].map(p => (
            <span key={p.label} style={{
              fontSize: 13,
              fontWeight: 600,
              color: p.color,
              padding: '4px 12px',
              borderRadius: 20,
              border: `1px solid ${p.color}30`,
              background: p.color + '12',
            }}>
              {p.label}
            </span>
          ))}
        </div>
      </section>

      <section id="how-it-works" style={{ maxWidth: 960, margin: '0 auto', padding: '80px 24px' }}>
        <h2 style={{
          fontSize: 28,
          fontWeight: 700,
          color: A.text,
          textAlign: 'center',
          marginBottom: 8,
        }}>
          How it works
        </h2>
        <p style={{
          fontSize: 15,
          color: A.textSoft,
          textAlign: 'center',
          marginBottom: 48,
        }}>
          From zero to a week of brand-consistent content in under 3 minutes.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 24 }}>
          {STEPS.map(({ n, title, desc }) => (
            <div key={n} style={{
              padding: 28,
              borderRadius: 14,
              background: A.surface,
              border: `1px solid ${A.border}`,
            }}>
              <div style={{
                fontSize: 32,
                fontWeight: 800,
                color: A.indigo,
                opacity: 0.25,
                marginBottom: 16,
                letterSpacing: -1,
              }}>
                {n}
              </div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: A.text, marginBottom: 10 }}>{title}</h3>
              <p style={{ fontSize: 14, color: A.textSoft, lineHeight: 1.6 }}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section style={{ maxWidth: 960, margin: '0 auto', padding: '0 24px 80px' }}>
        <div style={{
          borderRadius: 16,
          border: `1px solid ${A.border}`,
          overflow: 'hidden',
          background: A.surface,
        }}>
          <div style={{
            padding: '12px 16px',
            borderBottom: `1px solid ${A.border}`,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FF5F57' }} />
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FFBD2E' }} />
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#28C840' }} />
            <span style={{ marginLeft: 12, fontSize: 12, color: A.textMuted }}>
              amplispark.io — Content Calendar
            </span>
          </div>
          <div style={{ padding: 24, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
            {PREVIEW_DAYS.map((d, i) => (
              <div key={d.platform} style={{
                borderRadius: 10,
                border: `1px solid ${A.border}`,
                overflow: 'hidden',
              }}>
                <div style={{ height: 4, background: d.color }} />
                <div style={{ padding: 14 }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                  }}>
                    <span style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'white',
                      background: d.color,
                      padding: '2px 8px',
                      borderRadius: 10,
                    }}>
                      {d.platform}
                    </span>
                    <span style={{ fontSize: 11, color: A.textMuted }}>Day {i + 1}</span>
                  </div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: A.text, marginBottom: 6 }}>
                    {d.theme}
                  </p>
                  <span style={{
                    fontSize: 11,
                    color: A.textMuted,
                    background: A.surfaceAlt,
                    padding: '2px 8px',
                    borderRadius: 10,
                  }}>
                    {d.pillar}
                  </span>
                  {d.anchor && (
                    <div style={{
                      marginTop: 8,
                      fontSize: 10,
                      color: A.amber,
                      background: A.amber + '15',
                      padding: '3px 8px',
                      borderRadius: 8,
                      border: `1px solid ${A.amber}30`,
                    }}>
                      {d.anchor}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section style={{ maxWidth: 960, margin: '0 auto', padding: '0 24px 80px' }}>
        <h2 style={{
          fontSize: 28,
          fontWeight: 700,
          color: A.text,
          textAlign: 'center',
          marginBottom: 8,
        }}>
          Everything your content needs
        </h2>
        <p style={{
          fontSize: 15,
          color: A.textSoft,
          textAlign: 'center',
          marginBottom: 48,
        }}>
          Six capabilities working together to make every post feel hand-crafted.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 20 }}>
          {FEATURES.map(({ Icon, color, title, desc }) => (
            <div key={title} style={{
              padding: 24,
              borderRadius: 12,
              background: A.surface,
              border: `1px solid ${A.border}`,
            }}>
              <Icon size={32} color={color} style={{ marginBottom: 12 }} />
              <h3 style={{ fontSize: 15, fontWeight: 700, color: A.text, marginBottom: 8 }}>{title}</h3>
              <p style={{ fontSize: 13, color: A.textSoft, lineHeight: 1.6 }}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <footer style={{
        borderTop: `1px solid ${A.border}`,
        padding: '24px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 24,
        flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: 12, color: A.textMuted }}>
          © 2026 Amplispark
        </span>
        <a href="/terms" style={{ fontSize: 12, color: A.textSoft, textDecoration: 'none' }}
           onMouseEnter={e => (e.currentTarget.style.color = A.indigo)}
           onMouseLeave={e => (e.currentTarget.style.color = A.textSoft)}>
          Terms of Service
        </a>
        <a href="/privacy" style={{ fontSize: 12, color: A.textSoft, textDecoration: 'none' }}
           onMouseEnter={e => (e.currentTarget.style.color = A.indigo)}
           onMouseLeave={e => (e.currentTarget.style.color = A.textSoft)}>
          Privacy Policy
        </a>
      </footer>

    </div>
  )
}
