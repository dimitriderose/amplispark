import { useState } from 'react'
import { A } from '../theme'
import { getPlatform, getMediaAspectRatio } from '../platformRegistry'

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

function CarouselMedia({ imageUrl, imageUrls, videoUrl, aspectRatio }: {
  imageUrl?: string
  imageUrls?: string[]
  videoUrl?: string
  aspectRatio: string
}) {
  const slides = imageUrls && imageUrls.length > 1 ? imageUrls : imageUrl ? [imageUrl] : []
  const isCarousel = slides.length > 1
  const [idx, setIdx] = useState(0)
  const active = slides[idx] ?? imageUrl

  if (videoUrl) return (
    <div style={{ width: '100%', aspectRatio, overflow: 'hidden' }}>
      <video src={videoUrl} controls muted loop style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </div>
  )
  if (!active) return null
  return (
    <div style={{ width: '100%', aspectRatio, overflow: 'hidden', position: 'relative' }}>
      <img src={active} alt={`Slide ${idx + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      {isCarousel && idx > 0 && (
        <button onClick={() => setIdx(i => i - 1)} style={{
          position: 'absolute', left: 6, top: '50%', transform: 'translateY(-50%)',
          background: 'rgba(0,0,0,0.4)', border: 'none', borderRadius: '50%',
          width: 24, height: 24, cursor: 'pointer', color: 'white', fontSize: 14,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>‹</button>
      )}
      {isCarousel && idx < slides.length - 1 && (
        <button onClick={() => setIdx(i => i + 1)} style={{
          position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)',
          background: 'rgba(0,0,0,0.4)', border: 'none', borderRadius: '50%',
          width: 24, height: 24, cursor: 'pointer', color: 'white', fontSize: 14,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>›</button>
      )}
      {isCarousel && (
        <div style={{ position: 'absolute', bottom: 8, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 4 }}>
          {slides.map((_, i) => (
            <div key={i} onClick={() => setIdx(i)} style={{
              width: 6, height: 6, borderRadius: '50%', cursor: 'pointer',
              background: i === idx ? 'white' : 'rgba(255,255,255,0.5)',
            }} />
          ))}
        </div>
      )}
      {isCarousel && (
        <span style={{ position: 'absolute', top: 8, right: 8, fontSize: 10, color: 'white', background: 'rgba(0,0,0,0.4)', padding: '2px 6px', borderRadius: 10 }}>
          {idx + 1}/{slides.length}
        </span>
      )}
    </div>
  )
}

function LinkedInPreview({ caption, imageUrl, imageUrls, videoUrl, derivativeType }: { caption: string; imageUrl?: string; imageUrls?: string[]; videoUrl?: string; derivativeType?: string }) {
  const spec = getPlatform('linkedin')
  const foldAt = spec.foldAt!
  const max = spec.captionMax
  const isFolded = caption.length > foldAt
  const overLimit = caption.length > max
  const [expanded, setExpanded] = useState(false)
  const mediaAspect = getMediaAspectRatio('linkedin', derivativeType)

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

      {/* Media — aspect ratio adapts to derivative type */}
      {(imageUrl || imageUrls?.length || videoUrl) && (
        <CarouselMedia imageUrl={imageUrl} imageUrls={imageUrls} videoUrl={videoUrl} aspectRatio={mediaAspect} />
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

function InstagramPreview({ caption, imageUrl, imageUrls, videoUrl, structuredHashtagCount, derivativeType }: {
  caption: string
  imageUrl?: string
  imageUrls?: string[]
  videoUrl?: string
  structuredHashtagCount: number
  derivativeType?: string
}) {
  const igSpec = getPlatform('instagram')
  const max = igSpec.captionMax
  const hashtagMax = igSpec.hashtagMax
  const inlineCount = countInlineHashtags(caption)
  const totalHashtags = structuredHashtagCount + inlineCount
  const overHashtags = totalHashtags > hashtagMax
  const mediaAspect = getMediaAspectRatio('instagram', derivativeType)
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

      {/* Media — aspect ratio adapts to derivative type */}
      {(imageUrl || imageUrls?.length || videoUrl)
        ? <CarouselMedia imageUrl={imageUrl} imageUrls={imageUrls} videoUrl={videoUrl} aspectRatio={mediaAspect} />
        : (
          <div style={{ width: '100%', aspectRatio: mediaAspect, background: A.surfaceAlt, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 24, opacity: 0.3 }}>🖼️</span>
          </div>
        )
      }

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

function GenericPreview({ caption, platform, imageUrl, imageUrls, videoUrl, derivativeType }: {
  caption: string; platform: string; imageUrl?: string; imageUrls?: string[]; videoUrl?: string; derivativeType?: string
}) {
  const max = getPlatform(platform).captionMax
  const overLimit = caption.length > max
  const aspectRatio = getMediaAspectRatio(platform, derivativeType)

  return (
    <div style={{ borderRadius: 8, border: `1px solid ${A.border}`, overflow: 'hidden', background: A.surface }}>
      {(videoUrl || imageUrl || (imageUrls && imageUrls.length > 0)) && (
        <CarouselMedia imageUrl={imageUrl} imageUrls={imageUrls} videoUrl={videoUrl} aspectRatio={aspectRatio} />
      )}
      <div style={{ padding: '8px 10px' }}>
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
    </div>
  )
}

interface PlatformPreviewProps {
  platform: string
  caption: string
  imageUrl?: string
  imageUrls?: string[]
  videoUrl?: string
  hashtagCount: number
  derivativeType?: string
}

export default function PlatformPreview({ platform, caption, imageUrl, imageUrls, videoUrl, hashtagCount, derivativeType }: PlatformPreviewProps) {
  const normalized = normalizePlatform(platform)

  return (
    <div>
      <p style={{ fontSize: 11, fontWeight: 500, color: A.textSoft, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        Platform Preview
      </p>
      {normalized === 'linkedin' && <LinkedInPreview caption={caption} imageUrl={imageUrl} imageUrls={imageUrls} videoUrl={videoUrl} derivativeType={derivativeType} />}
      {normalized === 'x' && <XPreview caption={caption} />}
      {normalized === 'instagram' && (
        <InstagramPreview caption={caption} imageUrl={imageUrl} imageUrls={imageUrls} videoUrl={videoUrl} structuredHashtagCount={hashtagCount} derivativeType={derivativeType} />
      )}
      {normalized !== 'linkedin' && normalized !== 'x' && normalized !== 'instagram' && (
        <GenericPreview caption={caption} platform={normalized} imageUrl={imageUrl} imageUrls={imageUrls} videoUrl={videoUrl} derivativeType={derivativeType} />
      )}
    </div>
  )
}
