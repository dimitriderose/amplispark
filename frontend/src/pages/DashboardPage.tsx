import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { A } from '../theme'
import { api } from '../api/client'
import { useBrandProfile } from '../hooks/useBrandProfile'
import { useContentPlan } from '../hooks/useContentPlan'
import { usePostLibrary } from '../hooks/usePostLibrary'
import BrandSummaryBar from '../components/BrandSummaryBar'
import ContentCalendar from '../components/ContentCalendar'
import PostLibrary from '../components/PostLibrary'
import PostHistory from '../components/PostHistory'
import EventsInput from '../components/EventsInput'
import VoiceCoach from '../components/VoiceCoach'
import SocialConnect from '../components/SocialConnect'
import IntegrationConnect from '../components/IntegrationConnect'
import VideoRepurpose from '../components/VideoRepurpose'
import Spinner from '../components/Spinner'
import { useIsMobile, useIsTablet } from '../hooks/useIsMobile'

type Tab = 'calendar' | 'posts' | 'connections' | 'video'

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'calendar', label: 'Calendar', icon: '📅' },
  { key: 'posts', label: 'Posts', icon: '📝' },
  { key: 'connections', label: 'Connections', icon: '🔗' },
  { key: 'video', label: 'Video', icon: '🎬' },
]

export default function DashboardPage() {
  const isMobile = useIsMobile()
  const isTablet = useIsTablet()
  const { brandId } = useParams<{ brandId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { brand, loading: brandLoading, error: brandError, updateBrand: _updateBrand, refetch: refetchBrand } = useBrandProfile(brandId)
  const { plan, loading: planLoading, generating, error: planError, generatePlan, setDayCustomPhoto, clearPlan } = useContentPlan(brandId ?? '')
  const { posts: calendarPosts } = usePostLibrary(brandId ?? '', plan?.plan_id)
  const [activeTab, setActiveTab] = useState<Tab>('calendar')
  const [postsSubTab, setPostsSubTab] = useState<'weekly' | 'history'>('weekly')
  const [trendSummaryOverride, setTrendSummaryOverride] = useState<any | null>(null)

  const handleRefreshResearch = async () => {
    if (!brandId || !plan?.plan_id) return
    try {
      const result = await api.refreshPlanResearch(brandId, plan.plan_id) as any
      if (result?.trend_summary) {
        setTrendSummaryOverride(result.trend_summary)
      }
    } catch (err) {
      // Silently fail — research is optional enhancement
    }
  }

  const activeTrendSummary = trendSummaryOverride ?? plan?.trend_summary

  // H-8: Store planId in sessionStorage so NavBar can include it in the Export link.
  useEffect(() => {
    if (plan?.plan_id && brandId) {
      sessionStorage.setItem(`amplifi_plan_${brandId}`, plan.plan_id)
      sessionStorage.setItem(`amplifi_brandname_${brandId}`, brand?.business_name || '')
    } else if (brandId) {
      sessionStorage.removeItem(`amplifi_plan_${brandId}`)
    }
  }, [plan?.plan_id, brandId])

  const approvedParam = searchParams.get('approved')
  const notionParam = searchParams.get('notion')
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

  // Auto-dismiss Notion connected banner
  useEffect(() => {
    if (notionParam) {
      const timer = setTimeout(() => {
        setSearchParams(prev => {
          const next = new URLSearchParams(prev)
          next.delete('notion')
          return next
        }, { replace: true })
      }, 4000)
      return () => clearTimeout(timer)
    }
  }, [notionParam, setSearchParams])

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
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: isMobile ? '16px 12px' : isTablet ? '20px 16px' : '32px 24px' }}>
      {/* Notion connected banner */}
      {notionParam === 'connected' && (
        <div style={{
          marginBottom: 20, padding: '10px 16px', borderRadius: 8,
          background: A.emeraldLight, border: `1px solid ${A.emerald}44`,
          color: A.emerald, fontSize: 13, fontWeight: 500,
        }}>
          Notion connected — select a database to start exporting your content calendar.
        </div>
      )}

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

      {/* Brand Summary Bar */}
      <BrandSummaryBar
        brand={brand}
        onNavigateEdit={() => navigate(`/edit/${brandId}`)}
        onNavigateNew={() => navigate('/onboard')}
      />

      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: 2,
        marginBottom: 20,
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
              padding: '9px 12px',
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
      {activeTab === 'calendar' && planLoading && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 10 }}>
          <Spinner size={18} />
          <span style={{ fontSize: 13, color: A.textSoft }}>Loading calendar...</span>
        </div>
      )}
      {activeTab === 'calendar' && !planLoading && (
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
              defaultImageStyle={brand?.default_image_style}
              onGeneratePost={(planId, dayIndex, imageStyle) => {
                const styleParam = imageStyle ? `&image_style=${encodeURIComponent(imageStyle)}` : ''
                navigate(`/generate/${planId}/${dayIndex}?brand_id=${brandId ?? ''}${styleParam}`)
              }}
              onViewPost={(planId, dayIndex, postId) =>
                navigate(`/generate/${planId}/${dayIndex}?brand_id=${brandId ?? ''}&post_id=${postId}`)
              }
              onPhotoUploaded={(dayIndex, photoUrl) =>
                setDayCustomPhoto(plan.plan_id, dayIndex, photoUrl)
              }
              trendSummary={activeTrendSummary}
              onRefreshResearch={handleRefreshResearch}
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
              onGenerate={(events) => {
                const platforms = brand.platform_mode === 'manual' && brand.selected_platforms?.length
                  ? brand.selected_platforms
                  : undefined
                generatePlan(7, events || undefined, platforms)
              }}
              generating={generating}
              analysisStatus={brand.analysis_status}
            />
          </div>
        )
      )}

      {/* ── Posts Tab ─────────────────────────────────────── */}
      {activeTab === 'posts' && (
        <div style={{ borderRadius: 12, background: A.surface, border: `1px solid ${A.border}`, overflow: 'hidden' }}>
          {/* Sub-tabs: Weekly / History */}
          <div style={{ display: 'flex', borderBottom: `1px solid ${A.border}` }}>
            {(['weekly', 'history'] as const).map(sub => (
              <button
                key={sub}
                onClick={() => setPostsSubTab(sub)}
                style={{
                  flex: 1, padding: '10px 0', border: 'none', cursor: 'pointer',
                  fontSize: 13, fontWeight: postsSubTab === sub ? 600 : 400,
                  color: postsSubTab === sub ? A.indigo : A.textSoft,
                  background: postsSubTab === sub ? A.indigoLight : 'transparent',
                  borderBottom: postsSubTab === sub ? `2px solid ${A.indigo}` : '2px solid transparent',
                }}
              >
                {sub === 'weekly' ? 'Weekly Plan' : 'All History'}
              </button>
            ))}
          </div>
          <div style={{ padding: 24 }}>
            {postsSubTab === 'weekly' ? (
              plan && brandId ? (
                <PostLibrary brandId={brandId} planId={plan.plan_id} notionReady={!!brand.integrations?.notion?.database_id} />
              ) : (
                <div style={{ padding: 40, textAlign: 'center', color: A.textMuted, fontSize: 13 }}>
                  Generate a content plan first to see your posts here.
                </div>
              )
            ) : (
              brandId ? (
                <PostHistory brandId={brandId} />
              ) : null
            )}
          </div>
        </div>
      )}

      {/* ── Connections Tab ────────────────────────────────── */}
      {activeTab === 'connections' && (
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 20, alignItems: 'start' }}>
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
            <IntegrationConnect
              brandId={brandId ?? ''}
              notion={brand.integrations?.notion}
              onUpdate={refetchBrand}
            />
          </div>
        </div>
      )}

      {/* ── Video Tab ──────────────────────────────────────── */}
      {activeTab === 'video' && (
        <div style={{
          padding: 24, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}`,
          maxWidth: 640,
        }}>
          <VideoRepurpose brandId={brandId ?? ''} />
        </div>
      )}

      {/* Voice Brand Coach — floating button, fixed position */}
      {brandId && (
        <VoiceCoach brandId={brandId} brandName={brand.business_name} planId={plan?.plan_id} />
      )}
    </div>
  )
}
