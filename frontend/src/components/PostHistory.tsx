import { useState, useEffect, useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { usePostLibrary, type Post } from '../hooks/usePostLibrary'
import { useIsMobile } from '../hooks/useIsMobile'
import PostCard from './PostCard'

type StatusFilter = 'all' | 'approved' | 'complete'

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'approved', label: 'Approved' },
  { key: 'complete', label: 'Ready' },
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
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(d)
  monday.setDate(diff)
  return `Week of ${monday.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
}

export default function PostHistory({ brandId }: { brandId: string }) {
  const isMobile = useIsMobile()
  const navigate = useNavigate()
  const { posts, loading, error, refresh } = usePostLibrary(brandId)

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [platformFilter, setPlatformFilter] = useState('all')
  const [pillarFilter, setPillarFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  // Only show complete or approved posts
  const sorted = useMemo(() =>
    [...posts]
      .filter(p => p.status === 'complete' || p.status === 'approved')
      .sort((a, b) => {
        const ta = a.created_at ? new Date(a.created_at).getTime() : 0
        const tb = b.created_at ? new Date(b.created_at).getTime() : 0
        return tb - ta
      }),
    [posts]
  )

  const filtered = useMemo(() => {
    let result = sorted
    if (statusFilter !== 'all') result = result.filter(p => p.status === statusFilter)
    if (platformFilter !== 'all') result = result.filter(p => p.platform === platformFilter)
    if (pillarFilter !== 'all') result = result.filter(p => p.pillar === pillarFilter)
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(p => {
        const haystack = [
          p.caption,
          p.platform,
          p.pillar?.replace(/_/g, ' '),
          ...(p.hashtags || []),
        ].filter(Boolean).join(' ').toLowerCase()
        return haystack.includes(q)
      })
    }
    return result
  }, [sorted, statusFilter, platformFilter, pillarFilter, search])

  const uniquePlatforms = useMemo(() =>
    Array.from(new Set(sorted.map(p => p.platform).filter(Boolean))) as string[],
    [sorted]
  )
  const uniquePillars = useMemo(() =>
    Array.from(new Set(sorted.map(p => p.pillar).filter(Boolean))) as string[],
    [sorted]
  )

  useEffect(() => {
    if (platformFilter !== 'all' && !uniquePlatforms.includes(platformFilter)) setPlatformFilter('all')
  }, [uniquePlatforms, platformFilter])
  useEffect(() => {
    if (pillarFilter !== 'all' && !uniquePillars.includes(pillarFilter)) setPillarFilter('all')
  }, [uniquePillars, pillarFilter])
  useEffect(() => { setVisibleCount(PAGE_SIZE) }, [statusFilter, platformFilter, pillarFilter, search])

  const paginated = filtered.slice(0, visibleCount)

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

  return (
    <div>
      {/* Header */}
      <p style={{ fontSize: 13, color: A.textMuted, margin: '0 0 16px' }}>
        All posts across all content plans
        {sorted.length > 0 && <span style={{ marginLeft: 8, fontWeight: 500 }}>({sorted.length} total)</span>}
      </p>

      {/* Search */}
      <div style={{ marginBottom: 12 }}>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search captions, hashtags, platforms..."
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
          No posts yet. Generate content plans to see posts here.
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
          gridTemplateColumns: isMobile ? 'repeat(auto-fill, minmax(140px, 1fr))' : 'repeat(auto-fill, minmax(200px, 1fr))',
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
                    ? () => navigate(`/generate/${item.post.plan_id}/${item.post.brief_index ?? item.post.day_index}?brand_id=${brandId}&post_id=${item.post.post_id}`)
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
