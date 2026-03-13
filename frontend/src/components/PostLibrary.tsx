import React from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { api } from '../api/client'
import PostCard from './PostCard'
import { usePostLibrary } from '../hooks/usePostLibrary'

type Filter = 'all' | 'approved' | 'complete' | 'generating' | 'failed'

interface Props {
  brandId: string
  planId?: string
  defaultFilter?: Filter
  notionReady?: boolean
}

export default function PostLibrary({ brandId, planId, defaultFilter = 'all', notionReady }: Props) {
  const navigate = useNavigate()
  const { posts, loading, error, refresh } = usePostLibrary(brandId, planId)
  const [filter, setFilter] = React.useState<Filter>(defaultFilter)
  const [platformFilter, setPlatformFilter] = React.useState<string>('all')
  const [exporting, setExporting] = React.useState(false)
  const [dismissed, setDismissed] = React.useState<Set<string>>(new Set())
  const [exportError, setExportError] = React.useState<string | null>(null)
  const [copyAllDone, setCopyAllDone] = React.useState(false)
  const copyAllTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const copiedCountRef = React.useRef(0)
  const [calDownloading, setCalDownloading] = React.useState(false)
  const [showEmailInput, setShowEmailInput] = React.useState(false)
  const [emailAddr, setEmailAddr] = React.useState('')
  const [emailSending, setEmailSending] = React.useState(false)
  const [emailSent, setEmailSent] = React.useState('')
  const emailSentTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const [notionExporting, setNotionExporting] = React.useState(false)
  const [notionResult, setNotionResult] = React.useState<string | null>(null)
  const notionTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const [menuOpen, setMenuOpen] = React.useState(false)
  const menuRef = React.useRef<HTMLDivElement>(null)

  // Close menu on outside click
  React.useEffect(() => {
    if (!menuOpen) return
    const handle = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [menuOpen])

  React.useEffect(() => {
    return () => {
      if (copyAllTimerRef.current) clearTimeout(copyAllTimerRef.current)
      if (emailSentTimerRef.current) clearTimeout(emailSentTimerRef.current)
      if (notionTimerRef.current) clearTimeout(notionTimerRef.current)
    }
  }, [])

  const FILTERS: { key: Filter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'approved', label: '✓ Approved' },
    { key: 'complete', label: 'Ready' },
    { key: 'generating', label: 'Generating' },
    { key: 'failed', label: 'Failed' },
  ]

  const visiblePosts = posts.filter(p => !dismissed.has(p.post_id))
  const statusFiltered = filter === 'all' ? visiblePosts : visiblePosts.filter(p => p.status === filter)
  const uniquePlatforms = Array.from(new Set(statusFiltered.map(p => p.platform).filter(Boolean))) as string[]
  // Auto-reset platform filter when it becomes invalid
  React.useEffect(() => {
    if (uniquePlatforms.length <= 1 || (platformFilter !== 'all' && !uniquePlatforms.includes(platformFilter))) {
      setPlatformFilter('all')
    }
  }, [uniquePlatforms.length, platformFilter, uniquePlatforms])
  const filtered = platformFilter === 'all' ? statusFiltered : statusFiltered.filter(p => p.platform === platformFilter)

  const handleCopyAll = () => {
    if (!navigator.clipboard || filtered.length === 0) return
    const withCaption = filtered.filter(p => p.caption)
    copiedCountRef.current = withCaption.length
    const lines = withCaption.map((p, i) => {
      const tags = (p.hashtags || []).map((h: string) => `#${h.replace(/^#/, '')}`).join(' ')
      const header = `[${i + 1}] ${p.platform ? p.platform.charAt(0).toUpperCase() + p.platform.slice(1) : 'Post'} · Day ${(p.day_index ?? 0) + 1}`
      return [header, p.caption, tags].filter(Boolean).join('\n\n')
    })
    const text = lines.join('\n\n---\n\n')
    navigator.clipboard.writeText(text).then(() => {
      if (copyAllTimerRef.current) clearTimeout(copyAllTimerRef.current)
      setCopyAllDone(true)
      copyAllTimerRef.current = setTimeout(() => setCopyAllDone(false), 1500)
    }).catch(() => {})
  }

  const handleBulkExport = async () => {
    if (!planId) return
    setMenuOpen(false)
    setExporting(true)
    setExportError(null)
    try {
      await api.exportPlan(planId, brandId)
    } catch (err: any) {
      setExportError(err.message || 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const handleDownloadCalendar = async () => {
    if (!planId) return
    setMenuOpen(false)
    setCalDownloading(true)
    setExportError(null)
    try {
      await api.downloadCalendar(brandId, planId)
    } catch (err: any) {
      setExportError(err.message || 'Calendar download failed')
    } finally {
      setCalDownloading(false)
    }
  }

  const handleEmailCalendar = async () => {
    if (!planId || !emailAddr.trim()) return
    setEmailSending(true)
    setExportError(null)
    try {
      await api.emailCalendar(brandId, planId, emailAddr.trim())
      setEmailSent(emailAddr.trim())
      setEmailAddr('')
      setShowEmailInput(false)
      if (emailSentTimerRef.current) clearTimeout(emailSentTimerRef.current)
      emailSentTimerRef.current = setTimeout(() => setEmailSent(''), 3000)
    } catch (err: any) {
      setExportError(err.message || 'Failed to send calendar email')
    } finally {
      setEmailSending(false)
    }
  }

  const handleExportNotion = async () => {
    if (!planId) return
    setMenuOpen(false)
    setNotionExporting(true)
    setExportError(null)
    setNotionResult(null)
    try {
      const res = await api.exportToNotion(brandId, planId)
      const msg = `Exported ${res.exported} of ${res.total} posts to Notion`
      setNotionResult(msg)
      if (notionTimerRef.current) clearTimeout(notionTimerRef.current)
      notionTimerRef.current = setTimeout(() => setNotionResult(null), 4000)
    } catch (err: any) {
      setExportError(err.message || 'Notion export failed')
    } finally {
      setNotionExporting(false)
    }
  }

  const isBusy = exporting || calDownloading || notionExporting

  // ── Dropdown menu item ──
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

  return (
    <div>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: A.text, margin: 0 }}>
          Post Library
          {visiblePosts.length > 0 && (
            <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 400, color: A.textMuted }}>
              {visiblePosts.length} posts
            </span>
          )}
        </h3>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button onClick={refresh} style={{
            padding: '5px 10px', borderRadius: 6, border: `1px solid ${A.border}`,
            background: 'transparent', color: A.textSoft, fontSize: 12, cursor: 'pointer',
          }}>↻</button>

          {filtered.length > 0 && (
            <button
              onClick={handleCopyAll}
              style={{
                padding: '5px 12px', borderRadius: 6,
                border: `1px solid ${copyAllDone ? A.emerald : A.border}`,
                background: copyAllDone ? A.emeraldLight : 'transparent',
                color: copyAllDone ? A.emerald : A.textSoft,
                fontSize: 12, fontWeight: copyAllDone ? 600 : 400, cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {copyAllDone ? `Copied ${copiedCountRef.current}` : 'Copy All'}
            </button>
          )}

          {/* Export & Share dropdown trigger */}
          {planId && visiblePosts.length > 0 && (
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
                    label={notionReady ? 'Export to Notion' : 'Notion'}
                    desc={notionReady ? 'Sync posts to your database' : 'Connect Notion first'}
                    onClick={handleExportNotion}
                    disabled={!notionReady}
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
      </div>

      {/* Success banners */}
      {notionResult && (
        <div style={{
          marginBottom: 12, padding: '8px 12px', borderRadius: 6,
          background: A.emeraldLight, color: A.emerald, fontSize: 12, fontWeight: 500,
        }}>
          {notionResult}
        </div>
      )}
      {emailSent && (
        <div style={{
          marginBottom: 12, padding: '8px 12px', borderRadius: 6,
          background: A.emeraldLight, color: A.emerald, fontSize: 12, fontWeight: 500,
        }}>
          Calendar sent to {emailSent}
        </div>
      )}

      {/* Inline email input */}
      {showEmailInput && (
        <div style={{
          display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12,
          padding: '8px 12px', borderRadius: 8, background: A.surfaceAlt,
          border: `1px solid ${A.border}`,
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
              background: emailSending || !emailAddr.trim()
                ? A.surfaceAlt
                : `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
              color: emailSending || !emailAddr.trim() ? A.textMuted : 'white',
              fontSize: 12, fontWeight: 600,
              cursor: emailSending || !emailAddr.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {emailSending ? 'Sending...' : 'Send'}
          </button>
          <button
            onClick={() => { setShowEmailInput(false); setEmailAddr('') }}
            style={{
              padding: '4px 8px', border: 'none', background: 'transparent',
              color: A.textMuted, fontSize: 14, cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Export error */}
      {exportError && (
        <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 6, background: A.coral + '15', color: A.coral, fontSize: 12 }}>
          {exportError}
        </div>
      )}

      {/* Status filter tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            style={{
              padding: '4px 10px', borderRadius: 16, fontSize: 12, cursor: 'pointer',
              border: filter === f.key ? 'none' : `1px solid ${A.border}`,
              background: filter === f.key ? A.indigo : 'transparent',
              color: filter === f.key ? 'white' : A.textSoft,
              fontWeight: filter === f.key ? 600 : 400,
            }}
          >
            {f.label}
            {f.key !== 'all' && visiblePosts.filter(p => p.status === f.key).length > 0 && (
              <span style={{ marginLeft: 4, opacity: 0.7 }}>
                ({visiblePosts.filter(p => p.status === f.key).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Platform filter */}
      {uniquePlatforms.length > 1 && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: A.textMuted, marginRight: 4 }}>Platform:</span>
          {['all', ...uniquePlatforms].map(p => (
            <button
              key={p}
              onClick={() => setPlatformFilter(p)}
              style={{
                padding: '3px 8px', borderRadius: 12, fontSize: 11, cursor: 'pointer',
                border: platformFilter === p ? 'none' : `1px solid ${A.border}`,
                background: platformFilter === p ? A.violet : 'transparent',
                color: platformFilter === p ? 'white' : A.textSoft,
                fontWeight: platformFilter === p ? 600 : 400,
                textTransform: 'capitalize',
              }}
            >
              {p === 'all' ? 'All' : p}
            </button>
          ))}
        </div>
      )}

      {/* Loading / error / empty states */}
      {loading && (
        <div style={{ padding: 40, textAlign: 'center', color: A.textSoft, fontSize: 14 }}>
          Loading posts...
        </div>
      )}
      {error && !loading && (
        <div style={{ padding: 20, borderRadius: 8, background: A.coral + '15', color: A.coral, fontSize: 13 }}>
          {error}
        </div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <div style={{
          padding: 40, textAlign: 'center', background: A.surfaceAlt,
          borderRadius: 10, color: A.textMuted, fontSize: 13,
        }}>
          {visiblePosts.length === 0
            ? 'No posts yet — generate some from the calendar above!'
            : `No ${filter} posts${platformFilter !== 'all' ? ` on ${platformFilter}` : ''}`}
        </div>
      )}

      {/* Grid */}
      {!loading && filtered.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 16,
        }}>
          {filtered.map(post => (
            <PostCard
              key={post.post_id}
              post={post}
              brandId={brandId}
              onApproved={refresh}
              onDismiss={
                post.status === 'generating' || post.status === 'failed'
                  ? () => setDismissed(prev => new Set([...prev, post.post_id]))
                  : undefined
              }
              onView={
                (post.status === 'complete' || post.status === 'approved') && planId
                  ? () => navigate(`/generate/${planId}/${post.day_index}?brand_id=${brandId}&post_id=${post.post_id}`)
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </div>
  )
}
