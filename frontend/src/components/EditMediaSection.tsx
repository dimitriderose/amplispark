import { useState, useEffect } from 'react'
import { A } from '../theme'
import { api } from '../api/client'

interface EditMediaSectionProps {
  postId: string
  brandId: string
  imageUrl: string
  imageUrls?: string[]
  videoUrl?: string | null
  derivativeType?: string
  editCount?: number
  onImageUpdated: (newUrl: string, newEditCount: number) => void
}

export default function EditMediaSection({
  postId,
  brandId,
  imageUrl,
  imageUrls,
  videoUrl,
  derivativeType,
  editCount,
  onImageUpdated,
}: EditMediaSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [editPrompt, setEditPrompt] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isAccepted, setIsAccepted] = useState(false)
  const [beforeUrl, setBeforeUrl] = useState('')
  const [currentUrl, setCurrentUrl] = useState(imageUrl)
  const [localEditCount, setLocalEditCount] = useState(editCount ?? 0)
  const [editHistory, setEditHistory] = useState<string[]>([])
  const [activeSlide, setActiveSlide] = useState(0)
  const referenceSlide = 0

  // When switching slides, show the correct slide's image (reset edit state)
  useEffect(() => {
    const slideUrl = imageUrls ? imageUrls[activeSlide] : imageUrl
    setCurrentUrl(slideUrl)
    setBeforeUrl('')
  }, [activeSlide]) // eslint-disable-line react-hooks/exhaustive-deps

  const atLimit = localEditCount >= 8

  const handleEdit = async () => {
    if (!editPrompt.trim() || atLimit || isLoading) return
    setIsLoading(true)
    const prevUrl = currentUrl
    try {
      const result = await api.editPostMedia(brandId, postId, {
        edit_prompt: editPrompt,
        slide_index: derivativeType === 'carousel' ? activeSlide : undefined,
      }) as { image_url: string; edit_count: number }
      setBeforeUrl(prevUrl)
      setCurrentUrl(result.image_url)
      setLocalEditCount(result.edit_count)
      setEditHistory(h => [...h, editPrompt])
      setEditPrompt('')
      setIsAccepted(false)  // new edit arrived — require Accept again
    } catch (err) {
      console.error('Edit failed', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAccept = () => {
    onImageUpdated(currentUrl, localEditCount)
    setIsAccepted(true)
  }

  const handleUndo = () => {
    if (beforeUrl && beforeUrl !== currentUrl) {
      const newCount = Math.max(0, localEditCount - 1)
      setCurrentUrl(beforeUrl)
      setBeforeUrl('')
      setLocalEditCount(newCount)
      setEditHistory(h => h.slice(0, -1))
      onImageUpdated(beforeUrl, newCount)
    }
  }

  const handleReset = async () => {
    setIsLoading(true)
    try {
      const result = await api.resetPostMedia(brandId, postId) as { image_url: string }
      setCurrentUrl(result.image_url)
      setBeforeUrl('')
      setLocalEditCount(0)
      setEditHistory([])
      onImageUpdated(result.image_url, 0)
    } catch (err) {
      console.error('Reset failed', err)
    } finally {
      setIsLoading(false)
    }
  }

  const headerLabel = derivativeType === 'carousel'
    ? 'Edit Carousel'
    : videoUrl
    ? 'Edit Video'
    : 'Edit Image'

  const hasBeforeAfter = beforeUrl && beforeUrl !== currentUrl

  const editCountColor = localEditCount >= 8
    ? A.coral
    : localEditCount >= 5
    ? A.amber
    : A.textSoft

  return (
    <div style={{
      borderRadius: 10,
      border: `1px solid ${A.border}`,
      background: A.surface,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div
        onClick={() => setIsExpanded(v => !v)}
        style={{
          padding: '12px 16px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          userSelect: 'none',
        }}
      >
        <span style={{ fontSize: 14, fontWeight: 600, color: A.text }}>
          ✨ {headerLabel}
        </span>
        <span style={{ fontSize: 12, color: A.textSoft }}>
          {isExpanded ? '▴' : '▸'}
        </span>
      </div>

      {isExpanded && (
        <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Before / After display */}
          {hasBeforeAfter ? (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 120 }}>
                <div style={{ fontSize: 10, color: A.textMuted, marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>Original</div>
                {videoUrl
                  ? <video src={beforeUrl} controls muted loop style={{ width: '100%', borderRadius: 8, border: `1px solid ${A.border}`, maxHeight: 200 }} />
                  : <img src={beforeUrl} alt="Before" style={{ width: '100%', borderRadius: 8, border: `1px solid ${A.border}`, objectFit: 'contain', maxHeight: 200, background: A.surfaceAlt }} />
                }
              </div>
              <div style={{ flex: 1, minWidth: 120 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 10, color: A.indigo, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>Edited</span>
                  {isAccepted
                    ? <span style={{ fontSize: 10, color: A.green || '#22c55e', fontWeight: 600 }}>✓ Accepted</span>
                    : <button
                        onClick={handleAccept}
                        style={{
                          padding: '2px 8px', borderRadius: 5, border: 'none',
                          background: A.indigo, color: 'white',
                          fontSize: 11, fontWeight: 600, cursor: 'pointer',
                        }}
                      >
                        ✓ Accept
                      </button>
                  }
                </div>
                {videoUrl
                  ? <video src={currentUrl} controls muted loop style={{ width: '100%', borderRadius: 8, border: `1px solid ${A.indigo}`, maxHeight: 200 }} />
                  : <img src={currentUrl} alt="After" style={{ width: '100%', borderRadius: 8, border: `1px solid ${A.indigo}`, objectFit: 'contain', maxHeight: 200, background: A.surfaceAlt }} />
                }
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 10, color: A.textMuted, marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>Current</div>
              {videoUrl
                ? <video src={videoUrl} controls muted loop style={{ width: '100%', borderRadius: 8, border: `1px solid ${A.border}`, maxHeight: 200 }} />
                : <img src={currentUrl} alt="Current" style={{ width: '100%', borderRadius: 8, border: `1px solid ${A.border}`, objectFit: 'contain', maxHeight: 200, background: A.surfaceAlt }} />
              }
            </div>
          )}

          {/* Carousel slide selector */}
          {derivativeType === 'carousel' && imageUrls && imageUrls.length > 1 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: A.textSoft, marginRight: 4 }}>Slide:</span>
              {imageUrls.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveSlide(i)}
                  style={{
                    padding: '3px 8px',
                    borderRadius: 5,
                    border: `1px solid ${activeSlide === i ? A.indigo : A.border}`,
                    background: activeSlide === i ? A.indigoLight : 'transparent',
                    color: activeSlide === i ? A.indigo : A.textSoft,
                    fontSize: 12,
                    fontWeight: activeSlide === i ? 700 : 400,
                    cursor: 'pointer',
                  }}
                >
                  {i + 1}{i === referenceSlide ? ' ★' : ''}
                </button>
              ))}
            </div>
          )}

          {/* Edit history */}
          {editHistory.length > 0 && (
            <div style={{ background: A.surfaceAlt, borderRadius: 7, padding: '8px 10px' }}>
              <div style={{ fontSize: 11, color: A.textSoft, marginBottom: 4, fontWeight: 600 }}>Edit history</div>
              <ol style={{ margin: 0, paddingLeft: 16 }}>
                {editHistory.map((e, i) => (
                  <li key={i} style={{ fontSize: 11, color: A.textSoft, marginBottom: 2 }}>{e}</li>
                ))}
              </ol>
            </div>
          )}

          {/* Edit count badge */}
          <div style={{ fontSize: 12, color: editCountColor, fontWeight: atLimit ? 600 : 400 }}>
            {atLimit
              ? 'Edit limit reached. Reset to start fresh.'
              : `${localEditCount} of 8 edits used`}
          </div>

          {/* Quick edit presets */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {['Blur background', 'Warm up colors', 'Professional tone', 'Add brand logo space'].map(preset => (
              <button
                key={preset}
                onClick={() => setEditPrompt(preset)}
                disabled={atLimit || isLoading}
                style={{
                  fontSize: 11,
                  padding: '3px 8px',
                  borderRadius: 5,
                  border: `1px solid ${A.border}`,
                  background: 'transparent',
                  color: A.textSoft,
                  cursor: atLimit || isLoading ? 'not-allowed' : 'pointer',
                  opacity: atLimit || isLoading ? 0.5 : 1,
                }}
              >
                {preset}
              </button>
            ))}
          </div>

          {/* Text input + Send */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <textarea
              value={editPrompt}
              onChange={e => setEditPrompt(e.target.value)}
              placeholder="Describe your edit..."
              disabled={atLimit || isLoading}
              rows={2}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleEdit()
                }
              }}
              style={{
                flex: 1,
                padding: '8px 10px',
                borderRadius: 7,
                border: `1px solid ${A.border}`,
                fontSize: 13,
                color: A.text,
                background: A.surface,
                resize: 'vertical',
                fontFamily: 'inherit',
                opacity: atLimit ? 0.5 : 1,
              }}
            />
            <button
              onClick={handleEdit}
              disabled={!editPrompt.trim() || atLimit || isLoading}
              style={{
                padding: '8px 14px',
                borderRadius: 7,
                border: 'none',
                background: A.indigo,
                color: 'white',
                fontSize: 13,
                fontWeight: 600,
                cursor: !editPrompt.trim() || atLimit || isLoading ? 'not-allowed' : 'pointer',
                opacity: !editPrompt.trim() || atLimit || isLoading ? 0.6 : 1,
                whiteSpace: 'nowrap',
              }}
            >
              {isLoading ? '⏳' : 'Send'}
            </button>
          </div>

          {/* Action row */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={handleUndo}
              disabled={!hasBeforeAfter || isLoading}
              style={{
                padding: '6px 12px',
                borderRadius: 7,
                border: `1px solid ${A.border}`,
                background: 'transparent',
                color: A.textSoft,
                fontSize: 12,
                cursor: !hasBeforeAfter || isLoading ? 'not-allowed' : 'pointer',
                opacity: !hasBeforeAfter || isLoading ? 0.5 : 1,
              }}
            >
              ↩ Undo Last
            </button>
            <button
              onClick={handleReset}
              disabled={isLoading}
              style={{
                padding: '6px 12px',
                borderRadius: 7,
                border: `1px solid ${A.border}`,
                background: 'transparent',
                color: A.textSoft,
                fontSize: 12,
                cursor: isLoading ? 'not-allowed' : 'pointer',
                opacity: isLoading ? 0.5 : 1,
              }}
            >
              ↩ Reset to Original
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
