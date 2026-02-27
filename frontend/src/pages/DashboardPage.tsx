import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { A } from '../theme'
import { useBrandProfile } from '../hooks/useBrandProfile'
import { useContentPlan } from '../hooks/useContentPlan'
import { usePostLibrary } from '../hooks/usePostLibrary'
import BrandProfileCard from '../components/BrandProfileCard'
import ContentCalendar from '../components/ContentCalendar'
import PostLibrary from '../components/PostLibrary'
import EventsInput from '../components/EventsInput'
import VoiceCoach from '../components/VoiceCoach'
import SocialConnect from '../components/SocialConnect'
import VideoRepurpose from '../components/VideoRepurpose'

type Tab = 'calendar' | 'posts' | 'export'

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'calendar', label: 'Calendar', icon: '📅' },
  { key: 'posts', label: 'Posts', icon: '📝' },
  { key: 'export', label: 'Export', icon: '📦' },
]

export default function DashboardPage() {
  const { brandId } = useParams<{ brandId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { brand, loading: brandLoading, error: brandError, updateBrand } = useBrandProfile(brandId)
  const { plan, generating, error: planError, generatePlan, setDayCustomPhoto, clearPlan } = useContentPlan(brandId ?? '')
  const { posts: calendarPosts } = usePostLibrary(brandId ?? '', plan?.plan_id)
  const [activeTab, setActiveTab] = useState<Tab>('calendar')

  // H-8: Store planId in sessionStorage so NavBar can include it in the Export link.
  useEffect(() => {
    if (plan?.plan_id && brandId) {
      sessionStorage.setItem(`amplifi_plan_${brandId}`, plan.plan_id)
    } else if (brandId) {
      sessionStorage.removeItem(`amplifi_plan_${brandId}`)
    }
  }, [plan?.plan_id, brandId])

  // Persist brandId to localStorage so grandfathering can claim it on next visit
  useEffect(() => {
    if (!brandId) return
    try {
      const stored: string[] = JSON.parse(localStorage.getItem('amplifi_brand_ids') || '[]')
      if (!stored.includes(brandId)) {
        stored.push(brandId)
        localStorage.setItem('amplifi_brand_ids', JSON.stringify(stored))
      }
    } catch { /* localStorage unavailable */ }
  }, [brandId])

  const approvedParam = searchParams.get('approved')
  const approvedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (approvedParam) {
      if (approvedTimerRef.current) clearTimeout(approvedTimerRef.current)
      approvedTimerRef.current = setTimeout(() => {
        setSearchParams(prev => {
          const next = new URLSearchParams(prev)
          next.delete('approved')
          return next
        }, { replace: true })
      }, 4000)
    }
    return () => {
      if (approvedTimerRef.current) clearTimeout(approvedTimerRef.current)
    }
  }, [approvedParam, setSearchParams])

  if (brandLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
        <p style={{ color: A.textSoft }}>Loading brand profile...</p>
      </div>
    )
  }

  if (brandError) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <p style={{ color: A.coral, marginBottom: 16 }}>{brandError}</p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '8px 16px', borderRadius: 8,
              background: A.indigo, color: 'white', border: 'none', cursor: 'pointer',
            }}
          >
            Retry
          </button>
          <button
            onClick={() => navigate('/onboard')}
            style={{
              padding: '8px 16px', borderRadius: 8, border: `1px solid ${A.border}`,
              background: 'transparent', cursor: 'pointer', fontSize: 13, color: A.textSoft,
            }}
          >
            Start Over
          </button>
        </div>
      </div>
    )
  }

  if (!brand) return null

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>
      {/* Approved success banner */}
      {approvedParam && (
        <div style={{
          marginBottom: 20, padding: '10px 16px', borderRadius: 8,
          background: A.emeraldLight, border: `1px solid ${A.emerald}44`,
          color: A.emerald, fontSize: 13, fontWeight: 500,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span>Post approved and ready for export</span>
          <button
            onClick={() => {
              const next = new URLSearchParams(searchParams)
              next.delete('approved')
              setSearchParams(next, { replace: true })
            }}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: A.emerald, fontSize: 16, lineHeight: 1, padding: '0 4px',
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: A.text, marginBottom: 4 }}>
            {brand.business_name || 'Your Brand'} — Dashboard
          </h1>
          <p style={{ fontSize: 14, color: A.textSoft }}>
            Manage your brand profile and content calendar
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => navigate(`/edit/${brandId}`)}
            style={{
              padding: '8px 16px', borderRadius: 8, border: `1px solid ${A.indigo}40`,
              background: A.indigoLight, cursor: 'pointer', fontSize: 13, color: A.indigo,
              fontWeight: 500,
            }}
          >
            Edit Brand
          </button>
          <button
            onClick={() => navigate('/onboard')}
            style={{
              padding: '8px 16px', borderRadius: 8, border: `1px solid ${A.border}`,
              background: 'transparent', cursor: 'pointer', fontSize: 13, color: A.textSoft,
            }}
          >
            + New Brand
          </button>
        </div>
      </div>

      {/* 1:2 grid layout — left: brand card, right: tabbed content */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 24, alignItems: 'start' }}>
        {/* Left column: Brand Profile Card + Social Connect + Video Repurpose */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <BrandProfileCard brand={brand} onUpdate={updateBrand} />
          <div style={{ padding: 20, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
            <SocialConnect
              brandId={brandId ?? ''}
              connectedPlatforms={brand.connected_platforms ?? []}
              existingVoiceAnalyses={brand.social_voice_analyses}
              existingVoiceAnalysis={brand.social_voice_analysis}
              existingVoicePlatform={brand.social_voice_platform}
            />
          </div>
          <div style={{ padding: 20, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
            <VideoRepurpose brandId={brandId ?? ''} />
          </div>
        </div>

        {/* Right column: Tab bar + tab content */}
        <div>
          {/* Tab bar */}
          <div style={{
            display: 'flex', gap: 2,
            marginBottom: 16,
            background: A.surfaceAlt,
            borderRadius: 10,
            padding: 3,
          }}>
            {TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: activeTab === tab.key ? 600 : 400,
                  background: activeTab === tab.key ? A.surface : 'transparent',
                  color: activeTab === tab.key ? A.text : A.textSoft,
                  boxShadow: activeTab === tab.key ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                  transition: 'all 0.15s',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                }}
              >
                <span style={{ fontSize: 14 }}>{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>

          {/* ── Calendar Tab ─────────────────────────────────── */}
          {activeTab === 'calendar' && (
            plan ? (
              <div style={{ padding: 24, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                  <button
                    onClick={() => {
                      if (window.confirm('This will clear your current plan. Are you sure?')) {
                        clearPlan()
                      }
                    }}
                    style={{
                      padding: '4px 12px', borderRadius: 6, border: `1px solid ${A.border}`,
                      background: 'transparent', color: A.textSoft, fontSize: 12, cursor: 'pointer',
                    }}
                  >
                    New Plan
                  </button>
                </div>
                <ContentCalendar
                  plan={{ plan_id: plan.plan_id, days: plan.days }}
                  brandId={brandId ?? ''}
                  posts={calendarPosts}
                  onGeneratePost={(planId, dayIndex) =>
                    navigate(`/generate/${planId}/${dayIndex}?brand_id=${brandId ?? ''}`)
                  }
                  onViewPost={(planId, dayIndex, postId) =>
                    navigate(`/generate/${planId}/${dayIndex}?brand_id=${brandId ?? ''}&post_id=${postId}`)
                  }
                  onPhotoUploaded={(dayIndex, photoUrl) =>
                    setDayCustomPhoto(plan.plan_id, dayIndex, photoUrl)
                  }
                />
              </div>
            ) : (
              <div style={{ padding: 24, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
                {planError && (
                  <p style={{ fontSize: 13, color: A.coral, marginBottom: 12 }}>
                    {planError}
                  </p>
                )}
                <EventsInput
                  onGenerate={(events) => generatePlan(7, events || undefined)}
                  generating={generating}
                  analysisStatus={brand.analysis_status}
                />
              </div>
            )
          )}

          {/* ── Posts Tab ─────────────────────────────────────── */}
          {activeTab === 'posts' && (
            <div style={{ padding: 24, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
              {plan && brandId ? (
                <PostLibrary brandId={brandId} planId={plan.plan_id} />
              ) : (
                <div style={{
                  padding: 40, textAlign: 'center',
                  color: A.textMuted, fontSize: 13,
                }}>
                  Generate a content plan first to see your posts here.
                </div>
              )}
            </div>
          )}

          {/* ── Export Tab ────────────────────────────────────── */}
          {activeTab === 'export' && (
            <div style={{ padding: 24, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
              {plan && brandId ? (
                <>
                  <div style={{
                    marginBottom: 16, padding: '12px 16px', borderRadius: 10,
                    background: `linear-gradient(135deg, ${A.indigo}10, ${A.violet}08)`,
                    border: `1px solid ${A.indigo}20`,
                    display: 'flex', alignItems: 'center', gap: 12,
                  }}>
                    <span style={{ fontSize: 20 }}>📦</span>
                    <div>
                      <p style={{ fontSize: 13, fontWeight: 600, color: A.text, margin: 0 }}>
                        Plan ZIP export available
                      </p>
                      <p style={{ fontSize: 12, color: A.textSoft, margin: 0 }}>
                        Use "Export All" to download all approved posts as a ZIP with captions and images.
                      </p>
                    </div>
                  </div>
                  <PostLibrary brandId={brandId} planId={plan.plan_id} defaultFilter="approved" />
                </>
              ) : (
                <div style={{
                  padding: 40, textAlign: 'center',
                  color: A.textMuted, fontSize: 13,
                }}>
                  Generate a content plan first to export your posts.
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Voice Brand Coach — floating button, fixed position */}
      {brandId && (
        <VoiceCoach brandId={brandId} brandName={brand.business_name} />
      )}
    </div>
  )
}
