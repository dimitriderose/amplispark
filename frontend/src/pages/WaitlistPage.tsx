import { Navigate, useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { useAuth } from '../hooks/useAuth'

export default function WaitlistPage() {
  const { loading, isSignedIn, role, betaExpired, signOut } = useAuth()
  const navigate = useNavigate()

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <p style={{ color: A.textMuted, fontSize: 14 }}>Loading...</p>
      </div>
    )
  }

  if (!isSignedIn) return <Navigate to="/" replace />

  if (role !== null && !betaExpired) return <Navigate to="/brands" replace />

  if (betaExpired) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{
          maxWidth: 480, width: '100%', margin: '0 24px',
          padding: 40, borderRadius: 16,
          background: A.surface, border: `1px solid ${A.border}`,
          textAlign: 'center',
        }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: A.text, marginBottom: 12 }}>
            Your beta period has ended
          </h1>
          <p style={{ fontSize: 15, color: A.textSoft, marginBottom: 32, lineHeight: 1.6 }}>
            Ready to keep going? Upgrade to continue.
          </p>
          <button
            onClick={() => navigate('/pricing')}
            style={{
              display: 'block', width: '100%', padding: '12px 24px',
              borderRadius: 10, border: 'none', cursor: 'pointer',
              background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
              color: 'white', fontSize: 15, fontWeight: 600, marginBottom: 12,
            }}
          >
            Upgrade
          </button>
          <button
            onClick={() => signOut()}
            style={{
              display: 'block', width: '100%', padding: '10px 24px',
              borderRadius: 10, border: `1px solid ${A.border}`,
              background: 'transparent', cursor: 'pointer',
              fontSize: 14, color: A.textSoft,
            }}
          >
            Sign Out
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <div style={{
        maxWidth: 480, width: '100%', margin: '0 24px',
        padding: 40, borderRadius: 16,
        background: A.surface, border: `1px solid ${A.border}`,
        textAlign: 'center',
      }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: A.text, marginBottom: 12 }}>
          You're on the list!
        </h1>
        <p style={{ fontSize: 15, color: A.textSoft, marginBottom: 32, lineHeight: 1.6 }}>
          We'll be in touch when your spot is ready.
        </p>
        <button
          onClick={() => signOut()}
          style={{
            display: 'block', width: '100%', padding: '10px 24px',
            borderRadius: 10, border: `1px solid ${A.border}`,
            background: 'transparent', cursor: 'pointer',
            fontSize: 14, color: A.textSoft,
          }}
        >
          Sign Out
        </button>
      </div>
    </div>
  )
}
