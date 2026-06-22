import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Spinner from '../../components/Spinner'

describe('Spinner', () => {
  it('renders with accessible role="status"', () => {
    render(<Spinner />)
    const el = screen.getByRole('status')
    expect(el).toBeInTheDocument()
  })

  it('has aria-label "Loading"', () => {
    render(<Spinner />)
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('renders with default size of 20', () => {
    render(<Spinner />)
    const el = screen.getByRole('status')
    // The size is applied via inline style
    expect(el).toHaveStyle({ width: '20px', height: '20px' })
  })

  it('respects custom size prop', () => {
    render(<Spinner size={48} />)
    const el = screen.getByRole('status')
    expect(el).toHaveStyle({ width: '48px', height: '48px' })
  })

  it('accepts a custom color prop without crashing', () => {
    render(<Spinner color="#FF0000" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('applies additional style prop', () => {
    render(<Spinner style={{ marginTop: '8px' }} />)
    const el = screen.getByRole('status')
    expect(el).toHaveStyle({ marginTop: '8px' })
  })

  it('does not duplicate amp-spin-style when rendered a second time', () => {
    // Render once to create the style element
    render(<Spinner />)
    const stylesBefore = document.querySelectorAll('#amp-spin-style').length

    // Render again — should not create another style element
    render(<Spinner />)
    const stylesAfter = document.querySelectorAll('#amp-spin-style').length

    expect(stylesAfter).toBe(stylesBefore)
  })
})
