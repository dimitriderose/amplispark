import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { A } from '../theme'

export default function NotionCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState(() => {
    if (searchParams.get('error')) return 'Notion authorization was cancelled.'
    if (!searchParams.get('code') || !searchParams.get('state')) return 'Missing authorization parameters.'
    return ''
  })

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state') // brand_id
    const errorParam = searchParams.get('error')

    if (errorParam) {
      setTimeout(() => navigate(state ? `/dashboard/${state}` : '/'), 2000)
      return
    }

    if (!code || !state) {
      setTimeout(() => navigate('/'), 2000)
      return
    }

    // Forward code + state to backend callback
    fetch(`/api/integrations/notion/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`, {
      redirect: 'manual', // Don't follow the 302 — handle it ourselves
    }).then(r => {
      if (r.type === 'opaqueredirect' || r.status === 302 || r.ok) {
        // Backend stored tokens and returned 302 to dashboard
        navigate(`/dashboard/${state}?notion=connected`)
      } else {
        return r.json().then(data => {
          setError(data.detail || 'Authorization failed')
        })
      }
    }).catch(() => {
      setError('Failed to complete Notion authorization')
    })
  }, [searchParams, navigate])

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <div style={{ textAlign: 'center' }}>
        {error ? (
          <>
            <p style={{ fontSize: 16, color: A.coral, marginBottom: 8 }}>{error}</p>
            <p style={{ fontSize: 13, color: A.textMuted }}>Redirecting...</p>
          </>
        ) : (
          <>
            <p style={{ fontSize: 16, color: A.text, marginBottom: 8 }}>Connecting to Notion...</p>
            <p style={{ fontSize: 13, color: A.textMuted }}>Please wait</p>
          </>
        )}
      </div>
    </div>
  )
}
