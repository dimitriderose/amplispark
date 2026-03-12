import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { api } from '../api/client'
import { getUid } from '../api/firebase'

interface UploadedFile {
  name: string
  type: string
  size: number
  file: File
}

type AnalysisStep = { label: string; icon: string }

const URL_STEPS: AnalysisStep[] = [
  { label: 'Crawling website...', icon: '🌐' },
  { label: 'Extracting brand colors', icon: '🎨' },
  { label: 'Analyzing tone of voice', icon: '✍️' },
  { label: 'Identifying target audience', icon: '👥' },
  { label: 'Scanning competitors', icon: '🔍' },
  { label: 'Building brand profile', icon: '✨' },
]

const NO_WEB_STEPS: AnalysisStep[] = [
  { label: 'Analyzing your description...', icon: '📝' },
  { label: 'Inferring brand personality', icon: '🎨' },
  { label: 'Identifying target audience', icon: '👥' },
  { label: 'Researching your market', icon: '🔍' },
  { label: 'Building brand profile', icon: '✨' },
]

export default function OnboardPage() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [desc, setDesc] = useState('')
  const [urlExpanded, setUrlExpanded] = useState(false)
  const [uploads, setUploads] = useState<UploadedFile[]>([])
  const [analyzing, setAnalyzing] = useState(false)
  const [completedSteps, setCompletedSteps] = useState<AnalysisStep[]>([])
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const urlInputRef = useRef<HTMLInputElement>(null)
  const isSubmittingRef = useRef(false)

  // Focus URL input when accordion expands
  useEffect(() => {
    if (urlExpanded) urlInputRef.current?.focus()
  }, [urlExpanded])

  const hasUrl = url.trim().length > 0
  const steps = hasUrl ? URL_STEPS : NO_WEB_STEPS
  const canSubmit = desc.length >= 20

  const handleFileAdd = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const valid = files.filter(f =>
      f.type.startsWith('image/') || f.type === 'application/pdf'
    ).slice(0, 3 - uploads.length)
    setUploads(prev => [...prev, ...valid.map(f => ({ name: f.name, type: f.type, size: f.size, file: f }))])
  }

  const handleSubmit = async () => {
    if (!canSubmit || isSubmittingRef.current) return
    isSubmittingRef.current = true
    setAnalyzing(true)
    setError('')
    setCompletedSteps([])
    setProgress(0)

    // Simulate analysis progress steps
    steps.forEach((step, idx) => {
      setTimeout(() => {
        setCompletedSteps(prev => [...prev, step])
        setProgress(((idx + 1) / steps.length) * 100)
      }, (idx + 1) * 800)
    })

    try {
      // Create brand record — attach user UID if signed in
      const uid = getUid()
      const { brand_id } = await api.createBrand({
        website_url: hasUrl ? url : null,
        description: desc,
        ...(uid ? { owner_uid: uid } : {}),
      }) as { brand_id: string }

      // Upload brand assets if any were selected
      if (uploads.length > 0) {
        const formData = new FormData()
        uploads.forEach(u => formData.append('files', u.file, u.name))
        api.uploadBrandAsset(brand_id, formData).catch(err =>
          console.error('Asset upload error:', err)
        )
      }

      // Wait for animation to mostly finish before navigating
      await new Promise(r => setTimeout(r, steps.length * 800 + 400))

      // Trigger analysis — fire-and-forget; dashboard polls analysis_status
      // Log failures so they're visible in the browser console for debugging
      api.analyzeBrand(brand_id, {
        website_url: hasUrl ? url : null,
        description: desc,
      }).catch(err => console.error('Brand analysis error (background):', err))

      navigate(`/dashboard/${brand_id}`)
    } catch (err: unknown) {
      setAnalyzing(false)
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      isSubmittingRef.current = false
    }
  }

  if (analyzing) {
    return (
      <div style={{
        minHeight: 'calc(100vh - 53px)', display: 'flex',
        alignItems: 'center', justifyContent: 'center', padding: '40px 24px',
      }}>
        <div style={{ maxWidth: 520, width: '100%' }}>
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: A.text, marginBottom: 6 }}>
              Building your brand profile
            </h2>
            <p style={{ fontSize: 13, color: A.textSoft }}>
              {hasUrl ? `Analyzing ${url}...` : 'Crafting your brand identity...'}
            </p>
          </div>

          {/* Progress bar */}
          <div style={{ height: 4, background: A.surfaceAlt, borderRadius: 2, overflow: 'hidden', marginBottom: 24 }}>
            <div style={{
              height: '100%', width: `${progress}%`,
              background: `linear-gradient(90deg, ${A.indigo}, ${A.violet})`,
              borderRadius: 2, transition: 'width 0.6s ease',
            }} />
          </div>

          {/* Steps */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {completedSteps.map((step, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px', borderRadius: 8,
                background: i === completedSteps.length - 1 && completedSteps.length < steps.length ? A.indigoLight : A.surface,
                border: `1px solid ${i === completedSteps.length - 1 && completedSteps.length < steps.length ? A.indigo + '30' : A.borderLight}`,
              }}>
                <span style={{ fontSize: 16 }}>{step.icon}</span>
                <span style={{ fontSize: 13, color: A.text, fontWeight: i === completedSteps.length - 1 && completedSteps.length < steps.length ? 500 : 400 }}>
                  {step.label}
                </span>
                {(i < completedSteps.length - 1 || completedSteps.length === steps.length) && (
                  <span style={{ marginLeft: 'auto', color: A.emerald, fontSize: 14 }}>✓</span>
                )}
              </div>
            ))}
            {/* M-1: Keep screen alive while API finishes after steps complete */}
            {completedSteps.length === steps.length && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px', borderRadius: 8,
                background: A.indigoLight, border: `1px solid ${A.indigo}30`,
              }}>
                <span style={{
                  display: 'inline-block', width: 12, height: 12, borderRadius: '50%',
                  background: A.indigo, flexShrink: 0,
                  animation: 'ob-pulse 1.2s ease-in-out infinite',
                }} />
                <span style={{ fontSize: 13, color: A.indigo, fontWeight: 500 }}>
                  Finalizing your brand profile...
                </span>
              </div>
            )}
          </div>
          <style>{`@keyframes ob-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.4;transform:scale(0.75)} }`}</style>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      minHeight: 'calc(100vh - 53px)', display: 'flex',
      alignItems: 'center', justifyContent: 'center', padding: '40px 24px',
    }}>
      <div style={{ maxWidth: 560, width: '100%' }}>
        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: A.text, marginBottom: 8 }}>
            Tell us about your brand
          </h1>
          <p style={{ fontSize: 15, color: A.textSoft }}>
            We'll analyze your brand and build a content strategy in under 2 minutes.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Description — primary input */}
          <div>
            <label htmlFor="desc-input" style={{ fontSize: 13, fontWeight: 500, color: A.text, display: 'block', marginBottom: 6 }}>
              Describe your business
              {/* M-2: Was "(0/20 min)" which read as "minutes" — clarified */}
              <span style={{ color: A.textMuted, fontWeight: 400, marginLeft: 8 }}>
                (min. 20 chars)
              </span>
            </label>
            <textarea
              id="desc-input"
              value={desc}
              onChange={e => setDesc(e.target.value)}
              placeholder="e.g. I run a family-owned Italian bakery in Austin. We specialize in sourdough and seasonal pastries, and our customers are local food enthusiasts who value craftsmanship."
              rows={4}
              autoFocus
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 8,
                border: `1px solid ${desc.length >= 20 ? A.emerald : A.border}`,
                fontSize: 14, color: A.text, background: A.surface,
                outline: 'none', resize: 'vertical', lineHeight: 1.5,
                transition: 'border-color 0.2s',
              }}
            />
            {desc.length > 0 && desc.length < 20 && (
              <p style={{ fontSize: 12, color: A.amber, marginTop: 4 }}>
                {20 - desc.length} more characters needed
              </p>
            )}
          </div>

          {/* Asset upload */}
          <div>
            <label style={{ fontSize: 13, fontWeight: 500, color: A.text, display: 'block', marginBottom: 6 }}>
              Brand assets <span style={{ color: A.textMuted, fontWeight: 400 }}>(optional — logo, photos, PDF brand guide)</span>
            </label>
            <div
              onClick={() => fileRef.current?.click()}
              style={{
                border: `2px dashed ${A.border}`, borderRadius: 8, padding: '20px 16px',
                textAlign: 'center', cursor: 'pointer', background: A.surfaceAlt,
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = A.indigo)}
              onMouseLeave={e => (e.currentTarget.style.borderColor = A.border)}
            >
              <span style={{ fontSize: 24 }}>📎</span>
              <p style={{ fontSize: 13, color: A.textSoft, marginTop: 8 }}>
                Drop files here or click to upload
              </p>
              <p style={{ fontSize: 12, color: A.textMuted, marginTop: 4 }}>
                JPG, PNG, PDF — max 3 files
              </p>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept="image/*,.pdf"
                onChange={handleFileAdd}
                style={{ display: 'none' }}
              />
            </div>

            {uploads.length > 0 && (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {uploads.map((f, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 12px', borderRadius: 6,
                    background: A.surface, border: `1px solid ${A.border}`,
                  }}>
                    <span style={{ fontSize: 16 }}>{f.type.includes('pdf') ? '📄' : '🖼️'}</span>
                    <span style={{ fontSize: 13, color: A.text, flex: 1 }}>{f.name}</span>
                    <button
                      onClick={() => setUploads(prev => prev.filter((_, j) => j !== i))}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: A.textMuted, fontSize: 16 }}
                    >×</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Website URL — collapsible enhancement */}
          <div style={{
            borderRadius: 8, border: `1px solid ${A.border}`,
            overflow: 'hidden',
          }}>
            <button
              onClick={() => setUrlExpanded(v => {
                if (v) setUrl('')  // clear URL when collapsing
                return !v
              })}
              aria-expanded={urlExpanded}
              aria-controls="url-panel"
              style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '12px 14px', background: urlExpanded ? A.indigoLight : A.surfaceAlt,
                border: 'none', cursor: 'pointer', color: urlExpanded ? A.indigo : A.textSoft,
                fontSize: 13, fontWeight: urlExpanded ? 500 : 400,
                transition: 'background 0.2s, color 0.2s',
              }}
            >
              <span>🌐 Have a website? Paste it for even better results</span>
              <span aria-hidden="true" style={{ fontSize: 11, opacity: 0.7 }}>{urlExpanded ? '▲' : '▼'}</span>
            </button>

            {urlExpanded && (
              <div id="url-panel" style={{ padding: '12px 14px', borderTop: `1px solid ${A.border}` }}>
                <label htmlFor="url-input" style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, display: 'block', marginBottom: 6 }}>
                  Website URL
                </label>
                <input
                  id="url-input"
                  ref={urlInputRef}
                  type="url"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://yourbusiness.com"
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 8,
                    border: `1px solid ${hasUrl ? A.indigo : A.border}`,
                    fontSize: 14, color: A.text,
                    background: A.surface, outline: 'none',
                    transition: 'border-color 0.2s',
                  }}
                />
                {hasUrl && (
                  <p style={{ fontSize: 12, color: A.indigo, marginTop: 6 }}>
                    ✓ We'll crawl your site for colors, tone, and competitors
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div style={{
              padding: '10px 14px', borderRadius: 8,
              background: '#FFF0F0', border: `1px solid ${A.coral}30`,
              fontSize: 13, color: A.coral,
            }}>
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            style={{
              padding: '14px', borderRadius: 10, border: 'none', cursor: canSubmit ? 'pointer' : 'not-allowed',
              background: canSubmit
                ? `linear-gradient(135deg, ${A.indigo}, ${A.violet})`
                : A.surfaceAlt,
              color: canSubmit ? 'white' : A.textMuted,
              fontSize: 15, fontWeight: 600, transition: 'all 0.2s',
            }}
          >
            {hasUrl ? 'Analyze My Brand →' : 'Build My Brand Profile →'}
          </button>
        </div>
      </div>
    </div>
  )
}
