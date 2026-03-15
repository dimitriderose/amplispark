import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { api } from '../api/client'
import { useBrandProfile } from '../hooks/useBrandProfile'
import { useIsMobile, useIsTablet } from '../hooks/useIsMobile'
import { PLATFORMS } from '../platformRegistry'
import { IMAGE_STYLE_GROUPS } from '../imageStyleOptions'
import PageContainer from '../components/ui/PageContainer'

/** Convert a gs:// URI to a proxy-servable URL. */
function gcsToUrl(gcsUri: string): string {
  const prefix = 'gs://'
  if (!gcsUri.startsWith(prefix)) return gcsUri
  // gs://bucket/path → /api/storage/serve/path
  const withoutScheme = gcsUri.slice(prefix.length)
  const slashIdx = withoutScheme.indexOf('/')
  if (slashIdx === -1) return gcsUri
  return `/api/storage/serve/${withoutScheme.slice(slashIdx + 1)}`
}

interface UploadedAsset {
  filename: string
  url: string
  type: string
}

export default function EditBrandPage() {
  const isMobile = useIsMobile()
  const isTablet = useIsTablet()
  const { brandId } = useParams<{ brandId: string }>()
  const navigate = useNavigate()
  const { brand, loading, error: loadError, refetch } = useBrandProfile(brandId)

  // Form state
  const [businessName, setBusinessName] = useState('')
  const [description, setDescription] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [industry, setIndustry] = useState('')
  const [tone, setTone] = useState('')
  const [targetAudience, setTargetAudience] = useState('')
  const [colors, setColors] = useState<string[]>([])
  const [visualStyle, setVisualStyle] = useState('')
  const [imageStyleDirective, setImageStyleDirective] = useState('')
  const [captionStyleDirective, setCaptionStyleDirective] = useState('')
  const [contentThemes, setContentThemes] = useState<string[]>([])
  const [competitors, setCompetitors] = useState<string[]>([])
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([])
  const [platformMode, setPlatformMode] = useState<'ai' | 'manual'>('ai')
  const [defaultImageStyle, setDefaultImageStyle] = useState('')
  const [logoUrl, setLogoUrl] = useState<string | null>(null)
  const [assets, setAssets] = useState<UploadedAsset[]>([])

  // UI state
  const [saving, setSaving] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [saveError, setSaveError] = useState('')
  const [newTheme, setNewTheme] = useState('')
  const [newCompetitor, setNewCompetitor] = useState('')
  const [newColor, setNewColor] = useState('#5B5FF6')
  const fileRef = useRef<HTMLInputElement>(null)
  const logoRef = useRef<HTMLInputElement>(null)

  // Populate form from brand
  useEffect(() => {
    if (!brand) return
    setBusinessName(brand.business_name || '')
    setDescription(brand.description || '')
    setWebsiteUrl(brand.website_url || '')
    setIndustry(brand.industry || '')
    setTone(brand.tone || '')
    setTargetAudience(brand.target_audience || '')
    setColors(brand.colors || [])
    setVisualStyle(brand.visual_style || '')
    setImageStyleDirective(brand.image_style_directive || '')
    setCaptionStyleDirective(brand.caption_style_directive || '')
    setContentThemes(brand.content_themes || [])
    setCompetitors(brand.competitors || [])
    setSelectedPlatforms(brand.selected_platforms || [])
    setPlatformMode(brand.platform_mode || 'ai')
    setDefaultImageStyle(brand.default_image_style || '')
    setLogoUrl(brand.logo_url || null)
    setAssets(brand.uploaded_assets || [])
  }, [brand])

  const handleSave = async () => {
    if (!brandId) return
    setSaving(true)
    setSaveError('')
    setSaveMsg('')
    try {
      await api.updateBrand(brandId, {
        business_name: businessName,
        description,
        website_url: websiteUrl || null,
        industry,
        tone,
        target_audience: targetAudience,
        colors,
        visual_style: visualStyle,
        image_style_directive: imageStyleDirective,
        caption_style_directive: captionStyleDirective,
        content_themes: contentThemes,
        competitors,
        selected_platforms: selectedPlatforms,
        platform_mode: platformMode,
        default_image_style: defaultImageStyle || null,
      })
      setSaveMsg('Saved successfully')
      setTimeout(() => setSaveMsg(''), 3000)
      await refetch()
    } catch (err: any) {
      setSaveError(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleReAnalyze = async () => {
    if (!brandId) return
    if (!description || description.length < 20) {
      setSaveError('Description must be at least 20 characters to re-analyze')
      return
    }
    setAnalyzing(true)
    setSaveError('')
    try {
      // Save current fields first
      await handleSave()
      // Trigger re-analysis
      await api.analyzeBrand(brandId, {
        website_url: websiteUrl || null,
        description,
      })
      navigate(`/dashboard/${brandId}`)
    } catch (err: any) {
      setSaveError(err.message || 'Re-analysis failed')
      setAnalyzing(false)
    }
  }

  const handleDeleteAsset = async (index: number) => {
    if (!brandId) return
    try {
      await api.deleteBrandAsset(brandId, index)
      setAssets(prev => prev.filter((_, i) => i !== index))
    } catch (err: any) {
      setSaveError(err.message || 'Failed to remove asset')
    }
  }

  const handleSetAsLogo = async (assetUrl: string) => {
    if (!brandId) return
    try {
      await api.setBrandLogo(brandId, assetUrl)
      setLogoUrl(assetUrl)
    } catch (err: any) {
      setSaveError(err.message || 'Failed to set logo')
    }
  }

  const handleRemoveLogo = async () => {
    if (!brandId) return
    try {
      await api.setBrandLogo(brandId, null)
      setLogoUrl(null)
    } catch (err: any) {
      setSaveError(err.message || 'Failed to remove logo')
    }
  }

  const handleUploadAssets = async (files: FileList) => {
    if (!brandId || files.length === 0) return
    const formData = new FormData()
    Array.from(files).slice(0, 3).forEach(f => formData.append('files', f, f.name))
    try {
      const res = await api.uploadBrandAsset(brandId, formData)
      if (res.uploaded) {
        setAssets(prev => [...prev, ...res.uploaded])
      }
    } catch (err: any) {
      setSaveError(err.message || 'Upload failed')
    }
  }

  const handleUploadLogo = async (file: File) => {
    if (!brandId) return
    const formData = new FormData()
    formData.append('files', file, file.name)
    try {
      const res = await api.uploadBrandAsset(brandId, formData)
      if (res.uploaded?.[0]) {
        const gcsUrl = res.uploaded[0].url
        await api.setBrandLogo(brandId, gcsUrl)
        setLogoUrl(gcsUrl)
        setAssets(prev => [...prev, ...res.uploaded])
      }
    } catch (err: any) {
      setSaveError(err.message || 'Logo upload failed')
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300 }}>
        <p style={{ color: A.textSoft }}>Loading brand profile...</p>
      </div>
    )
  }

  if (loadError || !brand) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <p style={{ color: A.coral, marginBottom: 16 }}>{loadError || 'Brand not found'}</p>
        <button
          onClick={() => navigate('/')}
          style={{
            padding: '8px 16px', borderRadius: 8,
            background: A.indigo, color: 'white', border: 'none', cursor: 'pointer',
          }}
        >
          Go Home
        </button>
      </div>
    )
  }

  return (
    <PageContainer maxWidth={720}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: A.text, marginBottom: 4 }}>
            Edit Brand
          </h1>
          <p style={{ fontSize: 14, color: A.textSoft }}>
            Update your brand profile, assets, and content strategy
          </p>
        </div>
        <button
          onClick={() => navigate(`/dashboard/${brandId}`)}
          style={{
            padding: '8px 16px', borderRadius: 8, border: `1px solid ${A.border}`,
            background: 'transparent', cursor: 'pointer', fontSize: 13, color: A.textSoft,
          }}
        >
          Back to Dashboard
        </button>
      </div>

      {/* Success / Error banners */}
      {saveMsg && (
        <div style={{
          marginBottom: 16, padding: '10px 16px', borderRadius: 8,
          background: A.emeraldLight, border: `1px solid ${A.emerald}44`,
          color: A.emerald, fontSize: 13, fontWeight: 500,
        }}>
          {saveMsg}
        </div>
      )}
      {saveError && (
        <div style={{
          marginBottom: 16, padding: '10px 16px', borderRadius: 8,
          background: '#FFF0F0', border: `1px solid ${A.coral}30`,
          color: A.coral, fontSize: 13,
        }}>
          {saveError}
          <button onClick={() => setSaveError('')} style={{
            float: 'right', background: 'none', border: 'none',
            color: A.coral, cursor: 'pointer', fontSize: 16,
          }}>x</button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

        {/* ── Section 1: Brand Identity ──────────────────────── */}
        <Section title="Brand Identity">
          <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16 }}>
            <FormField label="Business Name" value={businessName} onChange={setBusinessName} />
            <FormField label="Industry" value={industry} onChange={setIndustry} />
          </div>
          <FormField label="Description" value={description} onChange={setDescription}
            textarea rows={3} hint="min. 20 chars" />
          <FormField label="Website URL" value={websiteUrl} onChange={setWebsiteUrl}
            placeholder="https://yourbusiness.com" />
          <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16 }}>
            <FormField label="Tone of Voice" value={tone} onChange={setTone}
              placeholder="e.g. warm, professional, witty" />
            <FormField label="Target Audience" value={targetAudience} onChange={setTargetAudience} />
          </div>
        </Section>

        {/* ── Section 2: Visual Identity ─────────────────────── */}
        <Section title="Visual Identity">
          <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16 }}>
            <div>
              <Label>Brand Colors</Label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
                {colors.map((c, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 6, background: c,
                      border: `1px solid ${A.border}`, cursor: 'pointer',
                    }} title={c} />
                    <button onClick={() => setColors(prev => prev.filter((_, j) => j !== i))} style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: A.textMuted, fontSize: 14, padding: 0,
                    }}>x</button>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="color" value={newColor} onChange={e => setNewColor(e.target.value)}
                  style={{ width: 32, height: 28, border: 'none', cursor: 'pointer', padding: 0 }} />
                <button onClick={() => {
                  if (!colors.includes(newColor)) setColors(prev => [...prev, newColor])
                }} style={{
                  padding: '4px 10px', borderRadius: 6, border: `1px solid ${A.border}`,
                  background: 'transparent', cursor: 'pointer', fontSize: 12, color: A.textSoft,
                }}>+ Add</button>
              </div>
            </div>
            <FormField label="Visual Style" value={visualStyle} onChange={setVisualStyle}
              placeholder="e.g. clean-minimal, bold-vibrant" />
          </div>
          <div>
            <Label>Default Image Style</Label>
            <select
              value={defaultImageStyle}
              onChange={e => setDefaultImageStyle(e.target.value)}
              style={{
                width: '100%', padding: '8px 12px', borderRadius: 8,
                border: `1px solid ${A.border}`, fontSize: 13, color: A.text,
                background: A.surface, outline: 'none',
              }}
            >
              <option value="">Auto (AI chooses)</option>
              {IMAGE_STYLE_GROUPS.map(g => (
                <optgroup key={g.label} label={g.label}>
                  {g.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </optgroup>
              ))}
            </select>
          </div>
          <FormField label="Image Style Directive" value={imageStyleDirective}
            onChange={setImageStyleDirective} textarea rows={2} />
          <FormField label="Caption Style Directive" value={captionStyleDirective}
            onChange={setCaptionStyleDirective} textarea rows={2} />
        </Section>

        {/* ── Section 3: Platform Strategy ──────────────────── */}
        <Section title="Platform Strategy">
          {/* Mode toggle */}
          <div style={{ display: 'flex', gap: 4, background: A.surfaceAlt, borderRadius: 8, padding: 3 }}>
            {([
              { key: 'ai' as const, label: 'Let AI choose platforms' },
              { key: 'manual' as const, label: "I'll select my platforms" },
            ]).map(opt => (
              <button
                key={opt.key}
                onClick={() => setPlatformMode(opt.key)}
                style={{
                  flex: 1, padding: '8px 12px', borderRadius: 6, border: 'none',
                  cursor: 'pointer', fontSize: 12, fontWeight: platformMode === opt.key ? 600 : 400,
                  background: platformMode === opt.key ? A.surface : 'transparent',
                  color: platformMode === opt.key ? A.text : A.textSoft,
                  boxShadow: platformMode === opt.key ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                  transition: 'all 0.15s',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {platformMode === 'ai' ? (
            <p style={{ fontSize: 12, color: A.textMuted, lineHeight: 1.5 }}>
              AI mode: We'll analyze your brand and select the best 2-4 platforms
            </p>
          ) : (
            <>
              <p style={{ fontSize: 12, color: A.textMuted, lineHeight: 1.5, marginBottom: 4 }}>
                Manual: Choose which platforms to include in your content plans
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8 }}>
                {Object.values(PLATFORMS).map(spec => {
                  const Icon = spec.icon
                  const isSelected = selectedPlatforms.includes(spec.key)
                  return (
                    <button
                      key={spec.key}
                      onClick={() => {
                        setSelectedPlatforms(prev =>
                          isSelected
                            ? prev.filter(k => k !== spec.key)
                            : [...prev, spec.key]
                        )
                      }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '8px 12px', borderRadius: 8,
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
              {selectedPlatforms.length === 0 && (
                <p style={{ fontSize: 11, color: A.coral, marginTop: 2 }}>
                  Select at least 1 platform
                </p>
              )}
            </>
          )}
        </Section>

        {/* ── Section 4: Brand Assets ────────────────────────── */}
        <Section title="Brand Assets">
          {/* Logo */}
          <div style={{ marginBottom: 16 }}>
            <Label>Logo</Label>
            {logoUrl ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <img src={gcsToUrl(logoUrl)} alt="Brand logo"
                  style={{ width: 64, height: 64, objectFit: 'contain', borderRadius: 8,
                    border: `1px solid ${A.border}`, background: A.surfaceAlt }} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => logoRef.current?.click()} style={smallBtnStyle}>Replace</button>
                  <button onClick={handleRemoveLogo} style={{ ...smallBtnStyle, color: A.coral, borderColor: `${A.coral}40` }}>Remove</button>
                </div>
              </div>
            ) : (
              <button onClick={() => logoRef.current?.click()} style={{
                padding: '12px 16px', borderRadius: 8,
                border: `2px dashed ${A.border}`, background: A.surfaceAlt,
                cursor: 'pointer', fontSize: 13, color: A.textSoft, width: '100%',
              }}>
                Upload Logo
              </button>
            )}
            <input ref={logoRef} type="file" accept="image/*" style={{ display: 'none' }}
              onChange={e => { if (e.target.files?.[0]) handleUploadLogo(e.target.files[0]) }} />
          </div>

          {/* Uploaded assets */}
          {assets.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Label>Uploaded Assets</Label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {assets.map((asset, i) => (
                  <div key={i} style={{
                    position: 'relative', width: 100, borderRadius: 8,
                    border: `1px solid ${A.border}`, overflow: 'hidden', background: A.surfaceAlt,
                  }}>
                    {asset.type === 'image' ? (
                      <img src={gcsToUrl(asset.url)} alt={asset.filename}
                        style={{ width: 100, height: 80, objectFit: 'cover' }} />
                    ) : (
                      <div style={{
                        width: 100, height: 80, display: 'flex',
                        alignItems: 'center', justifyContent: 'center', fontSize: 24,
                      }}>
                        {asset.type === 'document' ? '📄' : '📎'}
                      </div>
                    )}
                    <div style={{ padding: '4px 6px' }}>
                      <p style={{ fontSize: 10, color: A.textSoft, overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {asset.filename}
                      </p>
                    </div>
                    <div style={{
                      position: 'absolute', top: 2, right: 2,
                      display: 'flex', gap: 2,
                    }}>
                      {asset.type === 'image' && asset.url !== logoUrl && (
                        <button onClick={() => handleSetAsLogo(asset.url)} title="Set as logo"
                          style={assetActionBtn}>
                          <span style={{ fontSize: 10 }}>logo</span>
                        </button>
                      )}
                      <button onClick={() => handleDeleteAsset(i)} title="Remove"
                        style={{ ...assetActionBtn, background: `${A.coral}dd` }}>
                        x
                      </button>
                    </div>
                    {asset.url === logoUrl && (
                      <div style={{
                        position: 'absolute', bottom: 22, left: 0, right: 0,
                        textAlign: 'center', fontSize: 9, fontWeight: 600,
                        color: 'white', background: `${A.indigo}cc`, padding: '2px 0',
                      }}>LOGO</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload new */}
          <div
            onClick={() => fileRef.current?.click()}
            style={{
              border: `2px dashed ${A.border}`, borderRadius: 8, padding: '16px',
              textAlign: 'center', cursor: 'pointer', background: A.surfaceAlt,
              transition: 'border-color 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = A.indigo)}
            onMouseLeave={e => (e.currentTarget.style.borderColor = A.border)}
          >
            <p style={{ fontSize: 13, color: A.textSoft }}>Drop files here or click to upload</p>
            <p style={{ fontSize: 12, color: A.textMuted, marginTop: 4 }}>JPG, PNG, PDF — max 3 files</p>
            <input ref={fileRef} type="file" multiple accept="image/*,.pdf" style={{ display: 'none' }}
              onChange={e => { if (e.target.files) handleUploadAssets(e.target.files) }} />
          </div>
        </Section>

        {/* ── Section 5: Content Strategy ────────────────────── */}
        <Section title="Content Strategy">
          <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16 }}>
            <TagEditor label="Content Themes" tags={contentThemes} setTags={setContentThemes}
              newValue={newTheme} setNewValue={setNewTheme} />
            <TagEditor label="Competitors" tags={competitors} setTags={setCompetitors}
              newValue={newCompetitor} setNewValue={setNewCompetitor} />
          </div>
        </Section>

        {/* ── Actions ────────────────────────────────────────── */}
        {platformMode === 'manual' && selectedPlatforms.length === 0 && (
          <div style={{
            padding: '10px 14px', borderRadius: 8,
            background: `${A.coral}12`, border: `1px solid ${A.coral}30`,
            fontSize: 12, color: A.coral, fontWeight: 500,
          }}>
            Select at least one platform before saving. Switch to manual platform selection above or choose "Let AI choose platforms".
          </div>
        )}
        <div style={{ display: 'flex', gap: 12, paddingTop: 8, paddingBottom: 32 }}>
          <button onClick={handleSave} disabled={saving || (platformMode === 'manual' && selectedPlatforms.length === 0)} style={{
            flex: 1, padding: '14px', borderRadius: 10, border: 'none',
            cursor: (saving || (platformMode === 'manual' && selectedPlatforms.length === 0)) ? 'not-allowed' : 'pointer',
            background: (saving || (platformMode === 'manual' && selectedPlatforms.length === 0)) ? A.surfaceAlt : `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
            color: (saving || (platformMode === 'manual' && selectedPlatforms.length === 0)) ? A.textMuted : 'white',
            fontSize: 15, fontWeight: 600, transition: 'all 0.2s',
          }}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          <button onClick={handleReAnalyze} disabled={analyzing} style={{
            padding: '14px 24px', borderRadius: 10,
            border: `1px solid ${A.indigo}`,
            background: 'transparent', cursor: analyzing ? 'not-allowed' : 'pointer',
            color: A.indigo, fontSize: 15, fontWeight: 600,
          }}>
            {analyzing ? 'Analyzing...' : 'Re-Analyze Brand'}
          </button>
          <button onClick={() => navigate(`/dashboard/${brandId}`)} style={{
            padding: '14px 20px', borderRadius: 10,
            border: `1px solid ${A.border}`, background: 'transparent',
            cursor: 'pointer', color: A.textSoft, fontSize: 14,
          }}>
            Cancel
          </button>
        </div>
      </div>
    </PageContainer>
  )
}

/* ── Shared sub-components ────────────────────────────────────── */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      padding: 24, borderRadius: 12, background: A.surface,
      border: `1px solid ${A.border}`,
    }}>
      <h2 style={{
        fontSize: 16, fontWeight: 600, color: A.text, marginBottom: 16,
        paddingBottom: 12, borderBottom: `1px solid ${A.borderLight}`,
      }}>
        {title}
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {children}
      </div>
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label style={{
      fontSize: 12, fontWeight: 500, color: A.textSoft,
      display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5,
    }}>
      {children}
    </label>
  )
}

function FormField({
  label, value, onChange, placeholder, textarea, rows, hint,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; textarea?: boolean; rows?: number; hint?: string;
}) {
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', borderRadius: 8,
    border: `1px solid ${A.border}`, fontSize: 13, color: A.text,
    background: A.surface, outline: 'none', resize: textarea ? 'vertical' : undefined,
    lineHeight: 1.5,
  }
  return (
    <div>
      <Label>
        {label}
        {hint && <span style={{ fontWeight: 400, color: A.textMuted, marginLeft: 6, textTransform: 'none' }}>({hint})</span>}
      </Label>
      {textarea ? (
        <textarea value={value} onChange={e => onChange(e.target.value)}
          placeholder={placeholder} rows={rows || 3} style={inputStyle} />
      ) : (
        <input value={value} onChange={e => onChange(e.target.value)}
          placeholder={placeholder} style={inputStyle} />
      )}
    </div>
  )
}

function TagEditor({
  label, tags, setTags, newValue, setNewValue,
}: {
  label: string; tags: string[]; setTags: (t: string[]) => void;
  newValue: string; setNewValue: (v: string) => void;
}) {
  const add = () => {
    const v = newValue.trim()
    if (v && !tags.includes(v)) {
      setTags([...tags, v])
      setNewValue('')
    }
  }
  return (
    <div>
      <Label>{label}</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        {tags.map((t, i) => (
          <span key={i} style={{
            fontSize: 11, padding: '3px 8px', borderRadius: 20,
            background: A.surfaceAlt, color: A.textSoft,
            border: `1px solid ${A.border}`, display: 'flex', alignItems: 'center', gap: 4,
          }}>
            {t}
            <button onClick={() => setTags(tags.filter((_, j) => j !== i))} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: A.textMuted, fontSize: 12, padding: 0, lineHeight: 1,
            }}>x</button>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input value={newValue} onChange={e => setNewValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder={`Add ${label.toLowerCase()}`}
          style={{
            flex: 1, padding: '6px 10px', borderRadius: 6,
            border: `1px solid ${A.border}`, fontSize: 12,
          }} />
        <button onClick={add} style={{
          padding: '4px 10px', borderRadius: 6, border: `1px solid ${A.border}`,
          background: 'transparent', cursor: 'pointer', fontSize: 12, color: A.textSoft,
        }}>+</button>
      </div>
    </div>
  )
}

const smallBtnStyle: React.CSSProperties = {
  padding: '4px 10px', borderRadius: 6, border: `1px solid ${A.border}`,
  background: 'transparent', cursor: 'pointer', fontSize: 12, color: A.textSoft,
}

const assetActionBtn: React.CSSProperties = {
  width: 20, height: 20, borderRadius: 4,
  border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 700,
  color: 'white', background: `${A.indigo}dd`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 0,
}
