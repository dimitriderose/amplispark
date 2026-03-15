import { useState, useEffect } from 'react'
import { A } from '../theme'
import { api } from '../api/client'

interface EngagementScores {
  hook_strength: number
  relevance: number
  cta_effectiveness: number
  platform_fit: number
}

interface ReviewResult {
  score: number
  brand_alignment: 'strong' | 'moderate' | 'weak'
  strengths: string[]
  improvements: string[]
  approved: boolean
  revision_notes: string | null
  engagement_scores?: EngagementScores
  engagement_prediction?: 'low' | 'medium' | 'high' | 'viral'
}

interface Props {
  brandId: string
  postId: string
  reviewKey?: number
  onApproved?: () => void
  initialReview?: ReviewResult | null
}

const ALIGNMENT_COLORS = {
  strong: A.emerald,
  moderate: A.amber,
  weak: A.coral,
}

const PREDICTION_COLORS = {
  low: A.coral,
  medium: A.amber,
  high: A.emerald,
  viral: A.violet,
}

const PREDICTION_LABELS = {
  low: '📉 Low',
  medium: '📊 Medium',
  high: '📈 High',
  viral: '🚀 Viral',
}

const ENGAGEMENT_LABELS: Record<string, string> = {
  hook_strength: 'Hook',
  relevance: 'Relevance',
  cta_effectiveness: 'CTA',
  platform_fit: 'Platform Fit',
}

export default function ReviewPanel({ brandId, postId, reviewKey, onApproved, initialReview }: Props) {
  const [review, setReview] = useState<ReviewResult | null>(initialReview ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [approved, setApproved] = useState(false)
  // Auto-trigger review on mount ONLY if no initial review was provided
  // (e.g., viewing an existing post that was generated before the review gate)
  useEffect(() => {
    if (initialReview) {
      setReview(initialReview)
      return
    }
    if (postId && brandId) runReview()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId, brandId, reviewKey, initialReview])

  const runReview = async (force = false) => {
    // Reset prior results at the start so the re-review button doesn't cause a
    // stale-state flash (setReview(null) outside was async and didn't flush first)
    setReview(null)
    setLoading(true)
    setError('')
    try {
      const res = await api.reviewPost(brandId, postId, force) as unknown as { review: ReviewResult }
      setReview(res.review)
      // Don't auto-navigate on approval — let the user see the review first
    } catch (err: any) {
      setError(err.message || 'Review failed')
    } finally {
      setLoading(false)
    }
  }

  const handleManualApprove = async () => {
    try {
      await api.approvePost(brandId, postId)
      setApproved(true)
      onApproved?.()
    } catch (err: any) {
      setError(err.message || 'Approval failed')
    }
  }

  if (approved) {
    return (
      <div style={{
        padding: '16px 20px', borderRadius: 10,
        background: A.emeraldLight, border: `1px solid ${A.emerald}30`,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{ fontSize: 20 }}>✅</span>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 14, fontWeight: 600, color: A.emerald, margin: 0 }}>Post Approved</p>
          <p style={{ fontSize: 12, color: A.textSoft, margin: 0 }}>Ready for export</p>
        </div>
        {onApproved && (
          <button
            onClick={onApproved}
            style={{
              padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
              background: A.emerald, color: 'white', fontSize: 13, fontWeight: 600,
            }}
          >
            ← Dashboard
          </button>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Review trigger */}
      {!review && (
        <button
          onClick={() => runReview()}
          disabled={loading}
          style={{
            padding: '10px 20px', borderRadius: 8, border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
            background: loading ? A.surfaceAlt : `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
            color: loading ? A.textMuted : 'white',
            fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8,
          }}
        >
          {loading ? (
            <>
              <span style={{
                display: 'inline-block', width: 14, height: 14, borderRadius: '50%',
                border: `2px solid ${A.textMuted}`, borderTopColor: 'transparent',
                animation: 'spin 0.8s linear infinite',
              }} />
              Reviewing...
            </>
          ) : '🔍 AI Review'}
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </button>
      )}

      {error && (
        <p style={{ fontSize: 13, color: A.coral }}>{error}</p>
      )}

      {/* Review results */}
      {review && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Score + alignment */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 16,
            padding: '14px 16px', borderRadius: 10,
            background: A.surfaceAlt, border: `1px solid ${A.border}`,
          }}>
            {/* Score circle */}
            <div
              aria-label={`Review score: ${review.score} out of 10`}
              style={{
              width: 56, height: 56, borderRadius: '50%',
              background: `conic-gradient(${A.indigo} ${review.score * 36}deg, ${A.surfaceAlt} 0deg)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: '50%',
                background: A.surface,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontSize: 16, fontWeight: 700, color: A.text }}>{review.score}</span>
              </div>
            </div>
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: A.text, margin: 0 }}>
                Score {review.score}/10
              </p>
              <span style={{
                fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 20,
                background: ALIGNMENT_COLORS[review.brand_alignment] + '15',
                color: ALIGNMENT_COLORS[review.brand_alignment],
              }}>
                {review.brand_alignment.toUpperCase()} BRAND ALIGNMENT
              </span>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              {review.approved ? (
                <span style={{ fontSize: 13, color: A.emerald, fontWeight: 600 }}>✓ Auto-approved</span>
              ) : (
                <span style={{ fontSize: 13, color: A.amber }}>Needs review</span>
              )}
            </div>
          </div>

          {/* Engagement prediction */}
          {review.engagement_scores && review.engagement_prediction && (
            <div style={{
              padding: '12px 16px', borderRadius: 10,
              background: A.surfaceAlt, border: `1px solid ${A.border}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: A.textSoft, textTransform: 'uppercase', letterSpacing: 0.5, margin: 0 }}>
                  Engagement Prediction
                </p>
                <span style={{
                  fontSize: 12, fontWeight: 600, padding: '2px 10px', borderRadius: 20,
                  background: PREDICTION_COLORS[review.engagement_prediction] + '18',
                  color: PREDICTION_COLORS[review.engagement_prediction],
                }}>
                  {PREDICTION_LABELS[review.engagement_prediction]}
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {(Object.entries(review.engagement_scores) as [string, number][]).map(([key, val]) => (
                  <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 12, color: A.textSoft, width: 90, flexShrink: 0 }}>
                      {ENGAGEMENT_LABELS[key]}
                    </span>
                    <div style={{ flex: 1, height: 6, background: A.border, borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', width: `${val * 10}%`,
                        background: val >= 8 ? A.emerald : val >= 6 ? A.indigo : val >= 4 ? A.amber : A.coral,
                        borderRadius: 3, transition: 'width 0.4s ease',
                      }} />
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: A.text, width: 24, textAlign: 'right' }}>
                      {val}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strengths */}
          {review.strengths.length > 0 && (
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: A.textSoft, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
                Strengths
              </p>
              {review.strengths.map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                  <span style={{ color: A.emerald, fontSize: 14 }}>✓</span>
                  <span style={{ fontSize: 13, color: A.text }}>{s}</span>
                </div>
              ))}
            </div>
          )}

          {/* Improvements */}
          {review.improvements.length > 0 && (
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: A.textSoft, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
                Suggested improvements
              </p>
              {review.improvements.map((imp, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                  <span style={{ color: A.amber, fontSize: 14 }}>→</span>
                  <span style={{ fontSize: 13, color: A.text }}>{imp}</span>
                </div>
              ))}
            </div>
          )}

          {/* Revision notes if provided */}
          {review.revision_notes && (
            <div style={{ padding: '10px 14px', borderRadius: 8, background: A.indigoLight, border: `1px solid ${A.indigo}20` }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: A.indigo, margin: '0 0 6px 0', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Revision notes
              </p>
              <p style={{ fontSize: 13, color: A.text, lineHeight: 1.5, margin: 0 }}>{review.revision_notes}</p>
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8 }}>
            {review.approved ? (
              <button
                onClick={() => { setApproved(true); onApproved?.() }}
                style={{
                  flex: 1, padding: '10px', borderRadius: 8, border: 'none', cursor: 'pointer',
                  background: `linear-gradient(135deg, ${A.emerald}, #059669)`,
                  color: 'white', fontSize: 13, fontWeight: 600,
                }}
              >
                ✓ Done — Go to Dashboard
              </button>
            ) : (
              <button
                onClick={handleManualApprove}
                style={{
                  flex: 1, padding: '10px', borderRadius: 8, border: 'none', cursor: 'pointer',
                  background: `linear-gradient(135deg, ${A.emerald}, #059669)`,
                  color: 'white', fontSize: 13, fontWeight: 600,
                }}
              >
                ✓ Approve Anyway
              </button>
            )}
            <button
              onClick={() => runReview(true)}
              style={{
                padding: '10px 16px', borderRadius: 8,
                border: `1px solid ${A.border}`,
                background: 'transparent', color: A.textSoft,
                fontSize: 13, cursor: 'pointer',
              }}
            >
              ↺ Re-review
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
