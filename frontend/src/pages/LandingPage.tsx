import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api/client'

function AccountDropdown({ user, onSignOut }: {
  user: { displayName: string | null; photoURL: string | null; email: string | null }
  onSignOut: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 12px', borderRadius: 10,
          border: `1px solid ${A.border}`, background: A.surface,
          cursor: 'pointer', fontSize: 13, fontWeight: 500, color: A.text,
        }}
      >
        {user.photoURL ? (
          <img src={user.photoURL} alt="" style={{ width: 24, height: 24, borderRadius: '50%' }} />
        ) : (
          <div style={{
            width: 24, height: 24, borderRadius: '50%',
            background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'white', fontSize: 11, fontWeight: 700,
          }}>
            {(user.displayName || user.email || '?')[0].toUpperCase()}
          </div>
        )}
        {user.displayName || 'Account'}
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0, top: '100%', marginTop: 6,
          background: A.surface, border: `1px solid ${A.border}`,
          borderRadius: 12, padding: 12, minWidth: 200,
          boxShadow: '0 8px 32px rgba(0,0,0,0.12)', zIndex: 100,
        }}>
          {user.email && (
            <div style={{ fontSize: 12, color: A.textMuted, marginBottom: 10, padding: '0 4px' }}>
              {user.email}
            </div>
          )}
          <button
            onClick={() => { setOpen(false); onSignOut() }}
            style={{
              width: '100%', padding: '8px 12px', borderRadius: 8,
              border: 'none', background: 'transparent', cursor: 'pointer',
              fontSize: 13, fontWeight: 500, color: A.text, textAlign: 'left',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = A.surfaceAlt)}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  )
}

interface BrandSummary {
  brand_id: string
  business_name?: string
  industry?: string
  analysis_status?: string
  description?: string
}

const FEATURES = [
  {
    icon: '🔍',
    title: 'Brand Analysis',
    // L-1: URL field is optional/collapsible — primary action is describing your business
    desc: 'Describe your business in a few sentences. Optionally add your website URL for even deeper analysis.',
  },
  {
    icon: '📅',
    title: 'Event-Aware Calendar',
    desc: "Tell us what's happening this week. Launches, markets, specials — they become content pillars.",
  },
  {
    icon: '✨',
    title: 'Interleaved Generation',
    desc: "Captions and matching images stream together in real time using Gemini's unique multimodal output.",
  },
  {
    icon: '🎨',
    title: 'Visual Identity Seed',
    desc: 'A 2–3 sentence style directive ensures every generated image shares the same visual DNA.',
  },
  {
    icon: '🎬',
    title: 'Video Generation',
    desc: '8-second Reels and TikTok clips via Veo 3, using your hero image as the first frame.',
  },
  {
    icon: '✓',
    title: 'AI Brand Review',
    desc: 'Every post gets scored for brand alignment before it reaches your feed. One-click approval.',
  },
]

const STEPS = [
  {
    n: '01',
    title: 'Describe your brand',
    // L-1: URL is optional/collapsible — description is the primary action
    desc: 'Describe your business in a few sentences. Optionally add your website URL for deeper analysis. The Brand Analyst builds your complete profile in 30 seconds.',
  },
  {
    n: '02',
    title: 'Get your strategy',
    desc: "Add this week's events. The Strategy Agent plans a 7-day content calendar with platform-specific pillars.",
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

export default function LandingPage() {
  const navigate = useNavigate()
  const { uid, user, isSignedIn, signIn, signOut } = useAuth()
  const [myBrands, setMyBrands] = useState<BrandSummary[]>([])

  // Fetch user's brands once UID is available
  useEffect(() => {
    if (!uid) return
    api.listBrands(uid)
      .then((res) => setMyBrands((res as unknown as { brands: BrandSummary[] }).brands || []))
      .catch(() => {})
  }, [uid])

  const handleAction = async () => {
    if (!isSignedIn) {
      try {
        await signIn()
      } catch {
        return // user closed popup
      }
    }
    navigate('/onboard')
  }

  const hasBrands = myBrands.length > 0

  return (
    <div style={{ minHeight: '100vh', background: A.bg }}>

      {/* ── Header ── */}
      <header style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 24px', maxWidth: 960, margin: '0 auto',
      }}>
        <span style={{ fontSize: 18, fontWeight: 800, color: A.text, letterSpacing: -0.5 }}>
          Amplifi
        </span>
        {isSignedIn && user ? (
          <AccountDropdown user={user} onSignOut={signOut} />
        ) : (
          <button
            onClick={signIn}
            style={{
              padding: '6px 16px', borderRadius: 8,
              border: `1px solid ${A.border}`, background: 'transparent',
              cursor: 'pointer', fontSize: 13, fontWeight: 500, color: A.text,
            }}
          >
            Sign in
          </button>
        )}
      </header>

      {/* ── Welcome-back banner (returning users only) ── */}
      {hasBrands && (
        <div style={{
          borderBottom: `1px solid ${A.border}`,
          background: A.indigoLight,
          padding: '10px 24px',
        }}>
          <div style={{
            maxWidth: 860,
            margin: '0 auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}>
            <span style={{ fontSize: 13, color: A.indigo, fontWeight: 500 }}>
              Welcome back — pick up where you left off
            </span>
            <button
              onClick={() => navigate(`/dashboard/${myBrands[0].brand_id}`)}
              style={{
                padding: '5px 14px',
                borderRadius: 8,
                border: 'none',
                background: A.indigo,
                color: 'white',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Open {myBrands[0].business_name || 'Dashboard'} →
            </button>
          </div>
        </div>
      )}

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section style={{
        maxWidth: 860,
        margin: '0 auto',
        padding: hasBrands ? '48px 24px 48px' : '96px 24px 80px',
        textAlign: 'center',
      }}>
        {/* Badge */}
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 14px',
          borderRadius: 20,
          border: `1px solid ${A.indigo}40`,
          background: A.indigoLight,
          fontSize: 12,
          fontWeight: 600,
          color: A.indigo,
          marginBottom: hasBrands ? 20 : 28,
          letterSpacing: 0.3,
        }}>
          ✨ Built for Google's Gemini API Developer Competition
        </div>

        <h1 style={{
          fontSize: hasBrands ? 'clamp(28px, 5vw, 48px)' : 'clamp(36px, 6vw, 64px)',
          fontWeight: 800,
          color: A.text,
          lineHeight: 1.08,
          letterSpacing: -1.5,
          marginBottom: hasBrands ? 16 : 24,
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

        {!hasBrands && (
          <p style={{
            fontSize: 18,
            color: A.textSoft,
            maxWidth: 520,
            margin: '0 auto 40px',
            lineHeight: 1.65,
          }}>
            Amplifi analyzes your brand, plans your strategy, and streams captions &amp; images
            together in real time — powered by Gemini 2.5 Flash's interleaved multimodal output.
          </p>
        )}

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={handleAction}
            style={{
              padding: hasBrands ? '12px 28px' : '14px 32px',
              borderRadius: 10,
              border: 'none',
              cursor: 'pointer',
              background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
              color: 'white',
              fontSize: hasBrands ? 14 : 16,
              fontWeight: 600,
              boxShadow: `0 8px 32px ${A.indigo}40`,
            }}
          >
            {hasBrands ? '+ New Brand' : 'Build My Brand Profile →'}
          </button>
          {!hasBrands && (
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
          )}
        </div>
      </section>

      {/* ── Your Brands (below hero for returning users) ── */}
      {hasBrands && (
        <section style={{
          maxWidth: 860,
          margin: '0 auto',
          padding: '0 24px 48px',
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: A.textSoft, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Your Brands
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {myBrands.map((b) => (
              <button
                key={b.brand_id}
                onClick={() => navigate(`/dashboard/${b.brand_id}`)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '14px 16px',
                  borderRadius: 12,
                  border: `1px solid ${A.border}`,
                  background: A.surface,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'border-color 0.15s, box-shadow 0.15s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = A.indigo + '50'
                  e.currentTarget.style.boxShadow = `0 2px 12px ${A.indigo}15`
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = A.border
                  e.currentTarget.style.boxShadow = 'none'
                }}
              >
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: 17,
                  fontWeight: 700,
                  flexShrink: 0,
                }}>
                  {(b.business_name || b.description || '?')[0].toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: A.text }}>
                    {b.business_name || b.description?.slice(0, 40) || 'Untitled Brand'}
                  </div>
                  {b.industry && (
                    <div style={{ fontSize: 12, color: A.textMuted, marginTop: 2 }}>
                      {b.industry}
                    </div>
                  )}
                </div>
                <span style={{
                  fontSize: 11,
                  fontWeight: 500,
                  color: b.analysis_status === 'complete' ? A.emerald : A.amber,
                  padding: '3px 10px',
                  borderRadius: 10,
                  background: (b.analysis_status === 'complete' ? A.emerald : A.amber) + '15',
                }}>
                  {b.analysis_status === 'complete' ? 'Ready' : b.analysis_status || 'Pending'}
                </span>
                <span style={{ color: A.textMuted, fontSize: 16 }}>&rarr;</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Platform strip ───────────────────────────────────── */}
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

      {/* ── How it works ─────────────────────────────────────── */}
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

      {/* ── Live preview mockup ───────────────────────────────── */}
      <section style={{ maxWidth: 960, margin: '0 auto', padding: '0 24px 80px' }}>
        <div style={{
          borderRadius: 16,
          border: `1px solid ${A.border}`,
          overflow: 'hidden',
          background: A.surface,
        }}>
          {/* Mock toolbar */}
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
              amplifi.app — Content Calendar
            </span>
          </div>
          {/* Mini calendar cards */}
          <div style={{ padding: 24, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
            {PREVIEW_DAYS.map((d, i) => (
              <div key={i} style={{
                borderRadius: 10,
                border: `1px solid ${A.border}`,
                overflow: 'hidden',
              }}>
                {/* Color bar */}
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

      {/* ── Feature grid ─────────────────────────────────────── */}
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
          {FEATURES.map(({ icon, title, desc }) => (
            <div key={title} style={{
              padding: 24,
              borderRadius: 12,
              background: A.surface,
              border: `1px solid ${A.border}`,
            }}>
              <div style={{ fontSize: 28, marginBottom: 12 }}>{icon}</div>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: A.text, marginBottom: 8 }}>{title}</h3>
              <p style={{ fontSize: 13, color: A.textSoft, lineHeight: 1.6 }}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Final CTA ────────────────────────────────────────── */}
      <section style={{
        borderTop: `1px solid ${A.border}`,
        padding: hasBrands ? '48px 24px' : '80px 24px',
        textAlign: 'center',
      }}>
        <h2 style={{ fontSize: hasBrands ? 24 : 32, fontWeight: 700, color: A.text, marginBottom: 16 }}>
          {hasBrands ? 'Add another brand' : "Ready to see your brand's content?"}
        </h2>
        <p style={{
          fontSize: hasBrands ? 14 : 16,
          color: A.textSoft,
          marginBottom: 32,
          maxWidth: 400,
          margin: '0 auto 32px',
        }}>
          {hasBrands
            ? 'Each brand gets its own AI-powered content strategy and calendar.'
            : 'Sign in with Google, describe your business, and watch the magic.'}
        </p>
        <button
          onClick={handleAction}
          style={{
            padding: hasBrands ? '12px 32px' : '16px 40px',
            borderRadius: 10,
            border: 'none',
            cursor: 'pointer',
            background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
            color: 'white',
            fontSize: hasBrands ? 15 : 17,
            fontWeight: 700,
            boxShadow: `0 8px 40px ${A.indigo}50`,
          }}
        >
          {hasBrands ? '+ New Brand' : 'Get Started Free →'}
        </button>
        <p style={{ fontSize: 12, color: A.textMuted, marginTop: 16 }}>
          Powered by Gemini 2.5 Flash · Google Cloud
        </p>
      </section>

      {/* ── Footer ─────────────────────────────────────────── */}
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
          © 2026 Amplifi
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
