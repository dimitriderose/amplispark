import { render } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: vi.fn().mockReturnValue(false),
  useIsTablet: vi.fn().mockReturnValue(false),
}))

import PageContainer from '../../components/ui/PageContainer'
import { useIsMobile, useIsTablet } from '../../hooks/useIsMobile'

describe('PageContainer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders children', () => {
    const { getByText } = render(
      <PageContainer>
        <span>Hello content</span>
      </PageContainer>
    )
    expect(getByText('Hello content')).toBeInTheDocument()
  })

  it('applies desktop padding when neither mobile nor tablet', () => {
    vi.mocked(useIsMobile).mockReturnValue(false)
    vi.mocked(useIsTablet).mockReturnValue(false)

    const { container } = render(<PageContainer><span>test</span></PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.style.padding).toBe('32px 24px')
  })

  it('applies mobile padding when isMobile is true', () => {
    vi.mocked(useIsMobile).mockReturnValue(true)
    vi.mocked(useIsTablet).mockReturnValue(false)

    const { container } = render(<PageContainer><span>test</span></PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.style.padding).toBe('16px 12px')
  })

  it('applies tablet padding when isTablet is true', () => {
    vi.mocked(useIsMobile).mockReturnValue(false)
    vi.mocked(useIsTablet).mockReturnValue(true)

    const { container } = render(<PageContainer><span>test</span></PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.style.padding).toBe('24px 16px')
  })

  it('overrides padding when padding prop is provided', () => {
    vi.mocked(useIsMobile).mockReturnValue(false)
    vi.mocked(useIsTablet).mockReturnValue(false)

    const { container } = render(<PageContainer padding="8px 4px"><span>test</span></PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.style.padding).toBe('8px 4px')
  })

  it('applies custom maxWidth', () => {
    const { container } = render(<PageContainer maxWidth={600}><span>test</span></PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.style.maxWidth).toBe('600px')
  })

  it('applies minHeight when provided', () => {
    const { container } = render(<PageContainer minHeight="100vh"><span>test</span></PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.style.minHeight).toBe('100vh')
  })
})
