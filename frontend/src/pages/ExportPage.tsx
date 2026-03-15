import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { A } from '../theme'
import PostLibrary from '../components/PostLibrary'
import PageContainer from '../components/ui/PageContainer'

export default function ExportPage() {
  const navigate = useNavigate()
  const { brandId } = useParams<{ brandId: string }>()
  const [searchParams] = useSearchParams()
  const planId = searchParams.get('plan_id') || undefined

  if (!brandId) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: A.textSoft }}>
        No brand selected.
      </div>
    )
  }

  return (
    <PageContainer maxWidth={1100}>
      <button
        onClick={() => navigate(`/dashboard/${brandId}`)}
        style={{
          marginBottom: 16, padding: '6px 12px', borderRadius: 6,
          border: `1px solid ${A.border}`, background: 'transparent',
          color: A.textSoft, fontSize: 13, cursor: 'pointer',
        }}
      >
        ← Back to Dashboard
      </button>

      {/* M-8: Differentiate export page from dashboard with clear workflow header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: A.text, margin: 0, marginBottom: 4 }}>
          Export Posts
        </h1>
        <p style={{ fontSize: 14, color: A.textSoft, margin: 0 }}>
          Copy captions to clipboard, download individual posts, or export an entire plan as a ZIP archive.
        </p>
      </div>

      {planId && (
        <div style={{
          marginBottom: 20, padding: '12px 16px', borderRadius: 10,
          background: `linear-gradient(135deg, ${A.indigo}10, ${A.violet}08)`,
          border: `1px solid ${A.indigo}20`,
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span style={{ fontSize: 20 }}>📦</span>
          <div>
            <p style={{ fontSize: 13, fontWeight: 600, color: A.text, margin: 0 }}>
              Plan ZIP export available
            </p>
            <p style={{ fontSize: 12, color: A.textSoft, margin: 0 }}>
              Use "↓ Export All" to download all approved posts as a single ZIP with captions and images.
            </p>
          </div>
        </div>
      )}

      <div style={{
        padding: 24, borderRadius: 12,
        background: A.surface, border: `1px solid ${A.border}`,
      }}>
        <PostLibrary brandId={brandId} planId={planId} defaultFilter="approved" />
      </div>
    </PageContainer>
  )
}
