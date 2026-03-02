import { useState } from 'react'
import { A } from '../theme'
import { getPlatform } from '../platformRegistry'

function normalizePlatform(platform: string): string {
  return getPlatform(platform).key
}

// Count all hashtags: both from the structured array and inline in caption body
function countInlineHashtags(caption: string): number {
  return (caption.match(/#\w+/g) ?? []).length
}

// Shared animated progress bar with proper ARIA
function CharBar({ len, max }: { len: number; max: number }) {
  const rawPct = (len / max) * 100
  const pct = Math.min(rawPct, 100) // clamp for CSS width only
  const overLimit = len > max
  const barColor = overLimit ? A.coral : rawPct >= 80 ? A.amber : A.emerald

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(rawPct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${len} of ${max} characters used`}
      style={{ flex: 1, height: 4, borderRadius: 2, background: A.border }}
    >
      <div style={{
        height: 4, borderRadius: 2,
        width: `${pct}%`,
        background: barColor,
        transition: 'width 0.3s ease, background 0.3s ease',
      }} />
    </div>
  )
}

function LinkedInPreview({ caption, imageUrl, videoUrl }: { caption: string; imageUrl?: string; videoUrl?: string }) {
  const spec = getPlatform('linkedin')
  const foldAt = spec.foldAt!
  const max = spec.captionMax
  const isFolded = caption.length > foldAt
  const overLimit = caption.length > max
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={{ borderRadius: 8, border: `1px solid ${A.border}`, overflow: 'hidden', background: A.surface }}>
      {/* Header */}
      <div style={{ padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: `1px solid ${A.border}` }}>
        <div style={{
          width: 30, height: 30, borderRadius: '50%',
          background: A.indigoLight, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
        }}>💼</div>
        <div>
          <p style={{ fontSize: 11, fontWeight: 600, color: A.text, margin: 0 }}>Your Brand</p>
          <p style={{ fontSize: 10, color: A.textMuted, margin: 0 }}>LinkedIn · Just now</p>
        </div>
      </div>

      {/* Media at LinkedIn's 1.91:1 ratio */}
      {(imageUrl || videoUrl) && (
        <div style={{ width: '100%', aspectRatio: '1.91 / 1', overflow: 'hidden' }}>
          {videoUrl
            ? <video src={videoUrl} controls muted loop style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : <img src={imageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          }
        </div>
      )}

      {/* Caption with fold simulation */}
      <div style={{ padding: '8px 10px' }}>
        <p style={{ fontSize: 11, color: A.text, margin: '0 0 8px', lineHeight: 1.55 }}>
          {expanded || !isFolded ? caption : caption.slice(0, foldAt)}
          {isFolded && !expanded && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: A.textSoft, fontSize: 11, padding: '0 2px',
              }}
            >
              …see more
            </button>
          )}
        </p>

        {/* Char count row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <CharBar len={caption.length} max={max} />
          <span style={{
            fontSize: 10, flexShrink: 0,
            color: overLimit ? A.coral : A.textMuted,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {caption.length.toLocaleString()} / {max.toLocaleString()}
            {overLimit && <span role="alert"> ⚠️</span>}
          </span>
        </div>

        {/* Fold warning */}
        {isFolded && (
          <div style={{
            marginTop: 6, fontSize: 10, color: A.amber,
            padding: '3px 7px', borderRadius: 4,
            background: `${A.amber}18`, border: `1px solid ${A.amber}30`,
          }}>
            ⚠️ First {foldAt} chars appear above "see more" fold — hook must be here
          </div>
        )}
      </div>
    </div>
  )
}

function XPreview({ caption }: { caption: string }) {
  const max = getPlatform('x').captionMax
  const overLimit = caption.length > max
  const displayCaption = overLimit ? caption.slice(0, 277) + '…' : caption

  return (
    <div style={{ borderRadius: 8, border: `1px solid ${A.border}`, overflow: 'hidden', background: A.surface }}>
      {/* Header */}
      <div style={{ padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: `1px solid ${A.border}` }}>
        <div style={{
          width: 30, height: 30, borderRadius: '50%',
          background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, color: 'white', fontWeight: 700, fontFamily: 'serif',
        }}>𝕏</div>
        <div>
          <p style={{ fontSize: 11, fontWeight: 600, color: A.text, margin: 0 }}>Your Brand</p>
          <p style={{ fontSize: 10, color: A.textMuted, margin: 0 }}>X · Just now</p>
        </div>
      </div>

      <div style={{ padding: '8px 10px' }}>
        {/* Caption — truncated if over limit */}
        <p style={{ fontSize: 11, color: A.text, margin: '0 0 8px', lineHeight: 1.55 }}>
          {displayCaption}
        </p>

        {/* Char count row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <CharBar len={caption.length} max={max} />
          <span style={{
            fontSize: 10, flexShrink: 0,
            color: overLimit ? A.coral : A.textMuted,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {caption.length} / {max}
            {overLimit && <span role="alert"> ⚠️</span>}
          </span>
        </div>

        {/* Truncation warning */}
        {overLimit && (
          <div style={{
            marginTop: 6, fontSize: 10, color: A.coral,
            padding: '3px 7px', borderRadius: 4,
            background: `${A.coral}15`, border: `1px solid ${A.coral}30`,
          }} role="alert">
            Caption truncated at 280 characters on X — text above is what users will see
          </div>
        )}
      </div>
    </div>
  )
}

function InstagramPreview({ caption, imageUrl, videoUrl, structuredHashtagCount }: {
  caption: string
  imageUrl?: string
  videoUrl?: string
  structuredHashtagCount: number
}) {
  const igSpec = getPlatform('instagram')
  const max = igSpec.captionMax
  const hashtagMax = igSpec.hashtagMax
  // Count both inline # in caption and structured hashtags from the array
  const inlineCount = countInlineHashtags(caption)
  const totalHashtags = structuredHashtagCount + inlineCount
  const overHashtags = totalHashtags > hashtagMax

  return (
    <div style={{ borderRadius: 8, border: `1px solid ${A.border}`, overflow: 'hidden', background: A.surface }}>
      {/* Header */}
      <div style={{ padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: `1px solid ${A.border}` }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: 'linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12,
        }}>📸</div>
        <p style={{ fontSize: 11, fontWeight: 600, color: A.text, margin: 0 }}>Your Brand</p>
      </div>

      {/* 1:1 square media crop */}
      {videoUrl ? (
        <div style={{ width: '100%', aspectRatio: '1 / 1', overflow: 'hidden' }}>
          <video src={videoUrl} controls muted loop style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      ) : imageUrl ? (
        <div style={{ width: '100%', aspectRatio: '1 / 1', overflow: 'hidden' }}>
          <img src={imageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      ) : (
        <div style={{ width: '100%', aspectRatio: '1 / 1', background: A.surfaceAlt, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 24, opacity: 0.3 }}>🖼️</span>
        </div>
      )}

      {/* Caption — Instagram shows ~125 chars then "more" */}
      <div style={{ padding: '8px 10px' }}>
        <p style={{ fontSize: 11, color: A.text, margin: '0 0 8px', lineHeight: 1.55 }}>
          {caption.slice(0, 125)}{caption.length > 125 ? '…' : ''}
        </p>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: overHashtags ? A.coral : A.textMuted }}>
            {totalHashtags} / {hashtagMax} hashtags
            {overHashtags && <span role="alert"> ⚠️</span>}
          </span>
          <span style={{ fontSize: 10, color: A.textMuted }}>
            {caption.length.toLocaleString()} / {max.toLocaleString()} chars
          </span>
        </div>
      </div>
    </div>
  )
}

function GenericPreview({ caption, platform }: { caption: string; platform: string }) {
  const max = getPlatform(platform).captionMax
  const overLimit = caption.length > max

  return (
    <div style={{ borderRadius: 8, border: `1px solid ${A.border}`, padding: '10px 12px', background: A.surface }}>
      <p style={{ fontSize: 11, color: A.text, margin: '0 0 8px', lineHeight: 1.5 }}>
        {caption.slice(0, 100)}{caption.length > 100 ? '…' : ''}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <CharBar len={caption.length} max={max} />
        <span style={{ fontSize: 10, color: overLimit ? A.coral : A.textMuted, flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
          {caption.length.toLocaleString()} / {max.toLocaleString()}
        </span>
      </div>
    </div>
  )
}

interface PlatformPreviewProps {
  platform: string
  caption: string
  imageUrl?: string
  videoUrl?: string
  hashtagCount: number
}

export default function PlatformPreview({ platform, caption, imageUrl, videoUrl, hashtagCount }: PlatformPreviewProps) {
  const normalized = normalizePlatform(platform)

  return (
    <div>
      <p style={{ fontSize: 11, fontWeight: 500, color: A.textSoft, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        Platform Preview
      </p>
      {normalized === 'linkedin' && <LinkedInPreview caption={caption} imageUrl={imageUrl} videoUrl={videoUrl} />}
      {normalized === 'x' && <XPreview caption={caption} />}
      {normalized === 'instagram' && (
        <InstagramPreview caption={caption} imageUrl={imageUrl} videoUrl={videoUrl} structuredHashtagCount={hashtagCount} />
      )}
      {normalized !== 'linkedin' && normalized !== 'x' && normalized !== 'instagram' && (
        <GenericPreview caption={caption} platform={normalized} />
      )}
    </div>
  )
}
