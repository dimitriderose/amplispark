import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import BrandProfileCard from '../../components/BrandProfileCard'

const completeBrand = {
  brand_id: 'brand-1',
  business_name: 'Acme Bakery',
  business_type: 'local_business',
  industry: 'Food & Beverage',
  tone: 'Friendly',
  colors: ['#FF5733', '#C70039'],
  target_audience: 'Local community',
  visual_style: 'Warm and inviting',
  image_style_directive: 'Warm tones with natural lighting',
  caption_style_directive: 'Conversational and welcoming',
  content_themes: ['Community', 'Freshness'],
  competitors: [],
  analysis_status: 'complete',
}

describe('BrandProfileCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders business name', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    expect(screen.getByText('Acme Bakery')).toBeInTheDocument()
  })

  it('shows analyzing state when analysis_status is analyzing', () => {
    const analyzingBrand = { ...completeBrand, analysis_status: 'analyzing' }
    render(<BrandProfileCard brand={analyzingBrand} onUpdate={vi.fn()} />)
    expect(screen.getByText('Analyzing your brand...')).toBeInTheDocument()
  })

  it('renders color swatches when colors are present', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    // Each color value is rendered as text below the swatch
    expect(screen.getByText('#FF5733')).toBeInTheDocument()
    expect(screen.getByText('#C70039')).toBeInTheDocument()
  })

  it('does not show color swatches when no colors provided', () => {
    const noBrand = { ...completeBrand, colors: [] }
    render(<BrandProfileCard brand={noBrand} onUpdate={vi.fn()} />)
    expect(screen.queryByText('#FF5733')).not.toBeInTheDocument()
  })

  it('shows industry field', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    expect(screen.getByText('Food & Beverage')).toBeInTheDocument()
  })

  it('shows Edit button when not editing', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
  })

  it('clicking Edit shows Cancel button and Save Changes button', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  it('clicking Cancel closes edit mode', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /save changes/i })).not.toBeInTheDocument()
  })

  it('clicking Save Changes calls onUpdate with draft values', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined)
    render(<BrandProfileCard brand={completeBrand} onUpdate={onUpdate} />)

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          industry: 'Food & Beverage',
          tone: 'Friendly',
        })
      )
    })
  })

  it('shows save error when onUpdate rejects', async () => {
    const onUpdate = vi.fn().mockRejectedValue(new Error('Server error'))
    render(<BrandProfileCard brand={completeBrand} onUpdate={onUpdate} />)

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(screen.getByText('Server error')).toBeInTheDocument()
    })
  })

  it('renders competitor names when competitors array is populated', () => {
    const brandWithCompetitors = { ...completeBrand, competitors: ['CompetitorA', 'CompetitorB'] }
    render(<BrandProfileCard brand={brandWithCompetitors} onUpdate={vi.fn()} />)
    expect(screen.getByText('CompetitorA')).toBeInTheDocument()
    expect(screen.getByText('CompetitorB')).toBeInTheDocument()
  })

  it('toggle switch hides competitors when clicked', () => {
    const brandWithCompetitors = { ...completeBrand, competitors: ['CompetitorA'] }
    render(<BrandProfileCard brand={brandWithCompetitors} onUpdate={vi.fn()} />)

    // Initially visible
    expect(screen.getByText('CompetitorA')).toBeInTheDocument()

    // Click the toggle switch
    const toggle = screen.getByRole('switch')
    fireEvent.click(toggle)

    // Competitor should now be hidden
    expect(screen.queryByText('CompetitorA')).not.toBeInTheDocument()
  })

  it('toggle switch calls onUpdate with show_competitors preference', () => {
    const onUpdate = vi.fn()
    const brandWithCompetitors = { ...completeBrand, competitors: ['CompetitorA'] }
    render(<BrandProfileCard brand={brandWithCompetitors} onUpdate={onUpdate} />)

    fireEvent.click(screen.getByRole('switch'))

    expect(onUpdate).toHaveBeenCalledWith({ ui_preferences: { show_competitors: false } })
  })

  it('respects initial show_competitors=false from ui_preferences', () => {
    const brandHidden = {
      ...completeBrand,
      competitors: ['CompetitorX'],
      ui_preferences: { show_competitors: false },
    }
    render(<BrandProfileCard brand={brandHidden} onUpdate={vi.fn()} />)
    // Competitor should be hidden by default
    expect(screen.queryByText('CompetitorX')).not.toBeInTheDocument()
  })

  it('syncs draft when brand prop changes', () => {
    const { rerender } = render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    expect(screen.getByText('Food & Beverage')).toBeInTheDocument()

    const updatedBrand = { ...completeBrand, industry: 'Healthcare' }
    rerender(<BrandProfileCard brand={updatedBrand} onUpdate={vi.fn()} />)

    expect(screen.getByText('Healthcare')).toBeInTheDocument()
  })

  it('shows dash for empty image_style_directive', () => {
    const brandNoDirective = { ...completeBrand, image_style_directive: '' }
    render(<BrandProfileCard brand={brandNoDirective} onUpdate={vi.fn()} />)
    // The empty string renders as '—'
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
  })

  it('renders content themes as tags', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    expect(screen.getByText('Community')).toBeInTheDocument()
    expect(screen.getByText('Freshness')).toBeInTheDocument()
  })

  it('can edit image_style_directive field in edit mode', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    // The textareas render in edit mode — find the one with the image_style_directive value
    const textareas = screen.getAllByRole('textbox') as HTMLTextAreaElement[]
    const imageDirectiveArea = textareas.find(t => t.value === 'Warm tones with natural lighting')
    expect(imageDirectiveArea).toBeDefined()
    fireEvent.change(imageDirectiveArea!, { target: { value: 'Dark moody studio lighting' } })
    expect(imageDirectiveArea!.value).toBe('Dark moody studio lighting')
  })

  it('can edit caption_style_directive field in edit mode', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    const textareas = screen.getAllByRole('textbox') as HTMLTextAreaElement[]
    const captionArea = textareas.find(t => t.value === 'Conversational and welcoming')
    expect(captionArea).toBeDefined()
    fireEvent.change(captionArea!, { target: { value: 'Bold and direct' } })
    expect(captionArea!.value).toBe('Bold and direct')
  })

  it('can edit industry field input in edit mode', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const industryInput = inputs.find(i => i.value === 'Food & Beverage')
    expect(industryInput).toBeDefined()
    fireEvent.change(industryInput!, { target: { value: 'Retail' } })
    expect(industryInput!.value).toBe('Retail')
  })

  it('save after editing calls onUpdate with updated values', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined)
    render(<BrandProfileCard brand={completeBrand} onUpdate={onUpdate} />)

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const industryInput = inputs.find(i => i.value === 'Food & Beverage')!
    fireEvent.change(industryInput, { target: { value: 'Retail' } })

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith(expect.objectContaining({ industry: 'Retail' }))
    })
  })

  it('can edit tone field in edit mode', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const toneInput = inputs.find(i => i.value === 'Friendly')
    expect(toneInput).toBeDefined()
    fireEvent.change(toneInput!, { target: { value: 'Formal' } })
    expect(toneInput!.value).toBe('Formal')
  })

  it('can edit target_audience field in edit mode', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const audienceInput = inputs.find(i => i.value === 'Local community')
    expect(audienceInput).toBeDefined()
    fireEvent.change(audienceInput!, { target: { value: 'Online shoppers' } })
    expect(audienceInput!.value).toBe('Online shoppers')
  })

  it('can edit visual_style field in edit mode', () => {
    render(<BrandProfileCard brand={completeBrand} onUpdate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    const vsInput = inputs.find(i => i.value === 'Warm and inviting')
    expect(vsInput).toBeDefined()
    fireEvent.change(vsInput!, { target: { value: 'Minimal and clean' } })
    expect(vsInput!.value).toBe('Minimal and clean')
  })
})
