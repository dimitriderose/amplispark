import React, { useState, useEffect, useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { usePostLibrary, type Post } from '../hooks/usePostLibrary'
import { useIsMobile, useIsTablet } from '../hooks/useIsMobile'
import { api } from '../api/client'
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

const MenuItem = ({ icon, label, desc, onClick, disabled }: {
  icon: string; label: string; desc: string; onClick: () => void; disabled?: boolean
}) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      display: 'flex', alignItems: 'center', gap: 10, width: '100%',
      padding: '8px 12px', border: 'none', background: 'transparent',
      color: disabled ? A.textMuted : A.text, fontSize: 13, cursor: disabled ? 'default' : 'pointer',
      textAlign: 'left', borderRadius: 6, transition: 'background 0.1s',
      opacity: disabled ? 0.5 : 1,
    }}
    onMouseEnter={e => { if (!disabled) e.currentTarget.style.background = A.surfaceAlt }}
    onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
  >
    <span style={{ width: 20, textAlign: 'center', fontSize: 15, flexShrink: 0 }}>{icon}</span>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontWeight: 500, lineHeight: 1.3 }}>{label}</div>
      <div style={{ fontSize: 11, color: A.textMuted, lineHeight: 1.3 }}>{desc}</div>
    </div>
  </button>
)

const SectionLabel = ({ children }: { children: string }) => (
  <div style={{
    padding: '8px 12px 4px', fontSize: 10, fontWeight: 600,
    color: A.textMuted, textTransform: 'uppercase', letterSpacing: 0.5,
  }}>
    {children}
  </div>
)

const Divider = () => (
  <div style={{ height: 1, background: A.border, margin: '4px 8px' }} />
)

interface Props {
  brandId: string
  onQuickPost?: () => void
}

export default function Library({ brandId, onQuickPost }: Props) {
  const isMobile = useIsMobile()
  const isTablet = useIsTablet()
  const navigate = useNavigate()
  const { posts, loading, error, refresh } = usePostLibrary(brandId)

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [platformFilter, setPlatformFilter] = useState('all')
  const [pillarFilter, setPillarFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  const [exporting, setExporting] = useState(false)
  const [calDownloading, setCalDownloading] = useState(false)
  const [notionExporting, setNotionExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [notionResult, setNotionResult] = useState<string | null>(null)
  const [showEmailInput, setShowEmailInput] = useState(false)
  const [emailAddr, setEmailAddr] = useState('')
  const [emailSending, setEmailSending] = useState(false)
  const [emailSent, setEmailSent] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = React.useRef<HTMLDivElement>(null)
  const emailSentTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const notionTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!menuOpen) return
    const handle = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [menuOpen])

  useEffect(() => {
    return () => {
      if (emailSentTimerRef.current) clearTimeout(emailSentTimerRef.current)
      if (notionTimerRef.current) clearTimeout(notionTimerRef.current)
    }
  }, [])

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

  const uniquePlatforms = useMemo(() =>
    Array.from(new Set(sorted.map(p => p.platform).filter(Boolean))) as string[],
    [sorted]
  )
  const uniquePillars = useMemo(() =>
    Array.from(new Set(sorted.map(p => p.pillar).filter(Boolean))) as string[],
    [sorted]
  )

  const activePlatformFilter = uniquePlatforms.includes(platformFilter) ? platformFilter : 'all'
  const activePillarFilter = uniquePillars.includes(pillarFilter) ? pillarFilter : 'all'

  const filtered = useMemo(() => {
    let result = sorted
    if (statusFilter !== 'all') result = result.filter(p => p.status === statusFilter)
    if (activePlatformFilter !== 'all') result = result.filter(p => p.platform === activePlatformFilter)
    if (activePillarFilter !== 'all') result = result.filter(p => p.pillar === activePillarFilter)
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
  }, [sorted, statusFilter, activePlatformFilter, activePillarFilter, search])

  useEffect(() => { setVisibleCount(PAGE_SIZE) }, [statusFilter, activePlatformFilter, activePillarFilter, search])

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

  const handleBulkExport = async () => {
    if (exporting) return
    setMenuOpen(false)
    setExporting(true)
    setExportError(null)
    try {
      const approvedPosts = sorted.filter(p => p.status === 'approved')
      if (approvedPosts.length === 0) {
        setExportError('No approved posts to export')
        return
      }
      const planId = approvedPosts.find(p => p.plan_id)?.plan_id
      if (planId) {
        await api.exportPlan(planId, brandId)
      } else {
        setExportError('No plan associated with posts')
      }
    } catch (err: unknown) {
      setExportError((err as Error).message || 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const handleDownloadCalendar = async () => {
    if (calDownloading) return
    setMenuOpen(false)
    setCalDownloading(true)
    setExportError(null)
    try {
      const planId = sorted.find(p => p.plan_id)?.plan_id
      if (planId) {
        await api.downloadCalendar(brandId, planId)
      } else {
        setExportError('No content plan found')
      }
    } catch (err: unknown) {
      setExportError((err as Error).message || 'Calendar download failed')
    } finally {
      setCalDownloading(false)
    }
  }

  const handleEmailCalendar = async () => {
    if (!emailAddr.trim()) return
    setEmailSending(true)
    setExportError(null)
    try {
      const planId = sorted.find(p => p.plan_id)?.plan_id
      if (planId) {
        await api.emailCalendar(brandId, planId, emailAddr.trim())
        setEmailSent(emailAddr.trim())
        setEmailAddr('')
        setShowEmailInput(false)
        if (emailSentTimerRef.current) clearTimeout(emailSentTimerRef.current)
        emailSentTimerRef.current = setTimeout(() => setEmailSent(''), 3000)
      }
    } catch (err: unknown) {
      setExportError((err as Error).message || 'Failed to send calendar email')
    } finally {
      setEmailSending(false)
    }
  }

  const handleExportNotion = async () => {
    if (notionExporting) return
    setMenuOpen(false)
    setNotionExporting(true)
    setExportError(null)
    setNotionResult(null)
    try {
      const planId = sorted.find(p => p.plan_id)?.plan_id
      if (planId) {
        const res = await api.exportToNotion(brandId, planId)
        const msg = `Exported ${res.exported} of ${res.total} posts to Notion`
        setNotionResult(msg)
        if (notionTimerRef.current) clearTimeout(notionTimerRef.current)
        notionTimerRef.current = setTimeout(() => setNotionResult(null), 4000)
      }
    } catch (err: unknown) {
      setExportError((err as Error).message || 'Notion export failed')
    } finally {
      setNotionExporting(false)
    }
  }

  const isBusy = exporting || calDownloading || notionExporting

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <p style={{ fontSize: 13, color: A.textMuted, margin: 0 }}>
          All posts across all content plans
          {sorted.length > 0 && <span style={{ marginLeft: 8, fontWeight: 500 }}>({sorted.length} total)</span>}
        </p>

        {sorted.length > 0 && (
          <div ref={menuRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setMenuOpen(v => !v)}
              disabled={isBusy}
              style={{
                padding: '5px 14px', borderRadius: 6, border: 'none',
                background: isBusy ? A.surfaceAlt : `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                color: isBusy ? A.textMuted : 'white',
                fontSize: 12, fontWeight: 600, cursor: isBusy ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: 5,
              }}
            >
              {isBusy
                ? (exporting ? 'Exporting...' : calDownloading ? 'Downloading...' : 'Syncing...')
                : <>Export & Share <span style={{ fontSize: 10, opacity: 0.7 }}>▾</span></>
              }
            </button>

            {menuOpen && (
              <div style={{
                position: 'absolute', right: 0, top: 'calc(100% + 6px)', zIndex: 50,
                minWidth: 250, borderRadius: 10, padding: 4,
                background: A.surface, border: `1px solid ${A.border}`,
                boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
              }}>
                <SectionLabel>Download</SectionLabel>
                <MenuItem
                  icon="↓"
                  label="ZIP with media"
                  desc="Captions, images & videos"
                  onClick={handleBulkExport}
                />
                <MenuItem
                  icon="📅"
                  label="Calendar (.ics)"
                  desc="Add to Google / Apple / Outlook"
                  onClick={handleDownloadCalendar}
                />
                <Divider />
                <SectionLabel>Publish</SectionLabel>
                <MenuItem
                  icon="📓"
                  label="Export to Notion"
                  desc="Sync posts to your database"
                  onClick={handleExportNotion}
                />
                <Divider />
                <SectionLabel>Share</SectionLabel>
                <MenuItem
                  icon="✉"
                  label="Email calendar"
                  desc="Send .ics invite to an inbox"
                  onClick={() => { setShowEmailInput(true); setMenuOpen(false) }}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {notionResult && (
        <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 6, background: A.emeraldLight, color: A.emerald, fontSize: 12, fontWeight: 500 }}>
          {notionResult}
        </div>
      )}
      {emailSent && (
        <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 6, background: A.emeraldLight, color: A.emerald, fontSize: 12, fontWeight: 500 }}>
          Calendar sent to {emailSent}
        </div>
      )}

      {showEmailInput && (
        <div style={{
          display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12,
          padding: '8px 12px', borderRadius: 8, background: A.surfaceAlt, border: `1px solid ${A.border}`,
        }}>
          <input
            type="email"
            value={emailAddr}
            onChange={e => setEmailAddr(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleEmailCalendar()
              if (e.key === 'Escape') { setShowEmailInput(false); setEmailAddr('') }
            }}
            placeholder="you@example.com"
            autoFocus
            style={{
              flex: 1, padding: '6px 10px', borderRadius: 6,
              border: `1px solid ${A.border}`, fontSize: 13,
              color: A.text, background: A.surface, outline: 'none',
            }}
          />
          <button
            onClick={handleEmailCalendar}
            disabled={emailSending || !emailAddr.trim()}
            style={{
              padding: '6px 14px', borderRadius: 6, border: 'none',
              background: emailSending || !emailAddr.trim() ? A.surfaceAlt : `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
              color: emailSending || !emailAddr.trim() ? A.textMuted : 'white',
              fontSize: 12, fontWeight: 600, cursor: emailSending || !emailAddr.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {emailSending ? 'Sending...' : 'Send'}
          </button>
          <button
            onClick={() => { setShowEmailInput(false); setEmailAddr('') }}
            style={{ padding: '4px 8px', border: 'none', background: 'transparent', color: A.textMuted, fontSize: 14, cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      {exportError && (
        <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 6, background: A.coral + '15', color: A.coral, fontSize: 12 }}>
          {exportError}
        </div>
      )}

      <div style={{ marginBottom: 12, marginTop: 12 }}>
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

      <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        {STATUS_FILTERS.map(f => (
          <Pill key={f.key} active={statusFilter === f.key} onClick={() => setStatusFilter(f.key)}>
            {f.label}
          </Pill>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        {uniquePlatforms.length > 1 && (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: A.textMuted }}>Platform:</span>
            <Pill active={activePlatformFilter === 'all'} onClick={() => setPlatformFilter('all')}>All</Pill>
            {uniquePlatforms.map(p => (
              <Pill key={p} active={activePlatformFilter === p} onClick={() => setPlatformFilter(p)}>{p}</Pill>
            ))}
          </div>
        )}
        {uniquePillars.length > 1 && (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: A.textMuted }}>Pillar:</span>
            <Pill active={activePillarFilter === 'all'} onClick={() => setPillarFilter('all')}>All</Pill>
            {uniquePillars.map(p => (
              <Pill key={p} active={activePillarFilter === p} onClick={() => setPillarFilter(p)}>
                {p.replace(/_/g, ' ')}
              </Pill>
            ))}
          </div>
        )}
      </div>

      {!loading && filtered.length > 0 && filtered.length !== sorted.length && (
        <div style={{ fontSize: 12, color: A.textMuted, marginBottom: 12 }}>
          Showing {Math.min(visibleCount, filtered.length)} of {filtered.length} matching posts
        </div>
      )}

      {loading && (
        <div style={{ padding: 60, textAlign: 'center', color: A.textSoft, fontSize: 14 }}>
          Loading library...
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
          <p style={{ margin: '0 0 16px' }}>No posts yet. Generate your first post to see it here.</p>
          {onQuickPost && (
            <button
              onClick={onQuickPost}
              style={{
                padding: '10px 20px', borderRadius: 8, border: 'none',
                background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                color: 'white', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              }}
            >
              + Create your first post
            </button>
          )}
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

      {!loading && paginated.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: isMobile ? 'repeat(auto-fill, minmax(140px, 1fr))' : isTablet ? 'repeat(auto-fill, minmax(160px, 1fr))' : 'repeat(auto-fill, minmax(200px, 1fr))',
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
