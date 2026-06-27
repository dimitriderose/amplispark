import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

const { mockJoinWaitlist } = vi.hoisted(() => ({ mockJoinWaitlist: vi.fn() }))
vi.mock('../../api/client', () => ({
  api: { joinWaitlist: mockJoinWaitlist },
}))

import LandingPage from '../../pages/LandingPage'
import { useAuth } from '../../hooks/useAuth'

const baseAuth = {
  role: null as null,
  betaExpired: false,
  usageCounters: null,
  userFetchError: false,
}

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
    mockJoinWaitlist.mockResolvedValue({ status: 'joined' })
  })

  it('renders main heading', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
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

  it('renders waitlist email form', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getAllByPlaceholderText(/you@example.com/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/join waitlist/i).length).toBeGreaterThan(0)
  })

  it('shows waitlist form when not signed in', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getAllByText(/join waitlist/i).length).toBeGreaterThan(0)
  })

  it('redirects to /waitlist when signed in but not approved', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <LandingPage />
      </MemoryRouter>
    )

    expect(screen.queryByText(/join waitlist/i)).not.toBeInTheDocument()
  })

  it('renders "How it works" section heading', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getAllByText(/how it works/i).length).toBeGreaterThan(0)
  })

  it('submitting waitlist form shows success state', async () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    const emailInput = screen.getAllByPlaceholderText(/you@example.com/i)[0]
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } })
    fireEvent.submit(emailInput.closest('form')!)

    await waitFor(() => {
      expect(screen.getAllByText(/you're on the list/i).length).toBeGreaterThan(0)
    })
    expect(mockJoinWaitlist).toHaveBeenCalledWith('test@example.com')
  })

  it('submitting waitlist form shows error state on failure', async () => {
    mockJoinWaitlist.mockRejectedValue(new Error('Server error'))
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    const emailInput = screen.getAllByPlaceholderText(/you@example.com/i)[0]
    fireEvent.change(emailInput, { target: { value: 'bad@example.com' } })
    fireEvent.submit(emailInput.closest('form')!)

    await waitFor(() => {
      expect(screen.getByText('Server error')).toBeInTheDocument()
    })
  })

  it('redirects to /brands when signed in and approved', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      role: 'beta' as unknown as null,
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <LandingPage />
      </MemoryRouter>
    )

    expect(screen.queryByText(/join waitlist/i)).not.toBeInTheDocument()
  })

  it('waitlist form renders in idle state initially', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getAllByText(/join waitlist/i).length).toBeGreaterThan(0)
  })

  it('renders platform strip with Instagram, LinkedIn, Twitter/X, Facebook', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getAllByText('Instagram').length).toBeGreaterThan(0)
    expect(screen.getAllByText('LinkedIn').length).toBeGreaterThan(0)
    expect(screen.getByText('Twitter / X')).toBeInTheDocument()
    expect(screen.getByText('Facebook')).toBeInTheDocument()
  })

  it('renders feature grid with Brand Analysis feature', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
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
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    expect(screen.getAllByText(/amplispark/i).length).toBeGreaterThan(0)
  })

  it('clicking "See how it works" button calls scrollIntoView', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

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
      ...baseAuth,
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
      ...baseAuth,
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    renderLanding()

    const termsLink = screen.getByText('Terms of Service')
    fireEvent.mouseEnter(termsLink)
    fireEvent.mouseLeave(termsLink)

    const privacyLink = screen.getByText('Privacy Policy')
    fireEvent.mouseEnter(privacyLink)
    fireEvent.mouseLeave(privacyLink)
  })
})
