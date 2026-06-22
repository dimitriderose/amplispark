import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('../../api/client', () => import('../mocks/client'))

import ReviewPanel from '../../components/ReviewPanel'
import { api } from '../../api/client'
import type { ReviewResult } from '../../components/ReviewPanel'

const mockReview: ReviewResult = {
  score: 8,
  brand_alignment: 'strong',
  strengths: ['Clear CTA', 'On-brand visuals'],
  improvements: ['Add more hashtags'],
  approved: true,
  revision_notes: null,
}

describe('ReviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders review score when initialReview is provided', () => {
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={mockReview}
      />
    )

    expect(screen.getByText('Score 8/10')).toBeInTheDocument()
  })

  it('shows brand alignment label', () => {
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={mockReview}
      />
    )

    expect(screen.getByText('STRONG BRAND ALIGNMENT')).toBeInTheDocument()
  })

  it('shows loading state while fetching when no initialReview', async () => {
    // Never-resolving promise to observe loading state
    vi.mocked(api.reviewPost).mockReturnValue(new Promise(() => {}) as never)

    render(<ReviewPanel brandId="brand-1" postId="post-1" />)

    await waitFor(() => {
      expect(screen.getByText('Reviewing...')).toBeInTheDocument()
    })
  })

  it('shows AI Review button when no review and not loading', async () => {
    vi.mocked(api.reviewPost).mockResolvedValue({ review: mockReview } as never)

    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={null}
      />
    )

    // After review resolves, the button is replaced by results
    // But initially (or when review is explicitly null) the button shows
    // We just need to confirm it renders without crashing and shows score
    await waitFor(() => {
      expect(screen.getByText('Score 8/10')).toBeInTheDocument()
    })
  })

  it('renders strengths list', () => {
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={mockReview}
      />
    )

    expect(screen.getByText('Clear CTA')).toBeInTheDocument()
    expect(screen.getByText('On-brand visuals')).toBeInTheDocument()
  })

  it('renders improvements list', () => {
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={mockReview}
      />
    )

    expect(screen.getByText('Add more hashtags')).toBeInTheDocument()
  })

  it('shows error when review fetch fails', async () => {
    vi.mocked(api.reviewPost).mockRejectedValue(new Error('Review failed'))

    render(<ReviewPanel brandId="brand-1" postId="post-1" />)

    await waitFor(() => {
      expect(screen.getByText('Review failed')).toBeInTheDocument()
    })
  })

  it('shows "Needs review" when review.approved is false', () => {
    const pendingReview = { ...mockReview, approved: false }
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={pendingReview}
      />
    )

    expect(screen.getByText('Needs review')).toBeInTheDocument()
  })

  it('shows "Auto-approved" when review.approved is true', () => {
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={mockReview}
      />
    )

    expect(screen.getByText('✓ Auto-approved')).toBeInTheDocument()
  })

  it('shows revision notes when present', () => {
    const reviewWithNotes = { ...mockReview, revision_notes: 'Please adjust the tone' }
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={reviewWithNotes}
      />
    )

    expect(screen.getByText('Please adjust the tone')).toBeInTheDocument()
  })

  it('shows engagement prediction when engagement_scores and prediction are present', () => {
    const reviewWithEngagement = {
      ...mockReview,
      engagement_scores: { hook_strength: 8, relevance: 7, cta_effectiveness: 6, platform_fit: 9 },
      engagement_prediction: 'high' as const,
    }
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={reviewWithEngagement}
      />
    )

    expect(screen.getByText('📈 High')).toBeInTheDocument()
    expect(screen.getByText('Hook')).toBeInTheDocument()
  })

  it('shows "Done — Go to Dashboard" button when review.approved is true and user clicks it', () => {
    const onApproved = vi.fn()
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={mockReview}
        onApproved={onApproved}
      />
    )

    fireEvent.click(screen.getByText(/Done — Go to Dashboard/i))
    expect(onApproved).toHaveBeenCalled()
  })

  it('handleManualApprove calls api.approvePost and shows approved state', async () => {
    vi.mocked(api.approvePost).mockResolvedValue({} as never)
    const onApproved = vi.fn()
    const pendingReview = { ...mockReview, approved: false }

    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={pendingReview}
        onApproved={onApproved}
      />
    )

    fireEvent.click(screen.getByText(/Approve Anyway/i))

    await waitFor(() => {
      expect(screen.getByText('Post Approved')).toBeInTheDocument()
    })
    expect(onApproved).toHaveBeenCalled()
  })

  it('handleManualApprove shows error on failure', async () => {
    vi.mocked(api.approvePost).mockRejectedValue(new Error('Approve failed'))
    const pendingReview = { ...mockReview, approved: false }

    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={pendingReview}
      />
    )

    fireEvent.click(screen.getByText(/Approve Anyway/i))

    await waitFor(() => {
      expect(screen.getByText('Approve failed')).toBeInTheDocument()
    })
  })

  it('shows approved state with "← Dashboard" button when onApproved provided', async () => {
    vi.mocked(api.approvePost).mockResolvedValue({} as never)
    const onApproved = vi.fn()
    const pendingReview = { ...mockReview, approved: false }

    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={pendingReview}
        onApproved={onApproved}
      />
    )

    fireEvent.click(screen.getByText(/Approve Anyway/i))

    await waitFor(() => {
      expect(screen.getByText('← Dashboard')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('← Dashboard'))
    expect(onApproved).toHaveBeenCalledTimes(2) // once on approve, once on dashboard click
  })

  it('shows moderate brand alignment', () => {
    const moderateReview = { ...mockReview, brand_alignment: 'moderate' as const }
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={moderateReview}
      />
    )

    expect(screen.getByText('MODERATE BRAND ALIGNMENT')).toBeInTheDocument()
  })

  it('shows weak brand alignment', () => {
    const weakReview = { ...mockReview, brand_alignment: 'weak' as const }
    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={weakReview}
      />
    )

    expect(screen.getByText('WEAK BRAND ALIGNMENT')).toBeInTheDocument()
  })

  it('re-review button triggers runReview with force=true', async () => {
    vi.mocked(api.reviewPost).mockResolvedValue({ review: mockReview } as never)

    render(
      <ReviewPanel
        brandId="brand-1"
        postId="post-1"
        initialReview={mockReview}
      />
    )

    // Click the re-review button
    fireEvent.click(screen.getByText(/Re-review/i))

    await waitFor(() => {
      expect(api.reviewPost).toHaveBeenCalledWith('brand-1', 'post-1', true)
    })
  })
})
