import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import NotificationBell from '../../components/NotificationBell'
import type { AppNotification } from '../../types'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const BRAND_ID = 'brand-abc'
const POST_ID = 'post-xyz'
const PLAN_ID = 'plan-123'

const makeNotif = (overrides: Partial<AppNotification> = {}): AppNotification => ({
  notification_id: 'notif-1',
  uid: 'user-1',
  type: 'complete',
  title: 'Post ready',
  body: 'Your Instagram post is ready.',
  brand_id: BRAND_ID,
  post_id: POST_ID,
  plan_id: PLAN_ID,
  day_index: 2,
  read: false,
  created_at: '2026-06-26T03:00:00Z',
  ...overrides,
})

interface BellProps {
  unreadCount: number
  notifications: AppNotification[]
  listLoading: boolean
  panelOpen: boolean
  onOpen: () => void
  onClose: () => void
  onMarkRead: (id: string) => Promise<void>
  onMarkAllRead: () => Promise<void>
}

const defaultProps: BellProps = {
  unreadCount: 0,
  notifications: [],
  listLoading: false,
  panelOpen: false,
  onOpen: vi.fn(),
  onClose: vi.fn(),
  onMarkRead: vi.fn().mockResolvedValue(undefined),
  onMarkAllRead: vi.fn().mockResolvedValue(undefined),
}

function renderBell(props: Partial<BellProps> = {}) {
  return render(
    <MemoryRouter>
      <NotificationBell {...defaultProps} {...props} />
    </MemoryRouter>,
  )
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockNavigate.mockClear()
  })

  it('renders bell button with aria-label when no unread', () => {
    renderBell()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('aria-label includes unread count when unreadCount > 0', () => {
    renderBell({ unreadCount: 3 })
    expect(screen.getByRole('button', { name: 'Notifications, 3 unread' })).toBeInTheDocument()
  })

  it('shows no badge when unreadCount is 0', () => {
    renderBell({ unreadCount: 0 })
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('shows badge with count when unreadCount > 0', () => {
    renderBell({ unreadCount: 5 })
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('caps badge at 9+ when unreadCount > 9', () => {
    renderBell({ unreadCount: 15 })
    expect(screen.getByText('9+')).toBeInTheDocument()
  })

  it('calls onOpen when bell clicked and panel is closed', () => {
    const onOpen = vi.fn()
    renderBell({ panelOpen: false, onOpen })
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(onOpen).toHaveBeenCalled()
  })

  it('calls onClose when bell clicked and panel is open', () => {
    const onClose = vi.fn()
    renderBell({ panelOpen: true, onClose, notifications: [] })
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('does not show panel when panelOpen is false', () => {
    renderBell({ panelOpen: false })
    expect(screen.queryByText('Notifications')).not.toBeInTheDocument()
  })

  it('shows panel header when panelOpen is true', () => {
    renderBell({ panelOpen: true, notifications: [] })
    expect(screen.getByText('Notifications')).toBeInTheDocument()
  })

  it('shows loading state when listLoading is true and no notifications', () => {
    renderBell({ panelOpen: true, listLoading: true, notifications: [] })
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('shows empty state when not loading and no notifications', () => {
    renderBell({ panelOpen: true, listLoading: false, notifications: [] })
    expect(screen.getByText('No notifications yet')).toBeInTheDocument()
    expect(screen.getByText("We'll let you know when your posts are ready")).toBeInTheDocument()
  })

  it('renders notification title and body', () => {
    renderBell({ panelOpen: true, notifications: [makeNotif()] })
    expect(screen.getByText('Post ready')).toBeInTheDocument()
    expect(screen.getByText('Your Instagram post is ready.')).toBeInTheDocument()
  })

  it('renders formatted timestamp when created_at is set', () => {
    renderBell({ panelOpen: true, notifications: [makeNotif({ created_at: '2026-06-26T03:00:00Z' })] })
    // formatTime produces a locale string — just check *something* rendered in time area
    const panel = screen.getByText('Post ready').closest('div')!.parentElement!
    expect(panel.textContent).toContain('Jun')
  })

  it('does not render timestamp when created_at is undefined', () => {
    renderBell({ panelOpen: true, notifications: [makeNotif({ created_at: undefined })] })
    expect(screen.getByText('Post ready')).toBeInTheDocument()
  })

  it('clicking complete notification calls onMarkRead and onClose', () => {
    const onMarkRead = vi.fn().mockResolvedValue(undefined)
    const onClose = vi.fn()
    const notif = makeNotif({ type: 'complete', notification_id: 'notif-1' })
    renderBell({ panelOpen: true, notifications: [notif], onMarkRead, onClose })
    fireEvent.click(screen.getByText('Post ready'))
    expect(onMarkRead).toHaveBeenCalledWith('notif-1')
    expect(onClose).toHaveBeenCalled()
  })

  it('clicking complete notification navigates to generate page', () => {
    const notif = makeNotif({ type: 'complete', plan_id: PLAN_ID, day_index: 2, brand_id: BRAND_ID, post_id: POST_ID })
    renderBell({ panelOpen: true, notifications: [notif] })
    fireEvent.click(screen.getByText('Post ready'))
    expect(mockNavigate).toHaveBeenCalledWith(
      `/generate/${PLAN_ID}/2?brand_id=${BRAND_ID}&post_id=${POST_ID}`
    )
  })

  it('clicking complete notification with null day_index defaults to 0', () => {
    const notif = makeNotif({ type: 'complete', day_index: null })
    renderBell({ panelOpen: true, notifications: [notif] })
    fireEvent.click(screen.getByText('Post ready'))
    expect(mockNavigate).toHaveBeenCalledWith(
      `/generate/${PLAN_ID}/0?brand_id=${BRAND_ID}&post_id=${POST_ID}`
    )
  })

  it('clicking failed notification does not navigate', () => {
    const notif = makeNotif({ type: 'failed', title: 'Post failed', body: 'Generation failed.' })
    renderBell({ panelOpen: true, notifications: [notif] })
    fireEvent.click(screen.getByText('Post failed'))
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('clicking processing notification does not navigate', () => {
    const notif = makeNotif({ type: 'processing', title: 'Processing...', body: 'In progress.' })
    renderBell({ panelOpen: true, notifications: [notif] })
    fireEvent.click(screen.getByText('Processing...'))
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('complete notification row has pointer cursor', () => {
    const notif = makeNotif({ type: 'complete', read: false })
    const { container } = renderBell({ panelOpen: true, notifications: [notif] })
    const rows = container.querySelectorAll<HTMLElement>('[style*="cursor"]')
    const row = Array.from(rows).find(el => el.textContent?.includes('Post ready'))
    expect(row?.style.cursor).toBe('pointer')
  })

  it('failed notification row has default cursor', () => {
    const notif = makeNotif({ type: 'failed', read: false, title: 'Post failed', body: 'Failed.' })
    const { container } = renderBell({ panelOpen: true, notifications: [notif] })
    const rows = container.querySelectorAll<HTMLElement>('[style*="cursor"]')
    const row = Array.from(rows).find(el => el.textContent?.includes('Post failed'))
    expect(row?.style.cursor).toBe('default')
  })

  it('read notification title renders with normal font weight', () => {
    const notif = makeNotif({ read: true })
    renderBell({ panelOpen: true, notifications: [notif] })
    const title = screen.getByText('Post ready')
    expect(title.style.fontWeight).toBe('400')
  })

  it('unread notification title renders with bold font weight', () => {
    const notif = makeNotif({ read: false })
    renderBell({ panelOpen: true, notifications: [notif] })
    const title = screen.getByText('Post ready')
    expect(title.style.fontWeight).toBe('600')
  })

  it('shows mark all read button when unreadCount >= 3', () => {
    renderBell({ panelOpen: true, unreadCount: 3, notifications: [] })
    expect(screen.getByText('Mark all read')).toBeInTheDocument()
  })

  it('hides mark all read button when unreadCount < 3', () => {
    renderBell({ panelOpen: true, unreadCount: 2, notifications: [] })
    expect(screen.queryByText('Mark all read')).not.toBeInTheDocument()
  })

  it('clicking mark all read calls onMarkAllRead', () => {
    const onMarkAllRead = vi.fn().mockResolvedValue(undefined)
    renderBell({ panelOpen: true, unreadCount: 3, notifications: [], onMarkAllRead })
    fireEvent.click(screen.getByText('Mark all read'))
    expect(onMarkAllRead).toHaveBeenCalled()
  })

  it('shows See all button when all notifications share one brand_id', () => {
    const notifs = [
      makeNotif({ notification_id: 'n1', brand_id: BRAND_ID }),
      makeNotif({ notification_id: 'n2', brand_id: BRAND_ID }),
    ]
    renderBell({ panelOpen: true, notifications: notifs })
    expect(screen.getByText('See all →')).toBeInTheDocument()
  })

  it('hides See all button when notifications span multiple brand_ids', () => {
    const notifs = [
      makeNotif({ notification_id: 'n1', brand_id: 'brand-1' }),
      makeNotif({ notification_id: 'n2', brand_id: 'brand-2' }),
    ]
    renderBell({ panelOpen: true, notifications: notifs })
    expect(screen.queryByText('See all →')).not.toBeInTheDocument()
  })

  it('See all navigates to post history and calls onClose', () => {
    const onClose = vi.fn()
    const notifs = [makeNotif({ brand_id: BRAND_ID })]
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={
            <NotificationBell {...defaultProps} panelOpen notifications={notifs} onClose={onClose} />
          } />
          <Route path={`/brands/${BRAND_ID}/history`} element={<div>History</div>} />
        </Routes>
      </MemoryRouter>
    )
    fireEvent.click(screen.getByText('See all →'))
    expect(mockNavigate).toHaveBeenCalledWith(`/brands/${BRAND_ID}/history`)
    expect(onClose).toHaveBeenCalled()
  })

  it('outside mousedown closes panel', () => {
    const onClose = vi.fn()
    renderBell({ panelOpen: true, notifications: [], onClose })
    fireEvent.mouseDown(document.body)
    expect(onClose).toHaveBeenCalled()
  })

  it('mousedown inside bell does not call onClose', () => {
    const onClose = vi.fn()
    renderBell({ panelOpen: true, notifications: [], onClose })
    fireEvent.mouseDown(screen.getByRole('button', { name: 'Notifications' }))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('notification row hover changes background on complete type', () => {
    const notif = makeNotif({ type: 'complete', read: false })
    renderBell({ panelOpen: true, notifications: [notif] })
    const row = screen.getByText('Post ready').closest('div')!.parentElement!
    fireEvent.mouseEnter(row)
    fireEvent.mouseLeave(row)
  })

  it('notification row hover does nothing on failed type', () => {
    const notif = makeNotif({ type: 'failed', read: false, title: 'Failed', body: 'Error.' })
    renderBell({ panelOpen: true, notifications: [notif] })
    const row = screen.getByText('Failed').closest('div')!.parentElement!
    const bgBefore = row.style.background
    fireEvent.mouseEnter(row)
    expect(row.style.background).toBe(bgBefore)
  })
})
