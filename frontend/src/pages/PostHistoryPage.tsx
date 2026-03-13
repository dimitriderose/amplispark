import { useState, useEffect, useMemo, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { useAuth } from '../hooks/useAuth'
import { usePostLibrary, Post } from '../hooks/usePostLibrary'
import PostCard from '../components/PostCard'

type StatusFilter = 'all' | 'approved' | 'complete' | 'generating' | 'failed'

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'approved', label: 'Approved' },
  { key: 'complete', label: 'Ready' },
  { key: 'generating', label: 'Generating' },
  { key: 'failed', label: 'Failed' },
]

const PAGE_SIZE = 20

function Pill({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick} style={{
      padding: '4px 10px', borderRadius: 16, fontSize: 12, cursor: 'pointer',
      border: active ? 'none' : `1px solid ${A.border}`,
      background: active ? A.indigo : 'transparent',
      color: active ? 'white' : A.textSoft,
      fontWeight: active ? 600 : 400,
      textTransform: 'capitalize',
    }}>
      {children}
    </button>
  )
}

function getWeekLabel(dateStr?: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return ''
  // Get Monday of that week
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(d)
  monday.setDate(diff)
  return `Week of ${monday.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
}

export default function PostHistoryPage() {
  const { brandId } = useParams<{ brandId: string }>()
  const navigate = useNavigate()
  const { isSignedIn, loading: authLoading } = useAuth()
  const { posts, loading, error, refresh } = usePostLibrary(brandId ?? '')

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [platformFilter, setPlatformFilter] = useState('all')
  const [pillarFilter, setPillarFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  // Auth guard
  useEffect(() => {
    if (!authLoading && !isSignedIn) navigate('/')
  }, [authLoading, isSignedIn, navigate])

  // Sort all posts by created_at desc
  const sorted = useMemo(() =>
    [...posts].sort((a, b) => {
      const ta = a.created_at ? new Date(a.created_at).getTime() : 0
      const tb = b.created_at ? new Date(b.created_at).getTime() : 0
      return tb - ta
    }),
    [posts]
  )

  // Filter pipeline
  const filtered = useMemo(() => {
    let result = sorted
    if (statusFilter !== 'all') result = result.filter(p => p.status === statusFilter)
    if (platformFilter !== 'all') result = result.filter(p => p.platform === platformFilter)
    if (pillarFilter !== 'all') result = result.filter(p => p.pillar === pillarFilter)
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(p => p.caption?.toLowerCase().includes(q))
    }
    return result
  }, [sorted, statusFilter, platformFilter, pillarFilter, search])

  // Derive unique platforms and pillars from all posts
  const uniquePlatforms = useMemo(() =>
    Array.from(new Set(sorted.map(p => p.platform).filter(Boolean))) as string[],
    [sorted]
  )
  const uniquePillars = useMemo(() =>
    Array.from(new Set(sorted.map(p => p.pillar).filter(Boolean))) as string[],
    [sorted]
  )

  // Auto-reset filters when they become invalid
  useEffect(() => {
    if (platformFilter !== 'all' && !uniquePlatforms.includes(platformFilter)) setPlatformFilter('all')
  }, [uniquePlatforms, platformFilter])
  useEffect(() => {
    if (pillarFilter !== 'all' && !uniquePillars.includes(pillarFilter)) setPillarFilter('all')
  }, [uniquePillars, pillarFilter])

  // Reset pagination when filters change
  useEffect(() => { setVisibleCount(PAGE_SIZE) }, [statusFilter, platformFilter, pillarFilter, search])

  const paginated = filtered.slice(0, visibleCount)

  // Build week-grouped render list
  const renderItems: ({ type: 'header'; label: string } | { type: 'post'; post: Post })[] = []
  let lastWeek = ''
  for (const post of paginated) {
    const week = getWeekLabel(post.created_at)
    if (week && week !== lastWeek) {
      renderItems.push({ type: 'header', label: week })
      lastWeek = week
    }
    renderItems.push({ type: 'post', post })
  }

  if (!brandId) return null

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: A.text, margin: '0 0 4px' }}>
          Post History
        </h2>
        <p style={{ fontSize: 13, color: A.textMuted, margin: 0 }}>
          All posts across all content plans
          {sorted.length > 0 && <span style={{ marginLeft: 8, fontWeight: 500 }}>({sorted.length} total)</span>}
        </p>
      </div>

      {/* Search */}
      <div style={{ marginBottom: 12 }}>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search captions..."
          style={{
            width: '100%', maxWidth: 400, padding: '8px 12px', borderRadius: 8,
            border: `1px solid ${A.border}`, fontSize: 13, color: A.text,
            background: A.surface, outline: 'none', boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Status filters */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        {STATUS_FILTERS.map(f => (
          <Pill key={f.key} active={statusFilter === f.key} onClick={() => setStatusFilter(f.key)}>
            {f.label}
          </Pill>
        ))}
      </div>

      {/* Platform + Pillar filters */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        {uniquePlatforms.length > 1 && (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: A.textMuted }}>Platform:</span>
            <Pill active={platformFilter === 'all'} onClick={() => setPlatformFilter('all')}>All</Pill>
            {uniquePlatforms.map(p => (
              <Pill key={p} active={platformFilter === p} onClick={() => setPlatformFilter(p)}>{p}</Pill>
            ))}
          </div>
        )}
        {uniquePillars.length > 1 && (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: A.textMuted }}>Pillar:</span>
            <Pill active={pillarFilter === 'all'} onClick={() => setPillarFilter('all')}>All</Pill>
            {uniquePillars.map(p => (
              <Pill key={p} active={pillarFilter === p} onClick={() => setPillarFilter(p)}>
                {p.replace(/_/g, ' ')}
              </Pill>
            ))}
          </div>
        )}
      </div>

      {/* Results count */}
      {!loading && filtered.length > 0 && filtered.length !== sorted.length && (
        <div style={{ fontSize: 12, color: A.textMuted, marginBottom: 12 }}>
          Showing {Math.min(visibleCount, filtered.length)} of {filtered.length} matching posts
        </div>
      )}

      {/* Loading / Error / Empty */}
      {loading && (
        <div style={{ padding: 60, textAlign: 'center', color: A.textSoft, fontSize: 14 }}>
          Loading post history...
        </div>
      )}
      {error && !loading && (
        <div style={{ padding: 20, borderRadius: 8, background: A.coral + '15', color: A.coral, fontSize: 13 }}>
          {error}
        </div>
      )}
      {!loading && !error && sorted.length === 0 && (
        <div style={{
          padding: 60, textAlign: 'center', background: A.surfaceAlt,
          borderRadius: 12, color: A.textMuted, fontSize: 14,
        }}>
          No posts yet. Generate content plans from your brand dashboard to see posts here.
        </div>
      )}
      {!loading && !error && sorted.length > 0 && filtered.length === 0 && (
        <div style={{
          padding: 40, textAlign: 'center', background: A.surfaceAlt,
          borderRadius: 12, color: A.textMuted, fontSize: 13,
        }}>
          No posts match your filters
        </div>
      )}

      {/* Post grid with week headers */}
      {!loading && paginated.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 16,
        }}>
          {renderItems.map((item, i) =>
            item.type === 'header' ? (
              <div key={`week-${i}`} style={{
                gridColumn: '1 / -1',
                fontSize: 13, fontWeight: 600, color: A.textSoft,
                padding: '12px 0 4px',
                borderBottom: `1px solid ${A.border}`,
                marginBottom: 4,
              }}>
                {item.label}
              </div>
            ) : (
              <PostCard
                key={item.post.post_id}
                post={item.post}
                brandId={brandId}
                onApproved={refresh}
                onView={
                  (item.post.status === 'complete' || item.post.status === 'approved') && item.post.plan_id
                    ? () => navigate(`/generate/${item.post.plan_id}/${item.post.day_index}?brand_id=${brandId}&post_id=${item.post.post_id}`)
                    : undefined
                }
              />
            )
          )}
        </div>
      )}

      {/* Load more */}
      {!loading && visibleCount < filtered.length && (
        <div style={{ textAlign: 'center', marginTop: 24 }}>
          <button
            onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
            style={{
              padding: '10px 28px', borderRadius: 8,
              border: `1px solid ${A.border}`, background: A.surface,
              color: A.text, fontSize: 13, fontWeight: 500, cursor: 'pointer',
            }}
          >
            Load more ({filtered.length - visibleCount} remaining)
          </button>
        </div>
      )}
    </div>
  )
}
