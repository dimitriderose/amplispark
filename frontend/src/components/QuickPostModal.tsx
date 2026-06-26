import { useState, useRef, useEffect, useCallback } from 'react'
import { A } from '../theme'
import { PLATFORMS } from '../platformRegistry'
import { PLATFORM_FORMATS, FORMAT_LABELS } from '../constants/platformFormats'
import { IMAGE_STYLE_GROUPS, styleLabel } from '../imageStyleOptions'
import { usePostGeneration } from '../hooks/usePostGeneration'
import PostGenerator from './PostGenerator'
import ReviewPanel from './ReviewPanel'
import GenerationToast from './ui/GenerationToast'
import { api } from '../api/client'

interface Props {
  brandId: string
  brand: { selected_platforms?: string[] | null; default_image_style?: string | null }
  onClose: () => void
  initialPlatform?: string
  initialContentType?: string
}

export default function QuickPostModal({ brandId, brand, onClose, initialPlatform, initialContentType }: Props) {
  const rawPlatforms = brand.selected_platforms?.filter(p => PLATFORMS[p]) ?? []
  const platforms = rawPlatforms.length > 0 ? rawPlatforms : Object.keys(PLATFORMS)
  const firstPlatform = initialPlatform && platforms.includes(initialPlatform) ? initialPlatform : (platforms[0] ?? 'instagram')

  const [selectedPlatform, setSelectedPlatform] = useState(firstPlatform)
  const [brief, setBrief] = useState('')
  const [imageStyle, setImageStyle] = useState(brand.default_image_style ?? '')
  const [showStyleMenu, setShowStyleMenu] = useState(false)
  const styleMenuRef = useRef<HTMLDivElement>(null)

  const platformFormats = PLATFORM_FORMATS[selectedPlatform] ?? ['original']
  const getInitialFormat = useCallback((platform: string, contentType?: string) => {
    const fmts = PLATFORM_FORMATS[platform] ?? ['original']
    if (contentType && fmts.includes(contentType)) return contentType
    return fmts[0]
  }, [])

  const [selectedFormat, setSelectedFormat] = useState(() => getInitialFormat(firstPlatform, initialContentType))

  useEffect(() => {
    setSelectedFormat(getInitialFormat(selectedPlatform))
  }, [selectedPlatform, getInitialFormat])

  useEffect(() => {
    if (!showStyleMenu) return
    const handle = (e: MouseEvent) => {
      if (styleMenuRef.current && !styleMenuRef.current.contains(e.target as Node)) {
        setShowStyleMenu(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [showStyleMenu])

  const { state, generateAdhoc, reset } = usePostGeneration()
  const generationStatus = state.status

  const [toastVisible, setToastVisible] = useState(false)
  const toastShownRef = useRef(false)
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    }
  }, [])

  useEffect(() => {
    if (state.status === 'idle') {
      toastShownRef.current = false
      setToastVisible(false)
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current)
        toastTimerRef.current = null
      }
    }
    if (state.status === 'generating' && !toastShownRef.current) {
      toastShownRef.current = true
      toastTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return
        setToastVisible(true)
        toastTimerRef.current = setTimeout(() => {
          if (mountedRef.current) setToastVisible(false)
        }, 5000)
      }, 0)
    }
  }, [state.status])

  const dismissToast = () => {
    setToastVisible(false)
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
  }

  const handleGenerate = () => {
    generateAdhoc(brandId, selectedPlatform, selectedFormat, brief || undefined, imageStyle || undefined)
  }

  const handleClose = () => {
    if (generationStatus === 'generating') {
      if (!window.confirm('Generation is in progress. Close anyway?')) return
    }
    reset()
    onClose()
  }

  const handleApprove = async () => {
    if (!state.postId) return
    try {
      await api.approvePost(brandId, state.postId)
      onClose()
    } catch {
      // ReviewPanel handles its own approval flow; this path is a fallback
    }
  }

  const platformSpec = PLATFORMS[selectedPlatform]
  const formatLabel = FORMAT_LABELS[selectedFormat]?.label ?? selectedFormat
  const isGenerating = generationStatus !== 'idle'

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.5)',
        zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) handleClose() }}
    >
      {toastVisible && <GenerationToast onDismiss={dismissToast} />}
      <div style={{
        background: A.bg,
        borderRadius: 12,
        border: `1px solid ${A.border}`,
        width: '100%',
        maxWidth: isGenerating ? 720 : 520,
        maxHeight: '90vh',
        overflowY: 'auto',
        transition: 'max-width 0.25s ease',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 20px 14px',
          borderBottom: `1px solid ${A.border}`,
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: A.text }}>New Post</h2>
            {isGenerating && (
              <p style={{ margin: '2px 0 0', fontSize: 12, color: A.textSoft }}>
                {platformSpec?.displayName ?? selectedPlatform} · {formatLabel}
              </p>
            )}
          </div>
          <button
            onClick={handleClose}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              fontSize: 20, color: A.textMuted, lineHeight: 1, padding: '4px 8px',
            }}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {!isGenerating && (
          <div style={{ padding: '20px 20px 24px' }}>
            <div style={{ marginBottom: 16 }}>
              <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: A.textSoft }}>Platform</p>
              <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                {platforms.map(key => {
                  const spec = PLATFORMS[key]
                  if (!spec) return null
                  const Icon = spec.icon
                  const isActive = selectedPlatform === key
                  return (
                    <button
                      key={key}
                      onClick={() => setSelectedPlatform(key)}
                      title={spec.displayName}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '6px 12px', borderRadius: 20, cursor: 'pointer',
                        border: isActive ? `2px solid ${A.indigo}` : `1px solid ${A.border}`,
                        background: isActive ? `${A.indigo}10` : A.surface,
                        color: isActive ? A.indigo : A.textSoft,
                        fontSize: 12, fontWeight: isActive ? 600 : 400,
                        flexShrink: 0, transition: 'all 0.15s',
                      }}
                    >
                      <Icon size={14} color={spec.color} />
                      <span>{spec.displayName}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {platformFormats.length > 1 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: A.textSoft }}>Format</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {platformFormats.map(fmt => {
                    const fmtSpec = FORMAT_LABELS[fmt]
                    if (!fmtSpec) return null
                    const Icon = fmtSpec.icon
                    const isActive = selectedFormat === fmt
                    return (
                      <button
                        key={fmt}
                        onClick={() => setSelectedFormat(fmt)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 5,
                          padding: '5px 10px', borderRadius: 16, cursor: 'pointer',
                          border: isActive ? `2px solid ${A.indigo}` : `1px solid ${A.border}`,
                          background: isActive ? `${A.indigo}10` : A.surface,
                          color: isActive ? A.indigo : A.textSoft,
                          fontSize: 12, fontWeight: isActive ? 600 : 400,
                          transition: 'all 0.15s',
                        }}
                      >
                        <Icon size={13} />
                        {fmtSpec.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: A.textSoft, marginBottom: 6 }}>
                What do you want to post about?
              </label>
              <textarea
                value={brief}
                onChange={e => setBrief(e.target.value)}
                placeholder="e.g. our new product launch, a behind-the-scenes moment, a client win..."
                rows={4}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 8,
                  border: `1px solid ${A.border}`, fontSize: 13, color: A.text,
                  background: A.surface, outline: 'none', resize: 'none',
                  boxSizing: 'border-box', fontFamily: 'inherit', lineHeight: 1.5,
                }}
              />
              <p style={{ margin: '4px 0 0', fontSize: 11, color: A.textMuted }}>
                The more context you give, the better the result.
              </p>
            </div>

            <div style={{ marginBottom: 20 }}>
              <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: A.textSoft }}>Visual Style</p>
              <div ref={styleMenuRef} style={{ position: 'relative' }}>
                <button
                  onClick={() => setShowStyleMenu(prev => !prev)}
                  aria-haspopup="listbox"
                  aria-expanded={showStyleMenu}
                  style={{
                    padding: '6px 10px', borderRadius: 6,
                    border: `1px solid ${imageStyle ? A.indigo + '40' : A.border}`,
                    background: imageStyle ? `${A.indigo}08` : A.surface,
                    color: imageStyle ? A.indigo : A.textSoft,
                    fontSize: 12, fontWeight: 500, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 5,
                  }}
                >
                  <span style={{ fontSize: 12 }}>✦</span>
                  Visual Style: {imageStyle ? styleLabel(imageStyle) : 'Auto'}
                  <span style={{ fontSize: 9, opacity: 0.6 }}>▾</span>
                </button>

                {showStyleMenu && (
                  <div
                    role="listbox"
                    aria-label="Visual style"
                    style={{
                      position: 'absolute', top: '100%', left: 0, minWidth: 260,
                      marginTop: 4, borderRadius: 8,
                      background: A.surface, border: `1px solid ${A.border}`,
                      boxShadow: '0 8px 24px rgba(0,0,0,0.14)', zIndex: 50,
                      maxHeight: 320, overflowY: 'auto', padding: '4px 0',
                    }}
                  >
                    <div
                      role="option"
                      aria-selected={!imageStyle}
                      onClick={() => { setImageStyle(''); setShowStyleMenu(false) }}
                      style={{
                        padding: '7px 12px', cursor: 'pointer', fontSize: 12,
                        color: !imageStyle ? A.indigo : A.text,
                        fontWeight: !imageStyle ? 600 : 400,
                        background: !imageStyle ? `${A.indigo}08` : 'transparent',
                        display: 'flex', alignItems: 'center', gap: 6,
                      }}
                    >
                      <span style={{ width: 16, fontSize: 11, color: A.indigo }}>{!imageStyle ? '✓' : ''}</span>
                      Auto
                    </div>

                    {IMAGE_STYLE_GROUPS.map(group => (
                      <div key={group.label}>
                        <div style={{
                          padding: '8px 12px 3px',
                          fontSize: 10, fontWeight: 600,
                          color: A.textMuted, textTransform: 'uppercase', letterSpacing: 0.5,
                        }}>
                          {group.label}
                        </div>
                        {group.options.map(opt => (
                          <div
                            key={opt.value}
                            role="option"
                            aria-selected={imageStyle === opt.value}
                            onClick={() => { setImageStyle(opt.value); setShowStyleMenu(false) }}
                            style={{
                              padding: '6px 12px', cursor: 'pointer', fontSize: 12,
                              color: imageStyle === opt.value ? A.indigo : A.text,
                              fontWeight: imageStyle === opt.value ? 600 : 400,
                              background: imageStyle === opt.value ? `${A.indigo}08` : 'transparent',
                              display: 'flex', alignItems: 'center', gap: 6,
                            }}
                            onMouseEnter={e => {
                              if (imageStyle !== opt.value) e.currentTarget.style.background = '#f5f5ff'
                            }}
                            onMouseLeave={e => {
                              if (imageStyle !== opt.value) e.currentTarget.style.background = 'transparent'
                            }}
                          >
                            <span style={{ width: 16, fontSize: 11, color: A.indigo }}>
                              {imageStyle === opt.value ? '✓' : ''}
                            </span>
                            <div>
                              <div>{opt.label}</div>
                              <div style={{ fontSize: 10, color: A.textMuted }}>{opt.desc}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={!selectedPlatform}
              style={{
                width: '100%', padding: '11px 0', borderRadius: 8, border: 'none',
                background: selectedPlatform
                  ? `linear-gradient(135deg, ${A.indigo}, ${A.violet})`
                  : A.surfaceAlt,
                color: selectedPlatform ? 'white' : A.textMuted,
                fontSize: 14, fontWeight: 600,
                cursor: selectedPlatform ? 'pointer' : 'not-allowed',
              }}
            >
              Generate Post
            </button>
          </div>
        )}

        {isGenerating && (
          <div style={{ padding: '20px 20px 24px' }}>
            <PostGenerator
              state={state}
              brandId={brandId}
              dayBrief={{
                platform: selectedPlatform,
                pillar: '',
                content_theme: brief,
                derivative_type: selectedFormat,
              }}
              onRegenerate={() => {
                handleGenerate()
              }}
            />

            {state.status === 'complete' && state.postId && (
              <div style={{ marginTop: 24 }}>
                <ReviewPanel
                  brandId={brandId}
                  postId={state.postId}
                  initialReview={state.review as import('./ReviewPanel').ReviewResult | null}
                  onApproved={handleApprove}
                />
              </div>
            )}

            {state.status === 'error' && (
              <div style={{ marginTop: 16 }}>
                <button
                  onClick={() => reset()}
                  style={{
                    padding: '8px 16px', borderRadius: 8,
                    border: `1px solid ${A.border}`, background: 'transparent',
                    color: A.textSoft, fontSize: 13, cursor: 'pointer',
                  }}
                >
                  Start Over
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
