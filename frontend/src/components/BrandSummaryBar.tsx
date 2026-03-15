import { A } from '../theme'
import { useIsMobile } from '../hooks/useIsMobile'
import type { BrandProfile } from '../hooks/useBrandProfile'

/** Convert a gs:// URI to a proxy-servable URL. */
function gcsToUrl(gcsUri: string): string {
  const prefix = 'gs://'
  if (!gcsUri.startsWith(prefix)) return gcsUri
  const withoutScheme = gcsUri.slice(prefix.length)
  const slashIdx = withoutScheme.indexOf('/')
  if (slashIdx === -1) return gcsUri
  return `/api/storage/serve/${withoutScheme.slice(slashIdx + 1)}`
}

interface Props {
  brand: BrandProfile
  onNavigateEdit: () => void
  onNavigateNew: () => void
}

export default function BrandSummaryBar({ brand, onNavigateEdit, onNavigateNew }: Props) {
  const isMobile = useIsMobile()
  const connectedPlatforms = brand.connected_platforms ?? []
  const notionConnected = !!brand.integrations?.notion?.access_token

  const isAnalyzing = brand.analysis_status === 'analyzing'

  return (
    <div style={{
      padding: '16px 20px',
      borderRadius: 12,
      background: A.surface,
      border: `1px solid ${A.border}`,
      marginBottom: 20,
    }}>
      {/* Row 1: Logo + Name + Industry + Colors + Buttons */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: isMobile ? 8 : 14,
        flexWrap: 'wrap',
      }}>
        {/* Logo / letter fallback */}
        {brand.logo_url ? (
          <img
            src={gcsToUrl(brand.logo_url)}
            alt=""
            style={{
              width: 40, height: 40, borderRadius: '50%',
              objectFit: 'cover', border: `1px solid ${A.border}`,
            }}
          />
        ) : (
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'white', fontSize: 18, fontWeight: 700,
          }}>
            {(brand.business_name || '?')[0].toUpperCase()}
          </div>
        )}

        {/* Name + Industry */}
        <div style={{ flex: '0 0 auto' }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: A.text, margin: 0, lineHeight: 1.2 }}>
            {brand.business_name || 'Your Brand'}
          </h1>
          <span style={{
            fontSize: 11, fontWeight: 500, padding: '1px 8px', borderRadius: 20,
            background: A.indigoLight, color: A.indigo,
          }}>
            {brand.industry || brand.business_type?.replace('_', ' ') || 'Brand'}
          </span>
        </div>

        {/* Color swatches */}
        {(brand.colors?.length ?? 0) > 0 && (
          <div style={{ display: 'flex', gap: 4, marginLeft: 4 }}>
            {brand.colors.slice(0, 5).map((color, i) => (
              <div key={i} style={{
                width: 20, height: 20, borderRadius: '50%',
                background: color, border: `1px solid ${A.border}`,
              }} title={color} />
            ))}
          </div>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button
            onClick={onNavigateEdit}
            style={{
              padding: '6px 14px', borderRadius: 7, border: `1px solid ${A.indigo}40`,
              background: A.indigoLight, cursor: 'pointer', fontSize: 13, color: A.indigo,
              fontWeight: 500,
            }}
          >
            Edit Brand
          </button>
          <button
            onClick={onNavigateNew}
            style={{
              padding: '6px 14px', borderRadius: 7, border: `1px solid ${A.border}`,
              background: 'transparent', cursor: 'pointer', fontSize: 13, color: A.textSoft,
            }}
          >
            + New Brand
          </button>
        </div>
      </div>

      {/* Row 2: Tone + Connected badges + Analyzing indicator */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginTop: 8,
        flexWrap: 'wrap',
      }}>
        {brand.tone && (
          <span style={{ fontSize: 12, color: A.textSoft, fontStyle: 'italic' }}>
            {brand.tone}
          </span>
        )}

        {brand.tone && (connectedPlatforms.length > 0 || notionConnected) && (
          <span style={{ color: A.border }}>|</span>
        )}

        {/* Connected platform badges */}
        {connectedPlatforms.map(p => (
          <span key={p} style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 20,
            background: A.emeraldLight, color: A.emerald, fontWeight: 500,
          }}>
            ✓ {p.charAt(0).toUpperCase() + p.slice(1)}
          </span>
        ))}

        {notionConnected && (
          <span style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 20,
            background: A.emeraldLight, color: A.emerald, fontWeight: 500,
          }}>
            ✓ Notion
          </span>
        )}

        {isAnalyzing && (
          <span style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 20,
            background: A.amberLight, color: A.amber, fontWeight: 500,
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }}>
            <span style={{
              display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
              border: `2px solid ${A.amberLight}`, borderTopColor: A.amber,
              animation: 'bsb-spin 0.8s linear infinite',
            }} />
            Analyzing...
          </span>
        )}
      </div>

      {isAnalyzing && (
        <style>{`@keyframes bsb-spin { to { transform: rotate(360deg); } }`}</style>
      )}
    </div>
  )
}
