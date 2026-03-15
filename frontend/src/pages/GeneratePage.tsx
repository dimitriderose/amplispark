import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { usePostGeneration } from '../hooks/usePostGeneration'
import { api } from '../api/client'
import PostGenerator from '../components/PostGenerator'
import ReviewPanel from '../components/ReviewPanel'
import EditMediaSection from '../components/EditMediaSection'
import PageContainer from '../components/ui/PageContainer'

export default function GeneratePage() {
  const { planId, dayIndex } = useParams<{ planId: string; dayIndex: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const brandId = searchParams.get('brand_id') || ''
  const viewPostId = searchParams.get('post_id') || ''
  const imageStyle = searchParams.get('image_style') || ''

  const { state, generate, reset, loadExisting } = usePostGeneration()

  const [dayBrief, setDayBrief] = useState<{ platform: string; pillar: string; content_theme: string; day_index?: number; derivative_type?: string } | undefined>(undefined)
  const [planDayCount, setPlanDayCount] = useState<number>(0)
  const [byopRecommendation, setByopRecommendation] = useState<string | undefined>(undefined)
  const [reviewKey, setReviewKey] = useState(0)
  const hasRegenerated = useRef(false)
  const generatedRef = useRef(false)
  // Local overrides for edited image URLs (post-edit)
  const [editedImageUrl, setEditedImageUrl] = useState<string | null>(null)
  const [editedEditCount, setEditedEditCount] = useState<number>(0)
  const [editedVideoCount, setEditedVideoCount] = useState<number>(0)

  // Load the day brief so PostGenerator knows the platform (needed for video button eligibility)
  useEffect(() => {
    if (!planId || dayIndex === undefined || !brandId) return
    api.getPlan(brandId, planId)
      .then(res => {
        const days = res.plan_profile?.days || []
        setPlanDayCount(days.length)
        const idx = parseInt(dayIndex, 10)
        if (days[idx]) setDayBrief(days[idx])
      })
      .catch(() => {})
  }, [planId, dayIndex, brandId])

  // Fetch brand to get image quality risk recommendation
  useEffect(() => {
    if (!brandId) return
    api.getBrand(brandId)
      .then(res => {
        const brand = res.brand_profile as Record<string, unknown>
        if (brand.image_generation_risk === 'high') {
          const rec = brand.byop_recommendation
          setByopRecommendation(
            typeof rec === 'string' && rec.trim().length > 0 ? rec : undefined
          )
        }
      })
      .catch(() => {})
  }, [brandId])

  // View mode: load existing post; Generate mode: start SSE generation
  useEffect(() => {
    if (viewPostId && brandId) {
      // View an existing post
      api.getPost(brandId, viewPostId)
        .then(post => {
          // If post is stuck/failed, show error with retry option instead of blank screen
          if (post.status === 'failed' || post.status === 'generating') {
            reset()
            return
          }
          loadExisting({
            postId: post.post_id,
            caption: post.caption || '',
            hashtags: post.hashtags || [],
            imageUrl: post.image_url || null,
            imageUrls: (post as unknown as Record<string, unknown>).image_urls as string[] || [],
            videoUrl: post.video?.url || null,
          })
        })
        .catch(() => {})
    } else if (planId && dayIndex !== undefined && brandId) {
      // Guard against double-fire in React strict mode
      if (generatedRef.current) return
      generatedRef.current = true
      // Auto-start generation; return cleanup so EventSource closes on unmount
      const cleanup = generate(planId, parseInt(dayIndex, 10), brandId, undefined, imageStyle || undefined)
      return () => {
        generatedRef.current = false
        if (typeof cleanup === 'function') cleanup()
      }
    }
  }, [planId, dayIndex, brandId, imageStyle, generate, viewPostId, loadExisting])

  const handleRegenerate = (instructions?: string) => {
    if (planId && dayIndex !== undefined && brandId) {
      hasRegenerated.current = true
      reset()
      generate(planId, parseInt(dayIndex, 10), brandId, instructions, imageStyle || undefined)
    }
  }

  // Re-trigger review after regeneration completes
  useEffect(() => {
    if (state.status === 'complete' && hasRegenerated.current) {
      hasRegenerated.current = false
      setReviewKey(k => k + 1)
    }
  }, [state.status])

  // L-8: Navigate to next day if one exists
  const currentDayIdx = dayIndex !== undefined ? parseInt(dayIndex, 10) : -1
  const hasNextDay = planDayCount > 0 && currentDayIdx < planDayCount - 1

  const goToNextDay = () => {
    if (planId && hasNextDay) {
      reset()
      navigate(`/generate/${planId}/${currentDayIdx + 1}?brand_id=${brandId}`)
    }
  }

  const isViewMode = !!viewPostId

  // H-3: Subtitle uses platform + content_theme from dayBrief instead of raw UUID
  const displayDay = dayBrief?.day_index !== undefined ? dayBrief.day_index + 1 : currentDayIdx + 1
  const subtitle = dayBrief
    ? `Day ${displayDay} · ${dayBrief.platform} · ${dayBrief.content_theme}`
    : `Day ${displayDay}`

  return (
    <PageContainer maxWidth={960} minHeight="calc(100vh - 53px)">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
        {/* H-1: Navigate to dashboard instead of navigate(-1) which can exit the app */}
        <button
          onClick={() => navigate(`/dashboard/${brandId}`)}
          style={{
            padding: '6px 12px', borderRadius: 6, border: `1px solid ${A.border}`,
            background: 'transparent', color: A.textSoft, fontSize: 13, cursor: 'pointer',
          }}
        >
          ← Dashboard
        </button>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: A.text, margin: 0 }}>
            {isViewMode ? 'View Post' : 'Generate Post'}
          </h1>
          {/* H-3: Show human-readable context instead of Plan UUID */}
          <p style={{ fontSize: 13, color: A.textSoft, margin: 0 }}>{subtitle}</p>
        </div>
        {/* L-7: Remove dead "✨ AI Generation" placeholder */}
      </div>

      {/* Generator */}
      <div style={{
        padding: 24, borderRadius: 12,
        background: A.surface, border: `1px solid ${A.border}`,
      }}>
        <PostGenerator
          state={state}
          dayBrief={dayBrief}
          onRegenerate={handleRegenerate}
          brandId={brandId}
          byopRecommendation={byopRecommendation}
          onVideoGenerated={() => setReviewKey(k => k + 1)}
          overrideImageUrl={editedImageUrl}
          editMediaSlot={
            state.status === 'complete' && state.postId && brandId && (editedImageUrl || state.imageUrl || state.imageUrls.length > 0 || (state.videoUrl && dayBrief?.derivative_type === 'video_first'))
              ? <EditMediaSection
                  postId={state.postId}
                  brandId={brandId}
                  imageUrl={editedImageUrl || state.imageUrl || state.videoUrl!}
                  imageUrls={state.imageUrls.length > 0 ? state.imageUrls : undefined}
                  videoUrl={dayBrief?.derivative_type === 'video_first' ? state.videoUrl : undefined}
                  derivativeType={dayBrief?.derivative_type}
                  editCount={editedEditCount}
                  onImageUpdated={(newUrl, newCount) => {
                    setEditedImageUrl(newUrl)
                    setEditedEditCount(newCount)
                  }}
                />
              : undefined
          }
          editVideoSlot={
            state.status === 'complete' && state.postId && brandId && state.videoUrl && dayBrief?.derivative_type !== 'video_first'
              ? <EditMediaSection
                  postId={state.postId}
                  brandId={brandId}
                  imageUrl={editedImageUrl || state.imageUrl || state.videoUrl}
                  videoUrl={state.videoUrl}
                  derivativeType="video_first"
                  editCount={editedVideoCount}
                  onImageUpdated={(_newUrl, newCount) => {
                    setEditedVideoCount(newCount)
                  }}
                />
              : undefined
          }
        />
      </div>

      {/* AI Brand Review — shown once generation is complete. H-2: Approval handled only here, not in PostGenerator */}
      {state.status === 'complete' && state.postId && brandId && (
        <div style={{
          marginTop: 16, padding: 24, borderRadius: 12,
          background: A.surface, border: `1px solid ${A.border}`,
        }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: A.text, marginBottom: 14 }}>
            AI Brand Review
          </h3>
          <ReviewPanel
            brandId={brandId}
            postId={state.postId}
            reviewKey={reviewKey}
            onApproved={() => navigate(`/dashboard/${brandId}?approved=${state.postId}`)}
            initialReview={state.review as any}
          />

          {/* L-8: Next Day CTA — shown after post is complete */}
          {hasNextDay && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${A.border}` }}>
              <button
                onClick={goToNextDay}
                style={{
                  padding: '10px 20px', borderRadius: 8, border: 'none', cursor: 'pointer',
                  background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                  color: 'white', fontSize: 13, fontWeight: 600,
                }}
              >
                Next Post →
              </button>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  )
}
