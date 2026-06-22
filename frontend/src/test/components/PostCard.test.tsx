import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/client', () => import('../mocks/client'))
vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: vi.fn().mockReturnValue(false),
}))

import PostCard from '../../components/PostCard'
import type { Post } from '../../hooks/usePostLibrary'

const basePost: Post = {
  post_id: 'post-1',
  caption: 'Check out our latest product launch!',
  platform: 'instagram',
  status: 'complete',
  day_index: 0,
  hashtags: ['launch', 'newproduct'],
  image_url: undefined,
  plan_id: 'plan-1',
  brief_index: 0,
}

function renderCard(overrides: Partial<Post> = {}) {
  const post = { ...basePost, ...overrides }
  return render(
    <MemoryRouter>
      <PostCard post={post} brandId="brand-123" />
    </MemoryRouter>
  )
}

describe('PostCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock navigator.clipboard
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
  })

  it('renders caption text', () => {
    renderCard()
    expect(screen.getByText('Check out our latest product launch!')).toBeInTheDocument()
  })

  it('renders platform name', () => {
    renderCard()
    expect(screen.getByText('instagram')).toBeInTheDocument()
  })

  it('shows status badge', () => {
    renderCard()
    // STATUS_LABELS_DECORATED maps 'complete' to a decorated label
    // The status badge is always rendered — check that the element exists
    const badges = screen.getAllByText(/complete|✓/i)
    expect(badges.length).toBeGreaterThan(0)
  })

  it('copy button exists when post is complete with caption', () => {
    renderCard({ status: 'complete' })
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
  })

  it('approve button is visible when status is complete', () => {
    renderCard({ status: 'complete' })
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
  })

  it('does not show approve button when status is approved', () => {
    renderCard({ status: 'approved' })
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
  })

  it('shows No caption yet when caption is missing', () => {
    renderCard({ caption: undefined })
    expect(screen.getByText('No caption yet')).toBeInTheDocument()
  })

  it('renders image when image_url is provided', () => {
    renderCard({ image_url: 'https://example.com/img.png' })
    const img = screen.getByRole('img', { name: /post visual/i })
    expect(img).toHaveAttribute('src', 'https://example.com/img.png')
  })

  it('renders video element when video.url is provided (no image_url)', () => {
    renderCard({ image_url: undefined, video: { url: 'https://example.com/vid.mp4', job_id: 'j1' } as never })
    const video = document.querySelector('video')
    expect(video).not.toBeNull()
    expect(video?.getAttribute('src')).toBe('https://example.com/vid.mp4')
  })

  it('shows dismiss button for generating posts when onDismiss provided', () => {
    const onDismiss = vi.fn()
    render(
      <MemoryRouter>
        <PostCard post={{ ...basePost, status: 'generating' }} brandId="brand-123" onDismiss={onDismiss} />
      </MemoryRouter>
    )
    const dismissBtn = screen.getByTitle('Remove from view')
    expect(dismissBtn).toBeInTheDocument()
    fireEvent.click(dismissBtn)
    expect(onDismiss).toHaveBeenCalled()
  })

  it('shows dismiss button for failed posts when onDismiss provided', () => {
    const onDismiss = vi.fn()
    render(
      <MemoryRouter>
        <PostCard post={{ ...basePost, status: 'failed' }} brandId="brand-123" onDismiss={onDismiss} />
      </MemoryRouter>
    )
    expect(screen.getByTitle('Remove from view')).toBeInTheDocument()
  })

  it('does not show dismiss button when onDismiss not provided', () => {
    render(
      <MemoryRouter>
        <PostCard post={{ ...basePost, status: 'generating' }} brandId="brand-123" />
      </MemoryRouter>
    )
    expect(screen.queryByTitle('Remove from view')).not.toBeInTheDocument()
  })

  it('shows retry button for failed posts with plan_id and day_index', () => {
    renderCard({ status: 'failed', plan_id: 'plan-1', day_index: 0 })
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('does not show retry button when plan_id is null', () => {
    renderCard({ status: 'failed', plan_id: undefined })
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument()
  })

  it('retry button navigates to generate_url from api.regeneratePost', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.regeneratePost).mockResolvedValue({ generate_url: '/generate/plan-1/0?brand_id=brand-123' } as never)

    const { Routes, Route } = await import('react-router-dom')
    const { MemoryRouter: MR } = await import('react-router-dom')
    render(
      <MR initialEntries={['/']}>
        <Routes>
          <Route path="/" element={
            <PostCard post={{ ...basePost, status: 'failed', plan_id: 'plan-1', day_index: 0 }} brandId="brand-123" />
          } />
          <Route path="/generate/:planId/:dayIndex" element={<div>Generate Page</div>} />
        </Routes>
      </MR>
    )

    fireEvent.click(screen.getByRole('button', { name: /retry/i }))

    await waitFor(() => {
      expect(api.regeneratePost).toHaveBeenCalledWith('brand-123', 'post-1')
    })
  })

  it('retry button falls back to navigate when regeneratePost fails', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.regeneratePost).mockRejectedValue(new Error('Server error'))

    const { Routes, Route } = await import('react-router-dom')
    const { MemoryRouter: MR } = await import('react-router-dom')
    render(
      <MR initialEntries={['/']}>
        <Routes>
          <Route path="/" element={
            <PostCard post={{ ...basePost, status: 'failed', plan_id: 'plan-1', day_index: 0, brief_index: 0 }} brandId="brand-123" />
          } />
          <Route path="/generate/:planId/:dayIndex" element={<div>Generate Fallback</div>} />
        </Routes>
      </MR>
    )

    fireEvent.click(screen.getByRole('button', { name: /retry/i }))

    await waitFor(() => {
      expect(screen.getByText('Generate Fallback')).toBeInTheDocument()
    })
  })

  it('export button is shown for complete posts', () => {
    renderCard({ status: 'complete' })
    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
  })

  it('export button is shown for approved posts', () => {
    renderCard({ status: 'approved' })
    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
  })

  it('calls api.approvePost and onApproved when approve button clicked', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.approvePost).mockResolvedValue({} as never)
    const onApproved = vi.fn()

    render(
      <MemoryRouter>
        <PostCard post={basePost} brandId="brand-123" onApproved={onApproved} />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() => {
      expect(api.approvePost).toHaveBeenCalledWith('brand-123', 'post-1')
      expect(onApproved).toHaveBeenCalled()
    })
  })

  it('shows approve error inline when approvePost fails', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.approvePost).mockRejectedValue(new Error('Approval failed'))

    render(
      <MemoryRouter>
        <PostCard post={basePost} brandId="brand-123" />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() => {
      expect(screen.getByText('Approval failed')).toBeInTheDocument()
    })
  })

  it('shows export error inline when exportPost fails', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.exportPost).mockRejectedValue(new Error('Export failed'))

    render(
      <MemoryRouter>
        <PostCard post={basePost} brandId="brand-123" />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /export/i }))

    await waitFor(() => {
      expect(screen.getByText('Export failed')).toBeInTheDocument()
    })
  })

  it('clicking the error dismiss button clears the export error', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.exportPost).mockRejectedValue(new Error('Export failed'))

    render(
      <MemoryRouter>
        <PostCard post={basePost} brandId="brand-123" />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /export/i }))

    await waitFor(() => {
      expect(screen.getByText('Export failed')).toBeInTheDocument()
    })

    // Click the × dismiss button rendered next to the error — it has textContent '×'
    const allButtons = screen.getAllByRole('button')
    const dismissError = allButtons.find(b => b.textContent === '×')
    expect(dismissError).toBeDefined()
    fireEvent.click(dismissError!)

    await waitFor(() => {
      expect(screen.queryByText('Export failed')).not.toBeInTheDocument()
    })
  })

  it('shows hashtag overflow count when more than 3 hashtags', () => {
    renderCard({ hashtags: ['a', 'b', 'c', 'd', 'e'] })
    expect(screen.getByText('+2')).toBeInTheDocument()
  })

  it('shows approve error inline and can dismiss it', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.approvePost).mockRejectedValue(new Error('Approval failed'))

    render(
      <MemoryRouter>
        <PostCard post={basePost} brandId="brand-123" />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() => {
      expect(screen.getByText('Approval failed')).toBeInTheDocument()
    })

    // Dismiss the approve error
    const allButtons = screen.getAllByRole('button')
    const dismissError = allButtons.find(b => b.textContent === '×')
    expect(dismissError).toBeDefined()
    fireEvent.click(dismissError!)

    await waitFor(() => {
      expect(screen.queryByText('Approval failed')).not.toBeInTheDocument()
    })
  })

  it('copy button calls navigator.clipboard.writeText with caption and hashtags', async () => {
    renderCard({ status: 'complete', caption: 'Hello world', hashtags: ['tag1', 'tag2'] })

    fireEvent.click(screen.getByRole('button', { name: /copy/i }))

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Hello world\n\n#tag1 #tag2')
    })
  })

  it('copy button shows Copied state after successful copy', async () => {
    renderCard({ status: 'complete', caption: 'Hello world', hashtags: [] })

    fireEvent.click(screen.getByRole('button', { name: /copy/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument()
    })
  })

  it('copy button skips clipboard when navigator.clipboard is not available', () => {
    // Remove clipboard
    Object.defineProperty(navigator, 'clipboard', {
      value: undefined,
      writable: true,
      configurable: true,
    })

    renderCard({ status: 'complete', caption: 'Hello world' })
    // Should not throw
    fireEvent.click(screen.getByRole('button', { name: /copy/i }))
  })

  it('export error auto-dismisses after 5 seconds', async () => {
    vi.useFakeTimers()
    const { api } = await import('../../api/client')
    vi.mocked(api.exportPost).mockRejectedValue(new Error('Export failed'))

    render(
      <MemoryRouter>
        <PostCard post={basePost} brandId="brand-123" />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /export/i }))

    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByText('Export failed')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(6000)
    })

    expect(screen.queryByText('Export failed')).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('approve error auto-dismisses after 5 seconds', async () => {
    vi.useFakeTimers()
    const { api } = await import('../../api/client')
    vi.mocked(api.approvePost).mockRejectedValue(new Error('Approval failed'))

    render(
      <MemoryRouter>
        <PostCard post={basePost} brandId="brand-123" />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /approve/i }))

    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByText('Approval failed')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(6000)
    })

    expect(screen.queryByText('Approval failed')).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('copy timer is cleaned up on unmount', async () => {
    vi.useFakeTimers()
    const { unmount } = renderCard({ status: 'complete', caption: 'Test caption', hashtags: [] })

    // Trigger a copy to set the timer
    fireEvent.click(screen.getByRole('button', { name: /copy/i }))

    await act(async () => {
      await Promise.resolve()
    })

    // Unmount should clean up the timer without error
    unmount()
    // Advance timers — the cleared timer should not cause state updates
    act(() => {
      vi.advanceTimersByTime(2000)
    })

    vi.useRealTimers()
  })

  it('video element responds to mouseOver and mouseOut events', () => {
    renderCard({ image_url: undefined, video: { url: 'https://example.com/vid.mp4', job_id: 'j1' } as never })
    const video = document.querySelector('video') as HTMLVideoElement
    expect(video).not.toBeNull()

    // Mock play and pause to avoid JSDOM errors
    video.play = vi.fn().mockResolvedValue(undefined)
    video.pause = vi.fn()

    fireEvent.mouseOver(video)
    expect(video.play).toHaveBeenCalled()

    fireEvent.mouseOut(video)
    expect(video.pause).toHaveBeenCalled()
  })

  it('calls onView when clicking image area of a final post', () => {
    const onView = vi.fn()
    render(
      <MemoryRouter>
        <PostCard
          post={{ ...basePost, status: 'complete', image_url: 'https://example.com/img.png' }}
          brandId="brand-123"
          onView={onView}
        />
      </MemoryRouter>
    )
    // The image container div is clickable for final posts with onView
    const img = screen.getByRole('img', { name: /post visual/i })
    const imgContainer = img.closest('div')!
    fireEvent.click(imgContainer)
    expect(onView).toHaveBeenCalled()
  })
})
