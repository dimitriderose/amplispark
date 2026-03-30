import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api/client'
import OnboardWizard from '../components/OnboardWizard'

export default function OnboardPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { uid, loading: authLoading } = useAuth()
  const [checking, setChecking] = useState(true)

  const isNewBrand = searchParams.get('new') === 'true'

  useEffect(() => {
    if (authLoading) return
    if (isNewBrand || !uid) {
      setChecking(false)
      return
    }
    api.listBrands(uid)
      .then((res) => {
        const brands = (res as unknown as { brands: unknown[] }).brands || []
        if (brands.length > 0) {
          navigate('/brands', { replace: true })
        } else {
          setChecking(false)
        }
      })
      .catch(() => {
        setChecking(false)
      })
  }, [authLoading, uid, isNewBrand, navigate])

  if (authLoading || checking) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <p style={{ color: '#888', fontSize: 14 }}>Loading...</p>
      </div>
    )
  }

  return <OnboardWizard />
}
