import { useState, useEffect } from 'react'
import { A } from '../theme'

interface BrandProfile {
  brand_id: string
  business_name: string
  business_type: string
  industry: string
  tone: string
  colors?: string[]
  target_audience: string
  visual_style: string
  image_style_directive: string
  caption_style_directive: string
  content_themes?: string[]
  competitors?: string[]
  analysis_status: string
  ui_preferences?: { show_competitors?: boolean }
}

interface Props {
  brand: BrandProfile
  onUpdate: (data: Partial<BrandProfile>) => void | Promise<void>
}

export default function BrandProfileCard({ brand, onUpdate }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(brand)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [showCompetitors, setShowCompetitors] = useState(
    brand.ui_preferences?.show_competitors ?? true
  )

  // Sync draft and toggle state when brand prop changes (e.g. after analysis or brand switch)
  useEffect(() => {
    setDraft(brand)
    setShowCompetitors(brand.ui_preferences?.show_competitors ?? true)
  }, [brand.brand_id])

  const handleToggleCompetitors = () => {
    const next = !showCompetitors
    setShowCompetitors(next)
    onUpdate({ ui_preferences: { show_competitors: next } })
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError('')
    try {
      await onUpdate({
        industry: draft.industry,
        tone: draft.tone,
        target_audience: draft.target_audience,
        visual_style: draft.visual_style,
        image_style_directive: draft.image_style_directive,
        caption_style_directive: draft.caption_style_directive,
      })
      setEditing(false)
    } catch (err: unknown) {
      setSaveError((err as Error).message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (brand.analysis_status === 'analyzing') {
    return (
      <div style={{
        padding: 24, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}`,
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: '50%',
          border: `3px solid ${A.indigoLight}`,
          borderTopColor: A.indigo,
          animation: 'spin 1s linear infinite',
        }} />
        <div>
          <p style={{ fontSize: 14, fontWeight: 500, color: A.text }}>Analyzing your brand...</p>
          <p style={{ fontSize: 12, color: A.textSoft }}>This usually takes 30–60 seconds</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: A.text, marginBottom: 4 }}>
            {brand.business_name || 'Your Brand'}
          </h2>
          <span style={{
            fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 20,
            background: A.indigoLight, color: A.indigo,
          }}>
            {brand.business_type?.replace('_', ' ').toUpperCase() || 'BRAND'}
          </span>
        </div>
        <button
          onClick={() => { setDraft(brand); setSaveError(''); setEditing(!editing) }}
          style={{
            padding: '6px 14px', borderRadius: 6, border: `1px solid ${A.border}`,
            background: 'transparent', cursor: 'pointer', fontSize: 13, color: A.textSoft,
          }}
        >
          {editing ? 'Cancel' : 'Edit'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Industry */}
        <Field label="Industry" value={brand.industry} editing={editing}
          onChange={v => setDraft(d => ({ ...d, industry: v }))} draft={draft.industry} />

        {/* Tone */}
        <Field label="Tone of Voice" value={brand.tone} editing={editing}
          onChange={v => setDraft(d => ({ ...d, tone: v }))} draft={draft.tone} />

        {/* Target Audience */}
        <div style={{ gridColumn: '1 / -1' }}>
          <Field label="Target Audience" value={brand.target_audience} editing={editing}
            onChange={v => setDraft(d => ({ ...d, target_audience: v }))} draft={draft.target_audience} />
        </div>

        {/* Visual Style */}
        <div style={{ gridColumn: '1 / -1' }}>
          <Field label="Visual Style" value={brand.visual_style} editing={editing}
            onChange={v => setDraft(d => ({ ...d, visual_style: v }))} draft={draft.visual_style} />
        </div>

        {/* Colors */}
        <div>
          <p style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>Brand Colors</p>
          <div style={{ display: 'flex', gap: 8 }}>
            {(brand.colors || []).map((color, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 32, height: 32, borderRadius: 6, background: color, border: `1px solid ${A.border}` }} />
                <span style={{ fontSize: 10, color: A.textMuted }}>{color}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Content Themes */}
        <div>
          <p style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>Content Themes</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(brand.content_themes || []).map((theme, i) => (
              <span key={i} style={{
                fontSize: 11, padding: '3px 8px', borderRadius: 20,
                background: A.surfaceAlt, color: A.textSoft, border: `1px solid ${A.border}`,
              }}>{theme}</span>
            ))}
          </div>
        </div>

        {/* Competitor Landscape — collapsible with persisted preference */}
        {(brand.competitors || []).length > 0 && (
          <div style={{ gridColumn: '1 / -1' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <p style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Competitor Landscape
              </p>
              {/* Toggle switch */}
              <div
                role="switch"
                aria-checked={showCompetitors}
                aria-label={showCompetitors ? 'Hide competitors' : 'Show competitors'}
                onClick={handleToggleCompetitors}
                style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}
              >
                <div style={{
                  width: 32, height: 18, borderRadius: 9,
                  background: showCompetitors ? A.indigo : A.border,
                  position: 'relative', transition: 'background 0.2s',
                }}>
                  <div style={{
                    position: 'absolute', top: 2,
                    left: showCompetitors ? 16 : 2,
                    width: 14, height: 14, borderRadius: '50%',
                    background: 'white', transition: 'left 0.2s',
                  }} />
                </div>
                <span style={{ fontSize: 11, color: A.textMuted }}>
                  {showCompetitors ? 'Showing' : 'Hidden'}
                </span>
              </div>
            </div>
            {showCompetitors && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {(brand.competitors || []).map(c => (
                  <span key={c} style={{
                    fontSize: 11, padding: '3px 8px', borderRadius: 20,
                    background: A.surfaceAlt, color: A.textSoft,
                    border: `1px solid ${A.border}`,
                  }}>{c}</span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Image Style Directive */}
        <div style={{ gridColumn: '1 / -1' }}>
          <p style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Visual Identity Seed
          </p>
          {editing ? (
            <textarea
              value={draft.image_style_directive}
              onChange={e => setDraft(d => ({ ...d, image_style_directive: e.target.value }))}
              rows={2}
              style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: `1px solid ${A.border}`, fontSize: 12, resize: 'vertical' }}
            />
          ) : (
            <p style={{ fontSize: 12, color: A.text, lineHeight: 1.5, padding: '8px 10px', borderRadius: 6, background: A.surfaceAlt }}>
              {brand.image_style_directive || '—'}
            </p>
          )}
        </div>

        {/* Caption Style Directive */}
        <div style={{ gridColumn: '1 / -1' }}>
          <p style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Caption Style Directive
          </p>
          {editing ? (
            <textarea
              value={draft.caption_style_directive}
              onChange={e => setDraft(d => ({ ...d, caption_style_directive: e.target.value }))}
              rows={2}
              style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: `1px solid ${A.border}`, fontSize: 12, resize: 'vertical' }}
            />
          ) : (
            <p style={{ fontSize: 12, color: A.text, lineHeight: 1.5, padding: '8px 10px', borderRadius: 6, background: A.surfaceAlt }}>
              {brand.caption_style_directive || '—'}
            </p>
          )}
        </div>
      </div>

      {editing && (
        <div style={{ marginTop: 16 }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '10px 20px', borderRadius: 8, border: 'none',
              cursor: saving ? 'not-allowed' : 'pointer',
              background: saving ? A.surfaceAlt : A.indigo,
              color: saving ? A.textMuted : 'white', fontSize: 14, fontWeight: 600,
            }}
          >
            {/* M-5: Show saving state with feedback */}
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          {saveError && (
            <p style={{ fontSize: 12, color: A.coral, marginTop: 6 }}>{saveError}</p>
          )}
        </div>
      )}
    </div>
  )
}

function Field({ label, value, draft, editing, onChange }: {
  label: string; value: string; draft: string; editing: boolean; onChange: (v: string) => void
}) {
  return (
    <div>
      <p style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</p>
      {editing ? (
        <input
          value={draft}
          onChange={e => onChange(e.target.value)}
          style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: `1px solid ${A.border}`, fontSize: 13 }}
        />
      ) : (
        <p style={{ fontSize: 13, color: A.text }}>{value || '—'}</p>
      )}
    </div>
  )
}
