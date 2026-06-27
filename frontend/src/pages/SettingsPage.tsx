import { A } from '../theme'
import { useAuth } from '../hooks/useAuth'

const ROLE_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  beta: { label: 'Beta', color: A.amber, bg: A.amberLight },
  user: { label: 'User', color: A.emerald, bg: A.emeraldLight },
  admin: { label: 'Admin', color: A.indigo, bg: A.indigoLight },
}

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div style={{ height: 6, background: A.surfaceAlt, borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${pct}%`, background: A.indigo, borderRadius: 4 }} />
    </div>
  )
}

function InitialsCircle({ name }: { name: string }) {
  const initials = name
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
  return (
    <div style={{
      width: 56, height: 56, borderRadius: '50%',
      background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'white', fontSize: 20, fontWeight: 700,
    }}>
      {initials}
    </div>
  )
}

export default function SettingsPage() {
  const { user, role, usageCounters, signOut } = useAuth()

  const badge = role ? ROLE_BADGE[role] : null

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '48px 24px' }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, color: A.text, marginBottom: 32 }}>Settings</h1>

      <div style={{
        padding: 28, borderRadius: 14,
        background: A.surface, border: `1px solid ${A.border}`,
        marginBottom: 20,
      }}>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: A.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 20 }}>
          Account
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          {user?.photoURL ? (
            <img src={user.photoURL} alt="" style={{ width: 56, height: 56, borderRadius: '50%' }} />
          ) : (
            <InitialsCircle name={user?.displayName || user?.email || 'U'} />
          )}
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: A.text }}>
              {user?.displayName || 'User'}
            </div>
            {user?.email && (
              <div style={{ fontSize: 13, color: A.textMuted, marginTop: 2 }}>{user.email}</div>
            )}
          </div>
          {badge && (
            <div style={{
              marginLeft: 'auto',
              padding: '3px 10px', borderRadius: 12,
              background: badge.bg, color: badge.color,
              fontSize: 12, fontWeight: 600,
            }}>
              {badge.label}
            </div>
          )}
        </div>
      </div>

      {role === 'beta' && usageCounters && (
        <div style={{
          padding: 28, borderRadius: 14,
          background: A.surface, border: `1px solid ${A.border}`,
          marginBottom: 20,
        }}>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: A.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 20 }}>
            Beta Usage
          </h2>

          {usageCounters.daysRemaining !== null && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 14, color: A.textSoft, marginBottom: 4 }}>
                Days remaining in beta
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: A.text }}>
                {usageCounters.daysRemaining}
              </div>
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 14, color: A.textSoft }}>Quick Posts this month</span>
              <span style={{ fontSize: 14, fontWeight: 600, color: A.text }}>
                {usageCounters.quickPostsThisMonth} / {usageCounters.quickPostsLimit ?? 8}
              </span>
            </div>
            <ProgressBar
              value={usageCounters.quickPostsThisMonth}
              max={usageCounters.quickPostsLimit ?? 8}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 14, color: A.textSoft }}>Calendars this month</span>
              <span style={{ fontSize: 14, fontWeight: 600, color: A.text }}>
                {usageCounters.calendarsThisMonth} / {usageCounters.calendarsLimit ?? 4}
              </span>
            </div>
            <ProgressBar
              value={usageCounters.calendarsThisMonth}
              max={usageCounters.calendarsLimit ?? 4}
            />
          </div>
        </div>
      )}

      <button
        onClick={() => signOut()}
        style={{
          padding: '10px 24px', borderRadius: 10,
          border: `1px solid ${A.border}`, background: 'transparent',
          cursor: 'pointer', fontSize: 14, color: A.textSoft,
        }}
      >
        Sign Out
      </button>
    </div>
  )
}
