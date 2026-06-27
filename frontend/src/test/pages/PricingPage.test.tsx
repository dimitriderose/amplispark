import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import PricingPage from '../../pages/PricingPage'

describe('PricingPage', () => {
  it('renders Pricing heading', () => {
    render(<MemoryRouter><PricingPage /></MemoryRouter>)
    expect(screen.getByText('Pricing')).toBeInTheDocument()
  })

  it('renders coming soon message', () => {
    render(<MemoryRouter><PricingPage /></MemoryRouter>)
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument()
  })

  it('renders contact email link', () => {
    render(<MemoryRouter><PricingPage /></MemoryRouter>)
    expect(screen.getByText(/deepvalueanalysis\.io/i)).toBeInTheDocument()
  })
})
