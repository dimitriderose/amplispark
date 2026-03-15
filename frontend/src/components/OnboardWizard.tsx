import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { api } from '../api/client'
import { getUid } from '../api/firebase'
import { useWizardState } from '../hooks/useWizardState'
import { useIsMobile } from '../hooks/useIsMobile'
import { PLATFORMS } from '../platformRegistry'

/* ── Analysis animation steps (reused from original OnboardPage) ── */

interface AnalysisStep { label: string; icon: string }

const URL_STEPS: AnalysisStep[] = [
  { label: 'Crawling website...', icon: '\u{1F310}' },
  { label: 'Extracting brand colors', icon: '\u{1F3A8}' },
  { label: 'Analyzing tone of voice', icon: '\u{270D}\u{FE0F}' },
  { label: 'Identifying target audience', icon: '\u{1F465}' },
  { label: 'Scanning competitors', icon: '\u{1F50D}' },
  { label: 'Building brand profile', icon: '\u{2728}' },
  { label: 'Generating content calendar', icon: '\u{1F4C5}' },
]

const NO_WEB_STEPS: AnalysisStep[] = [
  { label: 'Analyzing your description...', icon: '\u{1F4DD}' },
  { label: 'Inferring brand personality', icon: '\u{1F3A8}' },
  { label: 'Identifying target audience', icon: '\u{1F465}' },
  { label: 'Researching your market', icon: '\u{1F50D}' },
  { label: 'Building brand profile', icon: '\u{2728}' },
  { label: 'Generating content calendar', icon: '\u{1F4C5}' },
]

/* ── Wizard component ── */

export default function OnboardWizard() {
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const { step, data, update, next, back, canAdvance, clear } = useWizardState()

  // Analyzing state
  const [analyzing, setAnalyzing] = useState(false)
  const [completedSteps, setCompletedSteps] = useState<AnalysisStep[]>([])
  const [progress, setProgress] = useState(0)
  const [_error, setError] = useState('')
  const isSubmittingRef = useRef(false)

  // Color picker state
  const [newColor, setNewColor] = useState('#5B5FF6')

  // Logo/asset file refs
  const logoRef = useRef<HTMLInputElement>(null)
  const assetRef = useRef<HTMLInputElement>(null)

  const hasUrl = data.websiteUrl.trim().length > 0
  const steps = hasUrl ? URL_STEPS : NO_WEB_STEPS

  /* ── Create brand handler (step 3 final) ── */
  // Store timer IDs for cleanup on unmount/error
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([])
  useEffect(() => () => { timersRef.current.forEach(clearTimeout) }, [])

  // Use ref to avoid recreating handleGenerate on every keystroke (#11 fix)
  const dataRef = useRef(data)
  dataRef.current = data

  const handleGenerate = useCallback(async () => {
    if (isSubmittingRef.current) return
    isSubmittingRef.current = true
    const d = dataRef.current
    const _hasUrl = d.websiteUrl.trim().length > 0
    const _steps = _hasUrl ? URL_STEPS : NO_WEB_STEPS

    setAnalyzing(true)
    setError('')
    setCompletedSteps([])
    setProgress(0)

    // Clear any prior timers
    timersRef.current.forEach(clearTimeout)
    timersRef.current = []

    // Animate progress steps
    _steps.forEach((s, idx) => {
      const id = setTimeout(() => {
        setCompletedSteps(prev => [...prev, s])
        setProgress(((idx + 1) / _steps.length) * 100)
      }, (idx + 1) * 800)
      timersRef.current.push(id)
    })

    // Timeout: if pre-navigation steps take >2 min, abort and show error (#2 fix)
    const timeoutId = setTimeout(() => {
      if (isSubmittingRef.current) {
        timersRef.current.forEach(clearTimeout)
        timersRef.current = []
        setAnalyzing(false)
        setError('Setup is taking longer than expected. Your brand was created — check the dashboard.')
        isSubmittingRef.current = false
      }
    }, 120_000)
    timersRef.current.push(timeoutId)

    try {
      const uid = getUid()

      // 1. Create brand
      const { brand_id } = await api.createBrand({
        business_name: d.businessName,
        description: d.description,
        website_url: _hasUrl ? d.websiteUrl : null,
        industry: d.industry || null,
        ...(uid ? { owner_uid: uid } : {}),
      }) as { brand_id: string }

      // 2. Update with extra fields from steps 2-3
      await api.updateBrand(brand_id, {
        tone: d.tone || null,
        target_audience: d.targetAudience || null,
        colors: d.colors.length > 0 ? d.colors : null,
        platform_mode: d.platformMode,
        selected_platforms: d.platformMode === 'manual' ? d.selectedPlatforms : [],
      })

      // 3. Upload logo separately, then assets
      if (d.logoFile) {
        const logoForm = new FormData()
        logoForm.append('files', d.logoFile, d.logoFile.name)
        const logoRes = await api.uploadBrandAsset(brand_id, logoForm).catch(err => {
          console.error('Logo upload error:', err)
          return null
        })
        if (logoRes?.uploaded?.[0]) {
          await api.setBrandLogo(brand_id, logoRes.uploaded[0].url).catch(err =>
            console.error('Set logo error:', err)
          )
        }
      }
      if (d.assets.length > 0) {
        const assetForm = new FormData()
        d.assets.forEach(f => assetForm.append('files', f, f.name))
        await api.uploadBrandAsset(brand_id, assetForm).catch(err =>
          console.error('Asset upload error:', err)
        )
      }

      // 4. Trigger analysis — await so we know if it fails (#10 fix)
      await api.analyzeBrand(brand_id, {
        website_url: _hasUrl ? d.websiteUrl : null,
        description: d.description,
      }).catch(err => {
        // Non-fatal: dashboard polls analysis_status, but log prominently
        console.warn('Brand analysis failed — dashboard will show unanalyzed brand:', err)
      })

      // 5. Wait for animation to finish (runs in parallel with API calls)
      await new Promise(r => setTimeout(r, _steps.length * 800 + 400))

      clearTimeout(timeoutId)
      clear() // Clear persisted wizard data
      navigate(`/dashboard/${brand_id}`)
    } catch (err: unknown) {
      clearTimeout(timeoutId)
      timersRef.current.forEach(clearTimeout)
      timersRef.current = []
      setAnalyzing(false)
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      isSubmittingRef.current = false
    }
  }, [navigate, clear]) // #11 fix: no longer depends on `data` — reads from ref

  /* ── Analyzing overlay ── */
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
              {hasUrl ? `Analyzing ${data.websiteUrl}...` : 'Crafting your brand identity...'}
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
            {completedSteps.map((s, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px', borderRadius: 8,
                background: i === completedSteps.length - 1 && completedSteps.length < steps.length ? A.indigoLight : A.surface,
                border: `1px solid ${i === completedSteps.length - 1 && completedSteps.length < steps.length ? A.indigo + '30' : A.borderLight}`,
              }}>
                <span style={{ fontSize: 16 }}>{s.icon}</span>
                <span style={{ fontSize: 13, color: A.text, fontWeight: i === completedSteps.length - 1 && completedSteps.length < steps.length ? 500 : 400 }}>
                  {s.label}
                </span>
                {(i < completedSteps.length - 1 || completedSteps.length === steps.length) && (
                  <span style={{ marginLeft: 'auto', color: A.emerald, fontSize: 14 }}>{'\u2713'}</span>
                )}
              </div>
            ))}
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

  /* ── Step content renderer ── */
  const renderStep = () => {
    switch (step) {
      case 1: return renderStep1()
      case 2: return renderStep2()
      case 3: return renderStep3()
      default: return null
    }
  }

  /* ── Step 1: Tell us about your business ── */
  function renderStep1() {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Business Name */}
        <div>
          <label style={labelStyle}>
            Business Name <span style={{ color: A.coral, fontWeight: 400 }}>*</span>
          </label>
          <input
            value={data.businessName}
            onChange={e => update('businessName', e.target.value)}
            placeholder="e.g. Sunrise Bakery"
            autoFocus
            style={{
              ...inputStyle,
              borderColor: data.businessName.trim() ? A.emerald : A.border,
            }}
          />
        </div>

        {/* Description */}
        <div>
          <label style={labelStyle}>
            Describe your business <span style={{ color: A.coral, fontWeight: 400 }}>*</span>
            <span style={{ color: A.textMuted, fontWeight: 400, marginLeft: 8 }}>
              (min. 20 chars)
            </span>
          </label>
          <textarea
            value={data.description}
            onChange={e => update('description', e.target.value)}
            placeholder="e.g. I run a family-owned Italian bakery in Austin. We specialize in sourdough and seasonal pastries, and our customers are local food enthusiasts who value craftsmanship."
            rows={4}
            style={{
              ...inputStyle,
              resize: 'vertical' as const,
              lineHeight: 1.5,
              borderColor: data.description.length >= 20 ? A.emerald : A.border,
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            {data.description.length > 0 && data.description.length < 20 ? (
              <p style={{ fontSize: 12, color: A.amber, margin: 0 }}>
                {20 - data.description.length} more characters needed
              </p>
            ) : <span />}
            <p style={{ fontSize: 11, color: A.textMuted, margin: 0 }}>
              {data.description.length} / 20
            </p>
          </div>
        </div>

        {/* Website URL */}
        <div>
          <label style={labelStyle}>
            Website URL <span style={{ color: A.textMuted, fontWeight: 400 }}>(optional)</span>
          </label>
          <input
            value={data.websiteUrl}
            onChange={e => update('websiteUrl', e.target.value)}
            placeholder="https://yourbusiness.com"
            type="url"
            style={{
              ...inputStyle,
              borderColor: hasUrl ? A.indigo : A.border,
            }}
          />
          <p style={{ fontSize: 11, color: A.textMuted, marginTop: 4 }}>
            Helps us analyze your brand deeper — colors, tone, competitors
          </p>
        </div>

        {/* Industry */}
        <div>
          <label style={labelStyle}>
            Industry <span style={{ color: A.textMuted, fontWeight: 400 }}>(optional)</span>
          </label>
          <input
            value={data.industry}
            onChange={e => update('industry', e.target.value)}
            placeholder="e.g. Food & Beverage, SaaS, Fashion"
            style={inputStyle}
          />
        </div>
      </div>
    )
  }

  /* ── Step 2: Your brand identity ── */
  function renderStep2() {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Tone */}
        <div>
          <label style={labelStyle}>Tone of Voice</label>
          <input
            value={data.tone}
            onChange={e => update('tone', e.target.value)}
            placeholder="e.g. professional, friendly, bold"
            autoFocus
            style={inputStyle}
          />
        </div>

        {/* Target Audience */}
        <div>
          <label style={labelStyle}>Target Audience</label>
          <input
            value={data.targetAudience}
            onChange={e => update('targetAudience', e.target.value)}
            placeholder="e.g. small business owners, non-profit leaders"
            style={inputStyle}
          />
        </div>

        {/* Brand Colors */}
        <div>
          <label style={labelStyle}>Brand Colors</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
            {data.colors.map((c, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 6, background: c,
                  border: `1px solid ${A.border}`, cursor: 'pointer',
                }} title={c} />
                <button
                  onClick={() => update('colors', data.colors.filter((_, j) => j !== i))}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: A.textMuted, fontSize: 14, padding: 0,
                  }}
                >x</button>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              type="color"
              value={newColor}
              onChange={e => setNewColor(e.target.value)}
              style={{ width: 32, height: 28, border: 'none', cursor: 'pointer', padding: 0 }}
            />
            <button
              onClick={() => {
                if (!data.colors.includes(newColor)) update('colors', [...data.colors, newColor])
              }}
              style={{
                padding: '4px 10px', borderRadius: 6, border: `1px solid ${A.border}`,
                background: 'transparent', cursor: 'pointer', fontSize: 12, color: A.textSoft,
              }}
            >+ Add</button>
          </div>
        </div>

        {/* Logo Upload */}
        <div>
          <label style={labelStyle}>Logo</label>
          {data.logoFile ? (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
              borderRadius: 8, background: A.surface, border: `1px solid ${A.border}`,
            }}>
              <span style={{ fontSize: 20 }}>{'\u{1F5BC}\u{FE0F}'}</span>
              <span style={{ fontSize: 13, color: A.text, flex: 1 }}>{data.logoFile.name}</span>
              <button
                onClick={() => update('logoFile', null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: A.textMuted, fontSize: 16 }}
              >{'\u00D7'}</button>
            </div>
          ) : (
            <div
              onClick={() => logoRef.current?.click()}
              style={{
                border: `2px dashed ${A.border}`, borderRadius: 8, padding: '16px',
                textAlign: 'center', cursor: 'pointer', background: A.surfaceAlt,
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = A.indigo)}
              onMouseLeave={e => (e.currentTarget.style.borderColor = A.border)}
            >
              <p style={{ fontSize: 13, color: A.textSoft }}>Click to upload logo</p>
              <p style={{ fontSize: 12, color: A.textMuted, marginTop: 4 }}>JPG, PNG</p>
            </div>
          )}
          <input
            ref={logoRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={e => {
              const f = e.target.files?.[0]
              if (f && f.size > 10 * 1024 * 1024) {
                setError('Logo must be under 10 MB')
                e.target.value = ''
                return
              }
              if (f) update('logoFile', f)
              e.target.value = ''
            }}
          />
        </div>

        {/* Extra assets */}
        <div>
          <label style={labelStyle}>
            Brand assets <span style={{ color: A.textMuted, fontWeight: 400 }}>(optional — photos, PDF brand guide)</span>
          </label>
          <div
            onClick={() => assetRef.current?.click()}
            style={{
              border: `2px dashed ${A.border}`, borderRadius: 8, padding: '16px',
              textAlign: 'center', cursor: 'pointer', background: A.surfaceAlt,
              transition: 'border-color 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = A.indigo)}
            onMouseLeave={e => (e.currentTarget.style.borderColor = A.border)}
          >
            <p style={{ fontSize: 13, color: A.textSoft }}>Click to upload files</p>
            <p style={{ fontSize: 12, color: A.textMuted, marginTop: 4 }}>JPG, PNG, PDF — max 3 files</p>
          </div>
          <input
            ref={assetRef}
            type="file"
            multiple
            accept="image/*,.pdf"
            style={{ display: 'none' }}
            onChange={e => {
              const files = Array.from(e.target.files || [])
              const valid = files
                .filter(f => f.type.startsWith('image/') || f.type === 'application/pdf')
                .filter(f => {
                  if (f.size > 10 * 1024 * 1024) { setError('Files must be under 10 MB each'); return false }
                  return true
                })
                .slice(0, 3 - data.assets.length)
              if (valid.length > 0) update('assets', [...data.assets, ...valid].slice(0, 3))
              e.target.value = ''
            }}
          />
          {data.assets.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {data.assets.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px', borderRadius: 6,
                  background: A.surface, border: `1px solid ${A.border}`,
                }}>
                  <span style={{ fontSize: 16 }}>{f.type.includes('pdf') ? '\u{1F4C4}' : '\u{1F5BC}\u{FE0F}'}</span>
                  <span style={{ fontSize: 13, color: A.text, flex: 1 }}>{f.name}</span>
                  <button
                    onClick={() => update('assets', data.assets.filter((_, j) => j !== i))}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: A.textMuted, fontSize: 16 }}
                  >{'\u00D7'}</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  /* ── Step 3: Where do you post? ── */
  function renderStep3() {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Mode toggle */}
        <div style={{ display: 'flex', gap: 4, background: A.surfaceAlt, borderRadius: 8, padding: 3 }}>
          {([
            { key: 'ai' as const, label: 'Let AI choose platforms' },
            { key: 'manual' as const, label: "I'll select my platforms" },
          ]).map(opt => (
            <button
              key={opt.key}
              onClick={() => update('platformMode', opt.key)}
              style={{
                flex: 1, padding: '10px 12px', borderRadius: 6, border: 'none',
                cursor: 'pointer', fontSize: 13, fontWeight: data.platformMode === opt.key ? 600 : 400,
                background: data.platformMode === opt.key ? A.surface : 'transparent',
                color: data.platformMode === opt.key ? A.indigo : A.textSoft,
                boxShadow: data.platformMode === opt.key ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {data.platformMode === 'ai' ? (
          <div style={{
            padding: '16px', borderRadius: 10, background: A.indigoLight,
            border: `1px solid ${A.indigo}20`,
          }}>
            <p style={{ fontSize: 14, fontWeight: 500, color: A.indigo, marginBottom: 4 }}>
              AI-powered platform selection
            </p>
            <p style={{ fontSize: 12, color: A.textSoft, lineHeight: 1.5 }}>
              We'll analyze your brand and automatically select the 2-4 best platforms for your content strategy.
            </p>
          </div>
        ) : (
          <>
            <p style={{ fontSize: 12, color: A.textMuted, lineHeight: 1.5 }}>
              Choose which platforms to include in your content plans.
            </p>
            <div style={{
              display: 'grid',
              gridTemplateColumns: isMobile ? 'repeat(2, 1fr)' : 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: 8,
            }}>
              {Object.values(PLATFORMS).map(spec => {
                const Icon = spec.icon
                const isSelected = data.selectedPlatforms.includes(spec.key)
                return (
                  <button
                    key={spec.key}
                    onClick={() => {
                      update(
                        'selectedPlatforms',
                        isSelected
                          ? data.selectedPlatforms.filter(k => k !== spec.key)
                          : [...data.selectedPlatforms, spec.key],
                      )
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '10px 12px', borderRadius: 8,
                      border: `1.5px solid ${isSelected ? spec.color : A.border}`,
                      background: isSelected ? spec.color + '12' : 'transparent',
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}
                  >
                    <Icon size={16} color={isSelected ? spec.color : A.textMuted} />
                    <span style={{
                      fontSize: 12, fontWeight: isSelected ? 600 : 400,
                      color: isSelected ? spec.color : A.textSoft,
                    }}>
                      {spec.displayName}
                    </span>
                  </button>
                )
              })}
            </div>
          </>
        )}
      </div>
    )
  }

  /* ── Step titles ── */
  const STEP_TITLES = [
    'Tell us about your business',
    'Your brand identity',
    'Where do you post?',
  ]

  /* ── Main render ── */
  return (
    <div style={{
      minHeight: 'calc(100vh - 53px)', display: 'flex',
      alignItems: 'center', justifyContent: 'center', padding: '40px 24px',
    }}>
      <div style={{ maxWidth: 560, width: '100%' }}>
        {/* Progress indicator */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <p style={{ fontSize: 12, fontWeight: 500, color: A.textMuted, margin: 0, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Step {step} of 3
            </p>
            {step > 1 && (
              <button
                onClick={back}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: 13, color: A.textSoft, padding: 0,
                }}
              >
                {'\u2190'} Back
              </button>
            )}
          </div>

          {/* Dots */}
          <div style={{ display: 'flex', gap: 6 }}>
            {[1, 2, 3].map(i => (
              <div
                key={i}
                style={{
                  flex: 1, height: 4, borderRadius: 2,
                  background: i <= step
                    ? `linear-gradient(90deg, ${A.indigo}, ${A.violet})`
                    : A.surfaceAlt,
                  transition: 'background 0.3s ease',
                }}
              />
            ))}
          </div>
        </div>

        {/* Title */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: isMobile ? 22 : 28, fontWeight: 800, color: A.text, marginBottom: 8 }}>
            {STEP_TITLES[step - 1]}
          </h1>
          {step === 1 && (
            <p style={{ fontSize: 15, color: A.textSoft }}>
              We'll analyze your brand and build a content strategy in under 2 minutes.
            </p>
          )}
        </div>

        {/* Step content with transition */}
        <div
          key={step}
          style={{
            animation: 'wiz-fadein 0.25s ease',
          }}
        >
          {renderStep()}
        </div>

        {/* Navigation for steps 1-3 */}
        {step < 4 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginTop: 28,
          }}>
            {step > 1 ? (
              <button
                onClick={next}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: 13, color: A.textMuted, padding: 0,
                }}
              >
                Skip for now
              </button>
            ) : <span />}

            <button
              onClick={step === 3 ? handleGenerate : next}
              disabled={!canAdvance(step)}
              style={{
                padding: step === 3 ? '14px 36px' : '12px 32px', borderRadius: 10, border: 'none',
                cursor: canAdvance(step) ? 'pointer' : 'not-allowed',
                background: canAdvance(step)
                  ? `linear-gradient(135deg, ${A.indigo}, ${A.violet})`
                  : A.surfaceAlt,
                color: canAdvance(step) ? 'white' : A.textMuted,
                fontSize: step === 3 ? 16 : 15, fontWeight: step === 3 ? 700 : 600,
                transition: 'all 0.2s',
              }}
            >
              {step === 3 ? 'Create My Brand \u2728' : 'Next \u2192'}
            </button>
          </div>
        )}

        <style>{`
          @keyframes wiz-fadein {
            from { opacity: 0; transform: translateX(12px); }
            to { opacity: 1; transform: translateX(0); }
          }
        `}</style>
      </div>
    </div>
  )
}

/* ── Shared styles ── */

const labelStyle: React.CSSProperties = {
  fontSize: 13, fontWeight: 500, color: A.text,
  display: 'block', marginBottom: 6,
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px', borderRadius: 8,
  border: `1px solid ${A.border}`, fontSize: 14, color: A.text,
  background: A.surface, outline: 'none',
  transition: 'border-color 0.2s', boxSizing: 'border-box',
}
