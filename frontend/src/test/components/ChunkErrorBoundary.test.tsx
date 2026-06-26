import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Suspense, lazy, type ReactNode } from 'react'
import ChunkErrorBoundary from '../../components/ChunkErrorBoundary'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: vi.fn().mockReturnValue(false),
  useIsTablet: vi.fn().mockReturnValue(false),
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

function ThrowingChild({ error }: { error: unknown }): ReactNode {
  throw error
}

function renderWithBoundary(error: unknown) {
  return render(
    <ChunkErrorBoundary>
      <ThrowingChild error={error} />
    </ChunkErrorBoundary>
  )
}

const CHUNK_ERROR_MESSAGE = 'A new version of Amplispark was deployed. Reload to continue.'
const GENERIC_ERROR_MESSAGE = 'Something went wrong loading this page.'

describe('ChunkErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders children when no error occurs', () => {
    render(
      <ChunkErrorBoundary>
        <div>safe content</div>
      </ChunkErrorBoundary>
    )
    expect(screen.getByText('safe content')).toBeInTheDocument()
  })

  it('renders chunk-error message for ChunkLoadError by name', () => {
    const err = Object.assign(new Error('Loading chunk failed'), { name: 'ChunkLoadError' })
    renderWithBoundary(err)
    expect(screen.getByText(CHUNK_ERROR_MESSAGE)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reload/i })).toBeInTheDocument()
  })

  it('renders chunk-error message for Vite/Chrome failed-fetch message', () => {
    const err = new Error('Failed to fetch dynamically imported module: https://example.com/chunk.js')
    renderWithBoundary(err)
    expect(screen.getByText(CHUNK_ERROR_MESSAGE)).toBeInTheDocument()
  })

  it('renders chunk-error message for Safari module-script-failed message', () => {
    const err = new Error('Importing a module script failed')
    renderWithBoundary(err)
    expect(screen.getByText(CHUNK_ERROR_MESSAGE)).toBeInTheDocument()
  })

  it('renders chunk-error message for Firefox dynamically-imported-module message', () => {
    const err = new Error('error loading dynamically imported module')
    renderWithBoundary(err)
    expect(screen.getByText(CHUNK_ERROR_MESSAGE)).toBeInTheDocument()
  })

  it('renders generic error message for non-chunk Error', () => {
    renderWithBoundary(new Error('boom'))
    expect(screen.getByText(GENERIC_ERROR_MESSAGE)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reload/i })).toBeInTheDocument()
  })

  it('renders generic error message for non-chunk TypeError', () => {
    renderWithBoundary(new TypeError('Failed to fetch'))
    expect(screen.getByText(GENERIC_ERROR_MESSAGE)).toBeInTheDocument()
  })

  it('renders generic error message when a string is thrown', () => {
    renderWithBoundary('something broke')
    expect(screen.getByText(GENERIC_ERROR_MESSAGE)).toBeInTheDocument()
  })

  it('Reload button calls window.location.reload', () => {
    const reloadMock = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { ...window.location, reload: reloadMock },
      writable: true,
    })

    renderWithBoundary(new Error('boom'))
    fireEvent.click(screen.getByRole('button', { name: /reload/i }))
    expect(reloadMock).toHaveBeenCalledOnce()
  })

  it('componentDidCatch logs to console with boundary prefix', () => {
    const consoleSpy = vi.mocked(console.error)
    renderWithBoundary(new Error('test error'))
    const calls = consoleSpy.mock.calls.flat().join(' ')
    expect(calls).toContain('[ChunkErrorBoundary]')
  })

  it('NavBar stays in document while Suspense is pending inside ChunkErrorBoundary', async () => {
    const { useAuth } = await import('../../hooks/useAuth')
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })

    const NavBar = (await import('../../components/NavBar')).default
    const NeverResolves = lazy(() => new Promise<{ default: () => null }>(() => {}))

    render(
      <MemoryRouter>
        <NavBar />
        <ChunkErrorBoundary>
          <Suspense fallback={<p>Loading...</p>}>
            <NeverResolves />
          </Suspense>
        </ChunkErrorBoundary>
      </MemoryRouter>
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(screen.getByText('Amplispark')).toBeInTheDocument()
  })
})
