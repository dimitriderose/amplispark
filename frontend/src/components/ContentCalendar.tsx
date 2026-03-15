import React, { useEffect, useRef, useState } from 'react'
import { A } from '../theme'
import { getPlatform } from '../platformRegistry'
import { api } from '../api/client'
import { IMAGE_STYLE_GROUPS, styleLabel } from '../imageStyleOptions'
import { useIsMobile } from '../hooks/useIsMobile'
import type { Post } from '../hooks/usePostLibrary'

const PILLAR_COLORS: Record<string, string> = {
  education: A.indigo,
  inspiration: A.violet,
  promotion: A.coral,
  behind_the_scenes: A.emerald,
  user_generated: A.amber,
}

const STATUS_COLORS: Record<string, string> = {
  approved: A.emerald,
  complete: A.indigo,
  generating: A.amber,
  failed: A.coral,
}

const STATUS_LABELS: Record<string, string> = {
  approved: 'Approved',
  complete: 'Ready',
  generating: 'Generating',
  failed: 'Failed',
}

// Colors for series groups (distinct from pillar colors)
const SERIES_PALETTE = ['#f97316', '#06b6d4', '#ec4899', '#a78bfa']

/** Parse "8:00 AM" / "1:30 PM" into minutes since midnight for sorting. */
function parseTime(t?: string): number {
  if (!t) return 9999
  const m = t.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i)
  if (!m) return 9999
  let h = parseInt(m[1], 10)
  const min = parseInt(m[2], 10)
  const pm = m[3].toUpperCase() === 'PM'
  if (pm && h !== 12) h += 12
  if (!pm && h === 12) h = 0
  return h * 60 + min
}

export interface DayBrief {
  day_index: number
  platform: string
  pillar: string
  pillar_id?: string
  content_theme: string
  caption_hook: string
  key_message: string
  image_prompt: string
  hashtags: string[]
  derivative_type?: string
  event_anchor?: string | null
  custom_photo_url?: string | null
  suggested_time?: string
}

interface Props {
  plan: { plan_id: string; days: DayBrief[] }
  brandId?: string
  posts?: Post[]
  defaultImageStyle?: string
  onGeneratePost?: (planId: string, dayIndex: number, imageStyle?: string) => void
  onViewPost?: (planId: string, dayIndex: number, postId: string) => void
  onPhotoUploaded?: (dayIndex: number, photoUrl: string | null) => void
  trendSummary?: {
    researched_at: string
    platform_trends: Record<string, any>
    visual_trends: Record<string, any> | null
    video_trends: Record<string, any> | null
  }
  onRefreshResearch?: () => void
}

export default function ContentCalendar({ plan, brandId, posts, defaultImageStyle, onGeneratePost, onViewPost, onPhotoUploaded, trendSummary, onRefreshResearch }: Props) {
  const isMobile = useIsMobile()
  const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  // Map posts by day_index+platform — use the latest post per (day, platform)
  const postsByDayPlatform: Record<string, Post> = {}
  if (posts) {
    for (const post of posts) {
      const key = `${post.day_index}_${post.platform || ''}`
      const existing = postsByDayPlatform[key]
      if (!existing || (post.created_at && existing.created_at && post.created_at > existing.created_at)) {
        postsByDayPlatform[key] = post
      }
    }
  }

  // Compute which pillar_ids form repurposing series
  const pillarIdCounts: Record<string, number> = {}
  for (const day of plan.days) {
    if (day.pillar_id) {
      pillarIdCounts[day.pillar_id] = (pillarIdCounts[day.pillar_id] || 0) + 1
    }
  }
  const seriesIds = Object.keys(pillarIdCounts).filter(id => pillarIdCounts[id] > 1)
  const seriesColorMap: Record<string, string> = {}
  seriesIds.forEach((id, i) => {
    seriesColorMap[id] = SERIES_PALETTE[i % SERIES_PALETTE.length]
  })

  const hasAnySeries = seriesIds.length > 0

  // Group days by day_index for column stacking, tracking original array position
  const uniqueDayIndices: number[] = []
  const dayGroups: Record<number, (DayBrief & { _arrayIndex: number })[]> = {}
  for (let ai = 0; ai < plan.days.length; ai++) {
    const day = plan.days[ai]
    const idx = day.day_index ?? 0
    if (!dayGroups[idx]) {
      dayGroups[idx] = []
      uniqueDayIndices.push(idx)
    }
    dayGroups[idx].push({ ...day, _arrayIndex: ai })
  }
  // Sort each day's cards by suggested_time (earliest first)
  for (const idx of uniqueDayIndices) {
    dayGroups[idx].sort((a, b) => {
      const ta = parseTime(a.suggested_time)
      const tb = parseTime(b.suggested_time)
      return ta - tb
    })
  }
  const numDays = uniqueDayIndices.length
  const totalPosts = plan.days.length
  const isMultiPlatform = totalPosts > numDays
  const uniquePlatforms = new Set(plan.days.map(d => d.platform)).size

  return (
    <div>
      {/* Calendar header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: A.text, margin: 0 }}>
          {numDays}-Day Content Calendar
          {isMultiPlatform && (
            <span style={{ fontSize: 12, fontWeight: 400, color: A.textMuted, marginLeft: 8 }}>
              · {totalPosts} posts across {uniquePlatforms} platforms
            </span>
          )}
        </h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {Object.entries(PILLAR_COLORS).map(([pillar, color]) => (
            <span
              key={pillar}
              style={{ fontSize: 11, color: A.textSoft, display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <span style={{ width: 8, height: 8, borderRadius: 2, background: color, display: 'inline-block', flexShrink: 0 }} />
              {pillar.replace(/_/g, ' ')}
            </span>
          ))}
          {hasAnySeries && (
            <span style={{ fontSize: 11, color: A.textSoft, display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 10 }}>♻</span>
              repurposed
            </span>
          )}
        </div>
      </div>

      {/* Trend Research Banner */}
      {trendSummary && (
        <div style={{ marginBottom: 12, padding: '10px 14px', borderRadius: 8, background: '#f8f9ff', border: '1px solid #e0e4f0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span>📊</span>
            <span style={{ fontWeight: 600, fontSize: 13 }}>Trend Research</span>
            <span style={{ fontSize: 11, color: '#888', marginLeft: 4 }}>
              {new Date(trendSummary.researched_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            </span>
            {onRefreshResearch && (
              <button onClick={onRefreshResearch} title="Refresh trend research" style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: 14 }}>↻ Refresh</button>
            )}
          </div>
          {trendSummary.platform_trends && Object.keys(trendSummary.platform_trends).length > 0 && (
            <div style={{ fontSize: 11, color: '#555', marginBottom: 3 }}>
              <strong>Captions:</strong>{' '}
              {Object.values(trendSummary.platform_trends)
                .flatMap((t: any) => t?.trending_hooks?.slice(0, 2) ?? [])
                .slice(0, 4)
                .join(' · ')}
            </div>
          )}
          {trendSummary.visual_trends && (
            <div style={{ fontSize: 11, color: '#555', marginBottom: 3 }}>
              <strong>Visuals:</strong>{' '}
              {[...(trendSummary.visual_trends.trending_styles?.slice(0, 2) ?? []), trendSummary.visual_trends.format_performance].filter(Boolean).join(' · ').slice(0, 120)}
            </div>
          )}
          {trendSummary.video_trends && (
            <div style={{ fontSize: 11, color: '#555' }}>
              <strong>Video:</strong>{' '}
              {[...(trendSummary.video_trends.trending_formats?.slice(0, 2) ?? []), trendSummary.video_trends.optimal_lengths].filter(Boolean).join(' · ').slice(0, 120)}
            </div>
          )}
        </div>
      )}

      {/* Day-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : `repeat(${numDays}, 1fr)`, gap: 8 }}>
        {uniqueDayIndices.map((dayIdx, colIndex) => {
          const days = dayGroups[dayIdx]
          return (
            <div key={dayIdx} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {days.map((day, j) => {
                const seriesColor = day.pillar_id ? seriesColorMap[day.pillar_id] : undefined
                const dayPost = postsByDayPlatform[`${dayIdx}_${day.platform || ''}`]
                  ?? postsByDayPlatform[`${dayIdx}_`]
                return (
                  <DayCard
                    key={`${dayIdx}_${day.platform || j}`}
                    day={day}
                    dayName={j === 0 ? DAY_NAMES[colIndex % 7] : ''}
                    brandId={brandId}
                    planId={plan.plan_id}
                    arrayIndex={day._arrayIndex}
                    seriesColor={seriesColor}
                    post={dayPost}
                    defaultImageStyle={defaultImageStyle}
                    onGenerate={(imageStyle) => onGeneratePost?.(plan.plan_id, day._arrayIndex, imageStyle)}
                    onViewPost={dayPost && onViewPost
                      ? () => onViewPost(plan.plan_id, day._arrayIndex, dayPost.post_id)
                      : undefined
                    }
                    onPhotoUploaded={(photoUrl) => onPhotoUploaded?.(day._arrayIndex, photoUrl)}
                  />
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}

interface DayCardProps {
  day: DayBrief
  dayName: string
  brandId?: string
  planId?: string
  arrayIndex: number
  seriesColor?: string
  post?: Post
  defaultImageStyle?: string
  onGenerate: (imageStyle?: string) => void
  onViewPost?: () => void
  onPhotoUploaded: (photoUrl: string | null) => void
}

function DayCard({ day, dayName, brandId, planId, arrayIndex, seriesColor, post, defaultImageStyle, onGenerate, onViewPost, onPhotoUploaded }: DayCardProps) {
  const pillarColor = PILLAR_COLORS[day.pillar] || A.indigo
  const platformSpec = getPlatform(day.platform)
  const PlatformIcon = platformSpec.icon
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [photoError, setPhotoError] = useState('')
  const [showStyleMenu, setShowStyleMenu] = useState(false)
  const [selectedStyle, setSelectedStyle] = useState(defaultImageStyle || '')
  const styleMenuRef = useRef<HTMLDivElement>(null)
  useEffect(() => { setSelectedStyle(defaultImageStyle || '') }, [defaultImageStyle])
  // Close style menu on click outside
  useEffect(() => {
    if (!showStyleMenu) return
    const handler = (e: MouseEvent) => {
      if (styleMenuRef.current && !styleMenuRef.current.contains(e.target as Node)) {
        setShowStyleMenu(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showStyleMenu])

  const dayIndex = arrayIndex
  const isGenerated = post && (post.status === 'complete' || post.status === 'approved')
  const isGenerating = post?.status === 'generating'

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !brandId || !planId || dayIndex === undefined) return

    setUploading(true)
    setPhotoError('')
    const fd = new FormData()
    fd.append('file', file)

    try {
      const res = await api.uploadDayPhoto(brandId, planId, dayIndex, fd) as any
      onPhotoUploaded(res.custom_photo_url)
    } catch (err: any) {
      setPhotoError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleRemovePhoto = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!brandId || !planId || dayIndex === undefined) return
    setUploading(true)
    setPhotoError('')
    try {
      await api.deleteDayPhoto(brandId, planId, dayIndex)
      onPhotoUploaded(null)
    } catch (err: any) {
      setPhotoError(err.message || 'Remove failed')
    } finally {
      setUploading(false)
    }
  }

  // Review score from the post
  const reviewScore = (post as any)?.review?.score as number | undefined

  return (
    <div
      style={{
        borderRadius: 10,
        background: A.surface,
        border: `1px solid ${isGenerated ? A.emerald + '44' : A.border}`,
        boxShadow: seriesColor ? `inset 3px 0 0 0 ${seriesColor}` : undefined,
        overflow: 'visible',
        transition: 'transform 0.15s, box-shadow 0.15s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = seriesColor
          ? `0 4px 16px rgba(0,0,0,0.08), inset 3px 0 0 0 ${seriesColor}`
          : '0 4px 16px rgba(0,0,0,0.08)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = seriesColor ? `inset 3px 0 0 0 ${seriesColor}` : 'none'
      }}
    >
      {/* Pillar color bar */}
      <div style={{ height: 3, background: pillarColor, borderRadius: '10px 10px 0 0' }} />

      {/* Generated post thumbnail + status bar */}
      {isGenerated && (post?.image_url || post?.video?.url) ? (
        <div>
          {post.video?.url && !post.image_url ? (
            <video
              src={post.video.url}
              muted
              loop
              playsInline
              onMouseOver={e => (e.target as HTMLVideoElement).play()}
              onMouseOut={e => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0 }}
              style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block' }}
            />
          ) : (
            <img
              src={post.image_url}
              alt="Generated post"
              style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block' }}
            />
          )}
          {/* Status + score bar below image */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '4px 8px',
            background: (STATUS_COLORS[post.status] || A.textMuted) + '15',
            borderBottom: `2px solid ${STATUS_COLORS[post.status] || A.textMuted}`,
          }}>
            <span style={{
              fontSize: 10, fontWeight: 600,
              color: STATUS_COLORS[post.status] || A.textMuted,
            }}>
              {STATUS_LABELS[post.status] || post.status}
            </span>
            {reviewScore !== undefined && (
              <span style={{
                fontSize: 10, fontWeight: 700,
                color: reviewScore >= 8 ? A.emerald : reviewScore >= 6 ? A.amber : A.coral,
              }}>
                {reviewScore}/10
              </span>
            )}
          </div>
        </div>
      ) : day.custom_photo_url && !isGenerating ? (
        <div style={{ position: 'relative' }}>
          <img
            src={day.custom_photo_url}
            alt="Custom photo"
            style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block' }}
          />
          <button
            onClick={handleRemovePhoto}
            title="Remove photo"
            style={{
              position: 'absolute', top: 4, right: 4,
              width: 20, height: 20, borderRadius: '50%',
              background: 'rgba(0,0,0,0.55)', border: 'none',
              color: 'white', fontSize: 13, lineHeight: 1,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ×
          </button>
          <div style={{
            position: 'absolute', bottom: 4, left: 4,
            fontSize: 9, color: 'white', fontWeight: 600,
            background: 'rgba(0,0,0,0.5)', padding: '1px 5px', borderRadius: 4,
          }}>
            Your photo
          </div>
        </div>
      ) : isGenerating ? (
        <div style={{
          width: '100%', aspectRatio: '4 / 3',
          background: `linear-gradient(135deg, ${A.surfaceAlt}, ${A.indigoLight})`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexDirection: 'column', gap: 4,
        }}>
          <span style={{
            display: 'inline-block', width: 16, height: 16, borderRadius: '50%',
            border: `2px solid ${A.amber}`, borderTopColor: 'transparent',
            animation: 'cc-spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 10, color: A.amber, fontWeight: 500 }}>Generating...</span>
          <style>{`@keyframes cc-spin { to { transform: rotate(360deg) } }`}</style>
        </div>
      ) : null}

      <div style={{ padding: '10px 12px 14px' }}>
        {/* Day + platform */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: A.textSoft }}>{dayName}</span>
            {day.suggested_time && (
              <span style={{ fontSize: 10, color: A.textMuted, fontWeight: 400 }}>{day.suggested_time}</span>
            )}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <PlatformIcon size={14} color={platformSpec.color} />
            <span style={{ fontSize: 10, color: platformSpec.color, fontWeight: 500 }}>
              {platformSpec.displayName}
            </span>
          </span>
        </div>

        {/* Pillar badge */}
        <div
          style={{
            fontSize: 10,
            fontWeight: 500,
            padding: '2px 6px',
            borderRadius: 4,
            background: pillarColor + '15',
            color: pillarColor,
            display: 'inline-block',
            marginBottom: 6,
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          {day.pillar?.replace(/_/g, ' ')}
        </div>

        {/* Repurpose series indicator (left border only, no label — format not actually generated) */}

        {/* Event anchor badge */}
        {day.event_anchor && (
          <div style={{
            fontSize: 10, color: A.amber, background: A.amber + '15',
            padding: '2px 6px', borderRadius: 8, marginTop: 2,
            border: `1px solid ${A.amber}30`,
            display: 'inline-block', marginBottom: 6,
          }}>
            {day.event_anchor}
          </div>
        )}

        {/* Theme — 2 lines max */}
        <p
          style={{
            fontSize: 11,
            color: A.text,
            lineHeight: 1.4,
            marginBottom: 10,
            fontWeight: 500,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          } as React.CSSProperties}
        >
          {day.content_theme}
        </p>

        {/* Upload error */}
        {photoError && (
          <p style={{ fontSize: 10, color: A.coral, margin: '0 0 6px' }}>{photoError}</p>
        )}

        {/* Primary action: Generate (ungenerated) or View Post (generated) */}
        {!isGenerated && !isGenerating && (
          <div>
            {/* Generate button — always one-click */}
            <button
              onClick={() => onGenerate(selectedStyle || undefined)}
              style={{
                width: '100%',
                padding: '7px 0',
                borderRadius: 6,
                border: 'none',
                background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                color: 'white',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                marginBottom: 6,
              }}
            >
              {day.custom_photo_url ? 'Generate with photo' : 'Generate'}
            </button>

            {/* Visual Style button — opens dropdown */}
            <div ref={styleMenuRef} style={{ position: 'relative' }}>
              <button
                onClick={() => setShowStyleMenu(prev => !prev)}
                aria-haspopup="listbox"
                aria-expanded={showStyleMenu}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: 6,
                  border: `1px solid ${selectedStyle ? A.indigo + '40' : A.border}`,
                  background: selectedStyle ? `${A.indigo}08` : A.surface,
                  color: selectedStyle ? A.indigo : A.textSoft,
                  fontSize: 11,
                  fontWeight: 500,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: brandId && !day.custom_photo_url ? 6 : 0,
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ fontSize: 12 }}>✦</span>
                  Visual Style: {selectedStyle ? styleLabel(selectedStyle) : 'Auto'}
                </span>
                <span style={{ fontSize: 9, opacity: 0.6 }}>▾</span>
              </button>

              {/* Visual Style dropdown menu */}
              {showStyleMenu && (
                <div role="listbox" aria-label="Visual style" style={{
                  position: 'absolute', top: '100%', left: 0, right: 0,
                  marginTop: 4, borderRadius: 8,
                  background: A.surface, border: `1px solid ${A.border}`,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.14)', zIndex: 50,
                  maxHeight: 320, overflowY: 'auto', padding: '4px 0',
                }}>
                  {/* Auto option */}
                  <div
                    role="option"
                    aria-selected={!selectedStyle}
                    onClick={() => { setSelectedStyle(''); setShowStyleMenu(false) }}
                    style={{
                      padding: '7px 12px', cursor: 'pointer', fontSize: 12,
                      color: !selectedStyle ? A.indigo : A.text,
                      fontWeight: !selectedStyle ? 600 : 400,
                      background: !selectedStyle ? `${A.indigo}08` : 'transparent',
                      display: 'flex', alignItems: 'center', gap: 6,
                    }}
                    onMouseEnter={e => { if (selectedStyle) e.currentTarget.style.background = '#f5f5ff' }}
                    onMouseLeave={e => { if (selectedStyle) e.currentTarget.style.background = 'transparent' }}
                  >
                    <span style={{ width: 16, fontSize: 11, color: A.indigo }}>{!selectedStyle ? '✓' : ''}</span>
                    Auto (AI chooses)
                  </div>
                  <div style={{ height: 1, background: A.border, margin: '2px 8px' }} />

                  {/* Grouped styles */}
                  {IMAGE_STYLE_GROUPS.map(g => (
                    <div key={g.label} role="group" aria-label={g.label}>
                      <div style={{
                        padding: '8px 12px 3px', fontSize: 9, fontWeight: 700,
                        color: A.textMuted, textTransform: 'uppercase', letterSpacing: 0.6,
                      }}>
                        {g.label}
                      </div>
                      {g.options.map(o => {
                        const isSelected = selectedStyle === o.value
                        return (
                          <div
                            key={o.value}
                            role="option"
                            aria-selected={isSelected}
                            onClick={() => { setSelectedStyle(o.value); setShowStyleMenu(false) }}
                            title={o.desc}
                            style={{
                              padding: '5px 12px', cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: 6,
                              color: isSelected ? A.indigo : A.text,
                              fontWeight: isSelected ? 600 : 400,
                              background: isSelected ? `${A.indigo}08` : 'transparent',
                              fontSize: 12,
                            }}
                            onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = '#f5f5ff' }}
                            onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent' }}
                          >
                            <span style={{ width: 16, fontSize: 11, color: A.indigo }}>{isSelected ? '✓' : ''}</span>
                            {o.label}
                          </div>
                        )
                      })}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {isGenerated && onViewPost && (
          <button
            onClick={onViewPost}
            style={{
              width: '100%',
              padding: '6px 0',
              borderRadius: 6,
              border: `1px solid ${A.indigo}30`,
              background: A.indigoLight,
              color: A.indigo,
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            View Post →
          </button>
        )}

        {/* BYOP: add photo — only for ungenerated days without a photo yet */}
        {brandId && !isGenerated && !isGenerating && !day.custom_photo_url && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              style={{
                width: '100%',
                padding: '6px 0',
                background: uploading ? A.surfaceAlt : 'transparent',
                border: `1px dashed ${A.border}`,
                borderRadius: 6,
                color: uploading ? A.textMuted : A.textSoft,
                fontSize: 11,
                cursor: uploading ? 'not-allowed' : 'pointer',
                textAlign: 'center',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
              }}
              onMouseEnter={e => { if (!uploading) { e.currentTarget.style.borderColor = A.indigo; e.currentTarget.style.color = A.indigo } }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = A.border; e.currentTarget.style.color = A.textSoft }}
            >
              <span style={{ fontSize: 13 }}>📷</span>
              {uploading ? 'Uploading...' : 'Add your photo'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
