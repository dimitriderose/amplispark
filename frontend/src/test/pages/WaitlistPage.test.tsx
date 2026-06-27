import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

import WaitlistPage from '../../pages/WaitlistPage'
import { useAuth } from '../../hooks/useAuth'

const baseAuth = {
  uid: null as null,
  user: null as null,
  usageCounters: null,
  userFetchError: false,
  signIn: vi.fn(),
}

function renderWaitlist() {
  return render(
    <MemoryRouter>
      <WaitlistPage />
    </MemoryRouter>
  )
}

describe('WaitlistPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('redirects to / when not signed in', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      loading: false,
      isSignedIn: false,
      role: null,
      betaExpired: false,
      signOut: vi.fn(),
    })

    renderWaitlist()

    expect(screen.queryByText(/you're on the list/i)).not.toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      loading: true,
      isSignedIn: false,
      role: null,
      betaExpired: false,
      signOut: vi.fn(),
    })

    renderWaitlist()

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows on-the-list message for signed in unapproved user', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: null,
      betaExpired: false,
      signOut: vi.fn(),
    })

    renderWaitlist()

    expect(screen.getByText(/you're on the list/i)).toBeInTheDocument()
    expect(screen.getByText(/we'll be in touch/i)).toBeInTheDocument()
  })

  it('shows beta expired message with Upgrade button', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'beta' as unknown as null,
      betaExpired: true,
      signOut: vi.fn(),
    })

    renderWaitlist()

    expect(screen.getByText(/your beta period has ended/i)).toBeInTheDocument()
    expect(screen.getByText('Upgrade')).toBeInTheDocument()
  })

  it('sign out button calls signOut on unapproved page', () => {
    const signOut = vi.fn()
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: null,
      betaExpired: false,
      signOut,
    })

    renderWaitlist()

    fireEvent.click(screen.getByText('Sign Out'))
    expect(signOut).toHaveBeenCalled()
  })

  it('sign out button calls signOut on beta expired page', () => {
    const signOut = vi.fn()
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'beta' as unknown as null,
      betaExpired: true,
      signOut,
    })

    renderWaitlist()

    fireEvent.click(screen.getByText('Sign Out'))
    expect(signOut).toHaveBeenCalled()
  })

  it('redirects to /brands when signed in and approved', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      role: 'user' as unknown as null,
      betaExpired: false,
      signOut: vi.fn(),
    })

    renderWaitlist()

    expect(screen.queryByText(/you're on the list/i)).not.toBeInTheDocument()
  })
})
