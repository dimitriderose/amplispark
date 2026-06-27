import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: vi.fn().mockReturnValue(false),
}))

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: vi.fn().mockReturnValue({
    unreadCount: 0,
    notifications: [],
    listLoading: false,
    panelOpen: false,
    openPanel: vi.fn(),
    closePanel: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
  }),
}))

import NavBar from '../../components/NavBar'
import { useAuth } from '../../hooks/useAuth'
import { useIsMobile } from '../../hooks/useIsMobile'

const baseAuth = {
  role: null as null,
  betaExpired: false,
  usageCounters: null,
  userFetchError: false,
  signIn: vi.fn().mockResolvedValue(undefined),
}

function renderNavBar(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <NavBar />
    </MemoryRouter>,
  )
}

describe('NavBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "Home" link when not signed in', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.queryByText('My Brands')).not.toBeInTheDocument()
  })

  it('shows "My Brands" link when signed in', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    expect(screen.getByText('My Brands')).toBeInTheDocument()
    expect(screen.queryByText('Home')).not.toBeInTheDocument()
  })

  it('shows "Sign in" button when not signed in', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    expect(screen.getByText('Sign in')).toBeInTheDocument()
  })

  it('shows "Account" button when signed in', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    expect(screen.getByText('Account')).toBeInTheDocument()
  })

  it('always shows "Home" nav link', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    expect(screen.getByText('Home')).toBeInTheDocument()
  })

  it('renders the Amplispark brand name', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    expect(screen.getByText('Amplispark')).toBeInTheDocument()
  })

  it('shows user photo when photoURL is provided', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: 'https://example.com/photo.jpg' },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    const photo = document.querySelector('img[alt=""]') as HTMLImageElement
    expect(photo?.src).toContain('photo.jpg')
  })

  it('shows avatar SVG when photoURL is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    expect(screen.getByText('Account')).toBeInTheDocument()
    const imgs = document.querySelectorAll('img[alt=""]')
    expect(imgs.length).toBe(0)
  })

  it('opens account dropdown when Account button is clicked', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    fireEvent.click(screen.getByText('Account'))
    expect(screen.getByText('Sign Out')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
  })

  it('shows user display name in dropdown without email when email is absent', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Bob', email: null, photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    fireEvent.click(screen.getByText('Account'))
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.queryByText('alice@example.com')).not.toBeInTheDocument()
  })

  it('shows User as display name fallback when displayName is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: null, email: 'test@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    fireEvent.click(screen.getByText('Account'))
    expect(screen.getByText('User')).toBeInTheDocument()
  })

  it('sign out button calls signOut and closes dropdown', () => {
    const signOut = vi.fn()
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut,
    })

    renderNavBar()

    fireEvent.click(screen.getByText('Account'))
    fireEvent.click(screen.getByText('Sign Out'))
    expect(signOut).toHaveBeenCalled()
  })

  it('sign out button responds to hover events', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    fireEvent.click(screen.getByText('Account'))
    const signOutBtn = screen.getByText('Sign Out')
    fireEvent.mouseEnter(signOutBtn)
    fireEvent.mouseLeave(signOutBtn)
  })

  it('clicking outside closes dropdown (mousedown outside accountRef)', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    fireEvent.click(screen.getByText('Account'))
    expect(screen.getByText('Sign Out')).toBeInTheDocument()

    fireEvent.mouseDown(document.body)
    expect(screen.queryByText('Sign Out')).not.toBeInTheDocument()
  })

  it('shows brand name breadcrumb on /dashboard/:brandId path', () => {
    sessionStorage.setItem('amplifi_brandname_brand-abc', 'My Test Brand')

    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: null, photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/dashboard/brand-abc']}>
        <NavBar />
      </MemoryRouter>
    )

    sessionStorage.removeItem('amplifi_brandname_brand-abc')
  })

  it('calls signIn when sign in button is clicked', () => {
    const signIn = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn,
      signOut: vi.fn(),
    })

    renderNavBar()

    fireEvent.click(screen.getByText('Sign in'))
    expect(signIn).toHaveBeenCalled()
  })

  it('clicking logo navigates to /', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/brands']}>
        <Routes>
          <Route path="/brands" element={<NavBar />} />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    )

    fireEvent.click(screen.getByText('Amplispark').closest('div')!)
  })

  it('applies mobile padding when isMobile is true', () => {
    vi.mocked(useIsMobile).mockReturnValue(true)
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderNavBar()

    const nav = document.querySelector('nav')!
    expect(nav.style.padding).toBe('10px 12px')
  })

  it('renders generate path with brand_id from searchParams', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: null, photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })
    sessionStorage.setItem('amplifi_brandname_brand-abc', 'My Brand')

    render(
      <MemoryRouter initialEntries={['/generate/plan-1/0?brand_id=brand-abc']}>
        <NavBar />
      </MemoryRouter>
    )

    sessionStorage.removeItem('amplifi_brandname_brand-abc')
  })

  it('renders generate path without brand name when no sessionStorage entry', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: null, photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })
    sessionStorage.removeItem('amplifi_brandname_brand-xyz')

    render(
      <MemoryRouter initialEntries={['/generate/plan-1/0?brand_id=brand-xyz']}>
        <NavBar />
      </MemoryRouter>
    )

    expect(screen.getByText('Account')).toBeInTheDocument()
  })

  it('highlights active link on current path', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <NavBar />
      </MemoryRouter>
    )

    const homeBtn = screen.getByText('Home')
    expect(homeBtn).toBeInTheDocument()
  })
})
