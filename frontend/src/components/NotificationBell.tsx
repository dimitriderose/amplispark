import { useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import type { AppNotification } from '../types'

interface Props {
  unreadCount: number
  notifications: AppNotification[]
  listLoading: boolean
  panelOpen: boolean
  onOpen: () => void
  onClose: () => void
  onMarkRead: (id: string) => Promise<void>
  onMarkAllRead: () => Promise<void>
}

export default function NotificationBell({
  unreadCount,
  notifications,
  listLoading,
  panelOpen,
  onOpen,
  onClose,
  onMarkRead,
  onMarkAllRead,
}: Props) {
  const navigate = useNavigate()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const handleNotificationClick = (n: AppNotification) => {
    if (n.type !== 'complete') return
    onMarkRead(n.notification_id)
    onClose()
    const dayIdx = n.day_index ?? 0
    navigate(`/generate/${n.plan_id}/${dayIdx}?brand_id=${n.brand_id}&post_id=${n.post_id}`)
  }

  const rowBackground = (n: AppNotification) => {
    if (n.read) return 'transparent'
    if (n.type === 'failed') return 'rgba(255,107,107,0.08)'
    return A.indigoLight
  }

  const dotColor = (n: AppNotification) => {
    if (n.type === 'complete') return A.emerald
    if (n.type === 'failed') return A.coral
    return A.textMuted
  }

  const formatTime = (iso?: string) => {
    if (!iso) return ''
    const d = new Date(iso)
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => (panelOpen ? onClose() : onOpen())}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        style={{
          position: 'relative', padding: '4px 8px', borderRadius: 8,
          border: `1px solid ${A.border}`, background: 'transparent',
          cursor: 'pointer', display: 'flex', alignItems: 'center',
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke={A.textSoft} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute', top: 2, right: 2,
            background: A.coral, color: '#fff',
            borderRadius: '50%', fontSize: 10, fontWeight: 700,
            minWidth: 16, height: 16, lineHeight: '16px',
            textAlign: 'center', padding: '0 3px',
          }}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {panelOpen && (
        <div style={{
          position: 'absolute', right: 0, top: '100%', marginTop: 6,
          background: A.surface, border: `1px solid ${A.border}`,
          borderRadius: 10, width: 320,
          boxShadow: '0 8px 32px rgba(0,0,0,0.12)', zIndex: 100,
          overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 14px', borderBottom: `1px solid ${A.border}`,
          }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: A.text }}>Notifications</span>
            {unreadCount >= 3 && (
              <button onClick={onMarkAllRead} style={{
                fontSize: 11, color: A.indigo, background: 'none',
                border: 'none', cursor: 'pointer', fontWeight: 500,
              }}>
                Mark all read
              </button>
            )}
          </div>

          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            {listLoading && notifications.length === 0 && (
              <div style={{ padding: 20, textAlign: 'center', fontSize: 13, color: A.textMuted }}>
                Loading…
              </div>
            )}
            {!listLoading && notifications.length === 0 && (
              <div style={{ padding: '24px 14px', textAlign: 'center' }}>
                <div style={{ fontSize: 13, color: A.text, fontWeight: 500 }}>No notifications yet</div>
                <div style={{ fontSize: 12, color: A.textMuted, marginTop: 4 }}>
                  We'll let you know when your posts are ready
                </div>
              </div>
            )}
            {notifications.map(n => (
              <div
                key={n.notification_id}
                onClick={() => handleNotificationClick(n)}
                style={{
                  padding: '10px 14px',
                  cursor: n.type === 'complete' ? 'pointer' : 'default',
                  background: rowBackground(n),
                  borderBottom: `1px solid ${A.border}`,
                  display: 'flex', gap: 10, alignItems: 'flex-start',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => {
                  if (n.type === 'complete') e.currentTarget.style.background = A.surfaceAlt
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = rowBackground(n)
                }}
              >
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                  background: dotColor(n),
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: n.read ? 400 : 600, color: A.text }}>
                    {n.title}
                  </div>
                  <div style={{ fontSize: 12, color: A.textSoft, marginTop: 2 }}>{n.body}</div>
                  {n.created_at && (
                    <div style={{ fontSize: 11, color: A.textMuted, marginTop: 4 }}>
                      {formatTime(n.created_at)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {notifications.length > 0 && (() => {
            const brandIds = [...new Set(notifications.map(n => n.brand_id))]
            const singleBrandId = brandIds.length === 1 ? brandIds[0] : null
            return singleBrandId ? (
              <div style={{ padding: '8px 14px', borderTop: `1px solid ${A.border}`, textAlign: 'right' }}>
                <button
                  onClick={() => {
                    navigate(`/brands/${singleBrandId}/history`)
                    onClose()
                  }}
                  style={{
                    fontSize: 12, color: A.indigo, background: 'none',
                    border: 'none', cursor: 'pointer', fontWeight: 500,
                  }}
                >
                  See all →
                </button>
              </div>
            ) : null
          })()}
        </div>
      )}
    </div>
  )
}
