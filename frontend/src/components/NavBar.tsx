import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { A } from '../theme'

export default function NavBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()

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
    { path: '/onboard', label: 'Get Started' },
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
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, color: 'white', fontWeight: 700,
        }}>A</div>
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
    </nav>
  )
}
