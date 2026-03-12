import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { A } from '../theme'
import { useAuth } from '../hooks/useAuth'

export default function NavBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { user, isSignedIn, signIn, signOut } = useAuth()
  const [accountOpen, setAccountOpen] = useState(false)
  const accountRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) setAccountOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Extract brandId from dashboard/edit/export path segments, or from ?brand_id= on generate routes
  const dashboardMatch = location.pathname.match(/^\/dashboard\/([^/]+)/)
  const editMatch = location.pathname.match(/^\/edit\/([^/]+)/)
  const exportMatch = location.pathname.match(/^\/export\/([^/]+)/)
  const generateMatch = location.pathname.match(/^\/generate\//)
  const activeBrandId =
    (dashboardMatch && dashboardMatch[1]) ||
    (editMatch && editMatch[1]) ||
    (exportMatch && exportMatch[1]) ||
    (generateMatch && searchParams.get('brand_id')) ||
    null

  const staticLinks = [
    { path: '/', label: 'Home' },
    isSignedIn
      ? { path: '/brands', label: 'My Brands' }
      : { path: '/onboard', label: 'Get Started' },
  ]

  const isActive = (path: string) => location.pathname === path

  return (
    <nav style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 24px', borderBottom: `1px solid ${A.border}`,
      background: A.surface, position: 'sticky', top: 0, zIndex: 50,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
           onClick={() => navigate('/')}>
        <img src="/logo.svg" alt="Amplifi" style={{ width: 28, height: 28, borderRadius: 7 }} />
        <span style={{ fontSize: 17, fontWeight: 700, color: A.text, letterSpacing: -0.3 }}>
          Amplifi
        </span>
      </div>
      <div style={{ display: 'flex', gap: 2 }}>
        {staticLinks.map(({ path, label }) => (
          <button key={path} onClick={() => navigate(path)} style={{
            padding: '5px 12px', borderRadius: 6,
            background: isActive(path) ? A.indigoLight : 'transparent',
            border: 'none', cursor: 'pointer', fontSize: 13,
            color: isActive(path) ? A.indigo : A.textSoft,
            fontWeight: isActive(path) ? 600 : 400,
          }}>{label}</button>
        ))}
        {activeBrandId && (
          <button
            onClick={() => {
              // H-8: Include plan_id from sessionStorage so ExportPage loads the right plan ZIP
              const planId = sessionStorage.getItem(`amplifi_plan_${activeBrandId}`)
              const url = planId
                ? `/export/${activeBrandId}?plan_id=${planId}`
                : `/export/${activeBrandId}`
              navigate(url)
            }}
            style={{
              padding: '5px 12px', borderRadius: 6,
              background: location.pathname.startsWith('/export/') ? A.indigoLight : 'transparent',
              border: 'none', cursor: 'pointer', fontSize: 13,
              color: location.pathname.startsWith('/export/') ? A.indigo : A.textSoft,
              fontWeight: location.pathname.startsWith('/export/') ? 600 : 400,
            }}
          >
            Export
          </button>
        )}
      </div>

      {/* Account */}
      {isSignedIn && user ? (
        <div ref={accountRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setAccountOpen(!accountOpen)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 8,
              border: `1px solid ${A.border}`, background: 'transparent',
              cursor: 'pointer', fontSize: 12, fontWeight: 500, color: A.text,
            }}
          >
            {user.photoURL ? (
              <img src={user.photoURL} alt="" style={{ width: 22, height: 22, borderRadius: '50%' }} />
            ) : (
              <div style={{
                width: 22, height: 22, borderRadius: '50%',
                background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'white', fontSize: 10, fontWeight: 700,
              }}>
                {(user.displayName || user.email || '?')[0].toUpperCase()}
              </div>
            )}
            Account
          </button>
          {accountOpen && (
            <div style={{
              position: 'absolute', right: 0, top: '100%', marginTop: 6,
              background: A.surface, border: `1px solid ${A.border}`,
              borderRadius: 10, padding: 10, minWidth: 180,
              boxShadow: '0 8px 32px rgba(0,0,0,0.12)', zIndex: 100,
            }}>
              <div style={{ padding: '4px 8px', marginBottom: 6 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: A.text }}>
                  {user.displayName || 'User'}
                </div>
                {user.email && (
                  <div style={{ fontSize: 11, color: A.textMuted, marginTop: 2 }}>{user.email}</div>
                )}
              </div>
              <button
                onClick={() => { setAccountOpen(false); signOut(); navigate('/') }}
                style={{
                  width: '100%', padding: '6px 8px', borderRadius: 6,
                  border: 'none', background: 'transparent', cursor: 'pointer',
                  fontSize: 12, fontWeight: 500, color: A.text, textAlign: 'left',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = A.surfaceAlt)}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                Sign Out
              </button>
            </div>
          )}
        </div>
      ) : (
        <button
          onClick={signIn}
          style={{
            padding: '5px 14px', borderRadius: 8,
            border: `1px solid ${A.border}`, background: 'transparent',
            cursor: 'pointer', fontSize: 13, fontWeight: 500, color: A.text,
          }}
        >
          Sign in
        </button>
      )}
    </nav>
  )
}
