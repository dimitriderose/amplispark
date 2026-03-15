import { useIsMobile, useIsTablet } from '../../hooks/useIsMobile'

interface Props {
  maxWidth?: number
  minHeight?: string
  padding?: string
  children: React.ReactNode
}

export default function PageContainer({ maxWidth = 1400, minHeight, padding, children }: Props) {
  const isMobile = useIsMobile()
  const isTablet = useIsTablet()
  return (
    <div style={{
      maxWidth,
      margin: '0 auto',
      padding: padding || (isMobile ? '16px 12px' : isTablet ? '24px 16px' : '32px 24px'),
      minHeight,
    }}>
      {children}
    </div>
  )
}
