import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import PostHistory from '../components/PostHistory'
import PageContainer from '../components/ui/PageContainer'

export default function PostHistoryPage() {
  const { brandId } = useParams<{ brandId: string }>()
  const navigate = useNavigate()
  const { isSignedIn, loading: authLoading } = useAuth()

  useEffect(() => {
    if (!authLoading && !isSignedIn) navigate('/')
  }, [authLoading, isSignedIn, navigate])

  if (!brandId) return null

  return (
    <PageContainer maxWidth={1100}>
      <PostHistory brandId={brandId} />
    </PageContainer>
  )
}
