import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import NavBar from './components/NavBar'
import ChunkErrorBoundary from './components/ChunkErrorBoundary'
import { useAuth } from './hooks/useAuth'

const LandingPage        = lazy(() => import('./pages/LandingPage'))
const BrandsPage         = lazy(() => import('./pages/BrandsPage'))
const OnboardPage        = lazy(() => import('./pages/OnboardPage'))
const DashboardPage      = lazy(() => import('./pages/DashboardPage'))
const GeneratePage       = lazy(() => import('./pages/GeneratePage'))
const EditBrandPage      = lazy(() => import('./pages/EditBrandPage'))
const ExportPage         = lazy(() => import('./pages/ExportPage'))
const PostHistoryPage    = lazy(() => import('./pages/PostHistoryPage'))
const TermsPage          = lazy(() => import('./pages/TermsPage'))
const PrivacyPage        = lazy(() => import('./pages/PrivacyPage'))
const NotionCallbackPage = lazy(() => import('./pages/NotionCallbackPage'))
const WaitlistPage       = lazy(() => import('./pages/WaitlistPage'))
const SettingsPage       = lazy(() => import('./pages/SettingsPage'))
const PricingPage        = lazy(() => import('./pages/PricingPage'))

function ProtectedRoute() {
  const { loading, isSignedIn, role, betaExpired, userFetchError } = useAuth()
  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}><p style={{ color: '#888', fontSize: 14 }}>Loading...</p></div>
  if (!isSignedIn) return <Navigate to="/waitlist" replace />
  if (userFetchError) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}><p style={{ color: '#888', fontSize: 14 }}>Unable to reach server. Please refresh to try again.</p></div>
  if (role === null) return <Navigate to="/waitlist" replace />
  if (betaExpired) return <Navigate to="/waitlist" replace />
  return <Outlet />
}

export default function App() {
  return (
    <div style={{ minHeight: '100vh', background: '#FAFAF8' }}>
      <NavBar />
      <ChunkErrorBoundary>
        <Suspense fallback={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
            <p style={{ color: '#888', fontSize: 14 }}>Loading...</p>
          </div>
        }>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/waitlist" element={<WaitlistPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/brands" element={<BrandsPage />} />
              <Route path="/onboard" element={<OnboardPage />} />
              <Route path="/dashboard/:brandId" element={<DashboardPage />} />
              <Route path="/edit/:brandId" element={<EditBrandPage />} />
              <Route path="/generate/:planId/:dayIndex" element={<GeneratePage />} />
              <Route path="/export/:brandId" element={<ExportPage />} />
              <Route path="/brands/:brandId/history" element={<PostHistoryPage />} />
              <Route path="/auth/notion/callback" element={<NotionCallbackPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/waitlist" replace />} />
          </Routes>
        </Suspense>
      </ChunkErrorBoundary>
    </div>
  )
}
