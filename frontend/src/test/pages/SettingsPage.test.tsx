import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

import SettingsPage from '../../pages/SettingsPage'
import { useAuth } from '../../hooks/useAuth'

function renderSettings() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>
  )
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders Settings heading', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('shows user display name and email', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
  })

  it('shows User role badge', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('User')).toBeInTheDocument()
  })

  it('shows Beta role badge for beta users', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'beta' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('Beta')).toBeInTheDocument()
  })

  it('shows usage counters for beta users with usageCounters', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'beta' as unknown as null,
      betaExpired: false,
      usageCounters: {
        quickPostsThisMonth: 2,
        calendarsThisMonth: 1,
        quickPostsLimit: 8,
        calendarsLimit: 4,
        daysRemaining: 20,
      },
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText(/quick posts this month/i)).toBeInTheDocument()
    expect(screen.getByText(/calendars this month/i)).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
  })

  it('renders without badge when role is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.queryByText('Beta')).not.toBeInTheDocument()
    expect(screen.queryByText('User')).not.toBeInTheDocument()
  })

  it('does not show Beta Usage section for non-beta users', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.queryByText(/beta usage/i)).not.toBeInTheDocument()
  })

  it('shows photo when photoURL is provided', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: 'https://example.com/photo.jpg' },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    const photo = document.querySelector('img[alt=""]') as HTMLImageElement
    expect(photo?.src).toContain('photo.jpg')
  })

  it('shows initials when no photoURL', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice Smith', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('AS')).toBeInTheDocument()
  })

  it('sign out button calls signOut', () => {
    const signOut = vi.fn()
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut,
    })

    renderSettings()

    fireEvent.click(screen.getByText('Sign Out'))
    expect(signOut).toHaveBeenCalled()
  })

  it('shows Admin badge for admin users', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Admin User', email: 'admin@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'admin' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getAllByText('Admin').length).toBeGreaterThan(0)
  })

  it('falls back to email initial when displayName is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: null, email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('shows beta usage without days remaining when daysRemaining is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'beta' as unknown as null,
      betaExpired: false,
      usageCounters: {
        quickPostsThisMonth: 1,
        calendarsThisMonth: 0,
        quickPostsLimit: 0,
        calendarsLimit: 0,
        daysRemaining: null,
      },
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText(/quick posts this month/i)).toBeInTheDocument()
    expect(screen.queryByText(/days remaining/i)).not.toBeInTheDocument()
  })

  it('uses fallback limits of 8 and 4 when limits are null', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'beta' as unknown as null,
      betaExpired: false,
      usageCounters: {
        quickPostsThisMonth: 2,
        calendarsThisMonth: 1,
        quickPostsLimit: null,
        calendarsLimit: null,
        daysRemaining: 15,
      },
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('2 / 8')).toBeInTheDocument()
    expect(screen.getByText('1 / 4')).toBeInTheDocument()
  })

  it('shows U initial and User display fallback when displayName and email are both null', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: null, email: null, photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      usageCounters: null,
      userFetchError: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderSettings()

    expect(screen.getByText('U')).toBeInTheDocument()
    expect(screen.getAllByText('User').length).toBeGreaterThan(0)
  })
})
