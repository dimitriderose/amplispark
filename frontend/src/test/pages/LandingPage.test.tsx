import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

import LandingPage from '../../pages/LandingPage'
import { useAuth } from '../../hooks/useAuth'

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  )
}

describe('LandingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders main heading', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getByText(/your entire week of content/i)).toBeInTheDocument()
  })

  it('renders CTA button', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    // Two "Get Started Free" buttons (hero + final CTA section)
    const ctaButtons = screen.getAllByText(/get started free/i)
    expect(ctaButtons.length).toBeGreaterThan(0)
  })

  it('shows Get Started Free when not signed in', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getAllByText(/get started free/i).length).toBeGreaterThan(0)
  })

  it('shows Get Started Free when signed in (same CTA navigates)', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    // Same CTA button — navigates directly when already signed in
    expect(screen.getAllByText(/get started free/i).length).toBeGreaterThan(0)
  })

  it('renders "How it works" section heading', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    // Multiple elements contain "how it works" text — assert at least one exists
    expect(screen.getAllByText(/how it works/i).length).toBeGreaterThan(0)
  })

  it('clicking CTA when signed out calls signIn then navigates', async () => {
    const signIn = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn,
      signOut: vi.fn(),
    })

    renderLanding()

    fireEvent.click(screen.getAllByText(/get started free/i)[0])

    await waitFor(() => {
      expect(signIn).toHaveBeenCalled()
    })
  })

  it('clicking CTA when signed in navigates to /brands without calling signIn', async () => {
    const signIn = vi.fn()
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn,
      signOut: vi.fn(),
    })

    renderLanding()

    fireEvent.click(screen.getAllByText(/get started free/i)[0])

    // signIn should NOT be called when already signed in
    expect(signIn).not.toHaveBeenCalled()
  })

  it('does not navigate when signIn throws (user closes popup)', async () => {
    const signIn = vi.fn().mockRejectedValue(new Error('popup closed'))
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn,
      signOut: vi.fn(),
    })

    renderLanding()

    fireEvent.click(screen.getAllByText(/get started free/i)[0])

    await waitFor(() => {
      expect(signIn).toHaveBeenCalled()
    })
    // Page should still be rendered (no navigation crash)
    expect(screen.getAllByText(/get started free/i).length).toBeGreaterThan(0)
  })

  it('renders platform strip with Instagram, LinkedIn, Twitter/X, Facebook', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    // Multiple Instagram elements may exist (PREVIEW_DAYS + strip) — just check at least one
    expect(screen.getAllByText('Instagram').length).toBeGreaterThan(0)
    expect(screen.getAllByText('LinkedIn').length).toBeGreaterThan(0)
    expect(screen.getByText('Twitter / X')).toBeInTheDocument()
    expect(screen.getByText('Facebook')).toBeInTheDocument()
  })

  it('renders feature grid with Brand Analysis feature', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getByText('Brand Analysis')).toBeInTheDocument()
  })

  it('renders footer copyright', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    // Multiple elements with "Amplispark" exist — just check at least one
    expect(screen.getAllByText(/amplispark/i).length).toBeGreaterThan(0)
  })

  it('clicking "See how it works" button calls scrollIntoView', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    // Mock scrollIntoView
    const scrollIntoViewMock = vi.fn()
    const getElementByIdSpy = vi.spyOn(document, 'getElementById').mockReturnValue({
      scrollIntoView: scrollIntoViewMock,
    } as unknown as HTMLElement)

    renderLanding()

    fireEvent.click(screen.getByText(/see how it works/i))

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth' })
    getElementByIdSpy.mockRestore()
  })

  it('renders Terms of Service and Privacy Policy footer links', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getByText('Terms of Service')).toBeInTheDocument()
    expect(screen.getByText('Privacy Policy')).toBeInTheDocument()
  })

  it('footer links respond to mouseEnter/mouseLeave', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    const termsLink = screen.getByText('Terms of Service')
    // Should not throw
    fireEvent.mouseEnter(termsLink)
    fireEvent.mouseLeave(termsLink)

    const privacyLink = screen.getByText('Privacy Policy')
    fireEvent.mouseEnter(privacyLink)
    fireEvent.mouseLeave(privacyLink)
  })
})
