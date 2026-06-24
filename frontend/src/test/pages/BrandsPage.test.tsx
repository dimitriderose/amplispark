import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../../api/client', () => import('../mocks/client'))

vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: vi.fn().mockReturnValue(false),
  useIsTablet: vi.fn().mockReturnValue(false),
}))

import BrandsPage from '../../pages/BrandsPage'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../api/client'

const mockBrands = [
  { brand_id: 'b1', business_name: 'Acme Corp', industry: 'Tech', analysis_status: 'complete' },
  { brand_id: 'b2', business_name: 'Fresh Bakery', industry: 'Food', analysis_status: 'analyzing' },
]

function renderPage() {
  return render(
    <MemoryRouter>
      <BrandsPage />
    </MemoryRouter>
  )
}

describe('BrandsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: signed-in user
    vi.mocked(useAuth).mockReturnValue({
      uid: 'user-123',
      user: { displayName: 'Alice', email: 'alice@example.com', photoURL: null },
      loading: false,
      isSignedIn: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })
  })

  it('shows loading state (returns null) while auth loading', () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: true,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })
    vi.mocked(api.listBrands).mockReturnValue(new Promise(() => {}) as never)

    const { container } = renderPage()
    // When loading=true the page returns null
    expect(container.firstChild).toBeNull()
  })

  it('renders brand cards when data is loaded', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: mockBrands } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    })

    expect(screen.getByText('Fresh Bakery')).toBeInTheDocument()
  })

  it('shows empty state when no brands', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: [] } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('No brands yet')).toBeInTheDocument()
    })
  })

  it('"New Brand" button is present', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: [] } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /new brand/i })).toBeInTheDocument()
    })
  })

  it('"Create Your Brand" heading is present', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: [] } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Create Your Brand')).toBeInTheDocument()
    })
  })

  it('calls navigate to / when not signed in (redirect behavior)', async () => {
    vi.mocked(useAuth).mockReturnValue({
      uid: null,
      user: null,
      loading: false,
      isSignedIn: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    })
    vi.mocked(api.listBrands).mockResolvedValue({ brands: [] } as never)

    // The page renders in MemoryRouter and calls navigate('/') via useEffect
    // We verify the page was rendered (the effect triggers the navigate call)
    // Using Routes + Route setup to allow navigation away
    const { Routes, Route } = await import('react-router-dom')
    render(
      <MemoryRouter initialEntries={['/brands']}>
        <Routes>
          <Route path="/brands" element={<BrandsPage />} />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    )

    // After navigation to '/', the home page should render instead
    await waitFor(() => {
      expect(screen.getByText('Home Page')).toBeInTheDocument()
    })
  })

  it('shows analysis status badge as Ready for complete brands', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: mockBrands } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Ready')).toBeInTheDocument()
    })
  })

  it('shows non-complete analysis status as badge text', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: mockBrands } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('analyzing')).toBeInTheDocument()
    })
  })

  it('renders pagination when more than PAGE_SIZE brands', async () => {
    const manyBrands = Array.from({ length: 6 }, (_, i) => ({
      brand_id: `b${i}`,
      business_name: `Brand ${i}`,
      industry: 'Tech',
      analysis_status: 'complete',
    }))
    vi.mocked(api.listBrands).mockResolvedValue({ brands: manyBrands } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
  })

  it('navigates to next page when Next is clicked', async () => {
    const manyBrands = Array.from({ length: 6 }, (_, i) => ({
      brand_id: `b${i}`,
      business_name: `Brand ${i}`,
      industry: 'Tech',
      analysis_status: 'complete',
    }))
    vi.mocked(api.listBrands).mockResolvedValue({ brands: manyBrands } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    await waitFor(() => {
      expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
    })
  })

  it('shows description fallback when business_name is missing', async () => {
    const brandNoName = [{
      brand_id: 'b-no-name',
      description: 'A lovely bakery description',
      industry: 'Food',
      analysis_status: 'complete',
    }]
    vi.mocked(api.listBrands).mockResolvedValue({ brands: brandNoName } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('A lovely bakery description')).toBeInTheDocument()
    })
  })

  it('handles api.listBrands failure gracefully', async () => {
    vi.mocked(api.listBrands).mockRejectedValue(new Error('Network error'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Create Your Brand')).toBeInTheDocument()
    })
    expect(screen.getByText('Could not load your brands. Please try again.')).toBeInTheDocument()
  })

  it('brand card hover events do not throw', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: mockBrands } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    })

    const brandButton = screen.getByText('Acme Corp').closest('button')!
    fireEvent.mouseEnter(brandButton)
    fireEvent.mouseLeave(brandButton)
    // Should not throw — just verify element still exists
    expect(brandButton).toBeInTheDocument()
  })

  it('clicking brand card navigates to /dashboard/:brandId', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: mockBrands } as never)

    const { Routes, Route } = await import('react-router-dom')
    render(
      <MemoryRouter initialEntries={['/brands']}>
        <Routes>
          <Route path="/brands" element={<BrandsPage />} />
          <Route path="/dashboard/:brandId" element={<div>Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Acme Corp').closest('button')!)

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })
  })

  it('"New Brand" button navigates to /onboard?new=true', async () => {
    vi.mocked(api.listBrands).mockResolvedValue({ brands: [] } as never)

    const { Routes, Route } = await import('react-router-dom')
    render(
      <MemoryRouter initialEntries={['/brands']}>
        <Routes>
          <Route path="/brands" element={<BrandsPage />} />
          <Route path="/onboard" element={<div>Onboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /new brand/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /new brand/i }))

    await waitFor(() => {
      expect(screen.getByText('Onboard')).toBeInTheDocument()
    })
  })

  it('navigates back to previous page when Previous is clicked', async () => {
    const manyBrands = Array.from({ length: 6 }, (_, i) => ({
      brand_id: `b${i}`,
      business_name: `Brand ${i}`,
      industry: 'Tech',
      analysis_status: 'complete',
    }))
    vi.mocked(api.listBrands).mockResolvedValue({ brands: manyBrands } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    })

    // Go to page 2
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => expect(screen.getByText('Page 2 of 2')).toBeInTheDocument())

    // Go back to page 1
    fireEvent.click(screen.getByRole('button', { name: /previous/i }))
    await waitFor(() => expect(screen.getByText('Page 1 of 2')).toBeInTheDocument())
  })

  it('shows Pending for brands with no analysis_status', async () => {
    const brandPending = [{
      brand_id: 'b-pending',
      business_name: 'Pending Brand',
      industry: 'Other',
      analysis_status: undefined,
    }]
    vi.mocked(api.listBrands).mockResolvedValue({ brands: brandPending } as never)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Pending')).toBeInTheDocument()
    })
  })
})
