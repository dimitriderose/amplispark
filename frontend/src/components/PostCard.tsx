import { useState, useRef } from 'react'
import { A } from '../theme'
import { api } from '../api/client'
import type { Post } from '../hooks/usePostLibrary'

const STATUS_COLORS: Record<string, string> = {
  approved: A.emerald,
  complete: A.indigo,
  generating: A.amber,
  failed: A.coral,
  draft: A.textMuted,
}

const STATUS_LABELS: Record<string, string> = {
  approved: '✓ Approved',
  complete: 'Ready',
  generating: '⟳ Generating',
  failed: '✗ Failed',
  draft: 'Draft',
}

interface Props {
  post: Post
  brandId: string
  onApproved?: () => void
  /** DK-5: Called when user dismisses a stuck 'generating' or 'failed' post from the UI */
  onDismiss?: () => void
  /** Navigate to view this post's full content */
  onView?: () => void
}

export default function PostCard({ post, brandId, onApproved, onDismiss, onView }: Props) {
  const color = STATUS_COLORS[post.status] || A.textMuted
  const label = STATUS_LABELS[post.status] || post.status
  const [copied, setCopied] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [approveError, setApproveError] = useState<string | null>(null)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isFinal = post.status === 'complete' || post.status === 'approved'

  const handleCopy = () => {
    if (!navigator.clipboard) return
    const tags = (post.hashtags || []).map((h: string) => `#${h.replace(/^#/, '')}`).join(' ')
    const fullText = [post.caption, tags].filter(Boolean).join('\n\n')
    navigator.clipboard.writeText(fullText)
      .then(() => {
        if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
        setCopied(true)
        copyTimerRef.current = setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {})
  }

  const handleExport = async () => {
    setExportError(null)
    try {
      await api.exportPost(post.post_id, brandId)
    } catch (err: any) {
      setExportError(err.message || 'Export failed')
    }
  }

  const handleApprove = async () => {
    setApproveError(null)
    try {
      await api.approvePost(brandId, post.post_id)
      onApproved?.()
    } catch (err: any) {
      // L-5: Inline error instead of alert()
      setApproveError(err.message || 'Approval failed')
    }
  }

  return (
    <div style={{
      borderRadius: 10, background: A.surface, border: `1px solid ${A.border}`,
      overflow: 'hidden', display: 'flex', flexDirection: 'column',
    }}>
      {/* Image or placeholder */}
      <div
        onClick={isFinal && onView ? onView : undefined}
        style={{
          width: '100%', aspectRatio: '1', background: A.surfaceAlt,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          overflow: 'hidden', position: 'relative',
          cursor: isFinal && onView ? 'pointer' : 'default',
        }}
      >
        {post.image_url ? (
          <img
            src={post.image_url}
            alt="Post visual"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : post.video?.url ? (
          <video
            src={post.video.url}
            muted
            loop
            playsInline
            onMouseOver={e => (e.target as HTMLVideoElement).play()}
            onMouseOut={e => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0 }}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <span style={{ fontSize: 32, opacity: 0.3 }}>🖼️</span>
        )}
        {/* Status badge overlay */}
        <span style={{
          position: 'absolute', top: 8, right: 8,
          fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 12,
          background: color + '22', color, border: `1px solid ${color}44`,
        }}>
          {label}
        </span>
        {/* DK-5: Dismiss button for stuck generating/failed posts */}
        {(post.status === 'generating' || post.status === 'failed') && onDismiss && (
          <button
            onClick={onDismiss}
            title="Remove from view"
            style={{
              position: 'absolute', top: 8, left: 8,
              width: 20, height: 20, borderRadius: '50%',
              background: 'rgba(0,0,0,0.45)', border: 'none',
              color: 'white', fontSize: 12, lineHeight: 1,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ×
          </button>
        )}
      </div>

      {/* Content */}
      <div style={{ padding: '12px 14px', flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* Platform + Day */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {post.platform && (
            <span style={{
              fontSize: 11, fontWeight: 500, color: A.textSoft,
              background: A.surfaceAlt, padding: '2px 7px', borderRadius: 10,
            }}>
              {post.platform}
            </span>
          )}
          <span style={{ fontSize: 11, color: A.textMuted }}>
            Day {(post.day_index ?? 0) + 1}
          </span>
        </div>

        {/* Caption preview */}
        <p style={{
          fontSize: 12, color: A.textSoft, margin: 0, lineHeight: 1.5,
          display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        } as React.CSSProperties}>
          {post.caption || 'No caption yet'}
        </p>

        {/* Hashtags */}
        {post.hashtags && post.hashtags.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {post.hashtags.slice(0, 3).map((tag, i) => (
              <span key={i} style={{ fontSize: 10, color: A.indigo, background: A.indigoLight, padding: '1px 6px', borderRadius: 8 }}>
                #{tag}
              </span>
            ))}
            {post.hashtags.length > 3 && (
              <span style={{ fontSize: 10, color: A.textMuted }}>+{post.hashtags.length - 3}</span>
            )}
          </div>
        )}

        {/* L-5: Inline errors instead of alert() */}
        {exportError && (
          <p style={{ fontSize: 11, color: A.coral, margin: 0 }}>{exportError}</p>
        )}
        {approveError && (
          <p style={{ fontSize: 11, color: A.coral, margin: 0 }}>{approveError}</p>
        )}

        {/* Action buttons */}
        <div style={{ marginTop: 'auto', display: 'flex', gap: 6, paddingTop: 4, flexWrap: 'wrap' }}>
          {/* Copy caption — only when post is complete/approved with a caption */}
          {isFinal && post.caption && (
            <button
              type="button"
              onClick={handleCopy}
              aria-label={copied ? 'Copied to clipboard' : 'Copy caption to clipboard'}
              title="Copy caption + hashtags"
              style={{
                flex: 1, padding: '6px', borderRadius: 6, cursor: 'pointer',
                border: `1px solid ${copied ? A.emerald : A.border}`,
                background: copied ? A.emeraldLight : 'transparent',
                color: copied ? A.emerald : A.textSoft,
                fontSize: 11, fontWeight: 500, transition: 'all 0.2s',
              }}
            >
              {copied ? '✓ Copied' : '⎘ Copy'}
            </button>
          )}
          {(post.status === 'complete' || post.status === 'approved') && (
            <button
              onClick={handleExport}
              style={{
                flex: 1, padding: '6px', borderRadius: 6, border: 'none', cursor: 'pointer',
                background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                color: 'white', fontSize: 11, fontWeight: 600,
              }}
            >
              ↓ Export
            </button>
          )}
          {post.status === 'complete' && (
            <button
              onClick={handleApprove}
              style={{
                flex: 1, padding: '6px', borderRadius: 6, border: `1px solid ${A.emerald}`,
                background: 'transparent', color: A.emerald, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              ✓ Approve
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
