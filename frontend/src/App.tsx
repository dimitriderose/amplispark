import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import NavBar from './components/NavBar'
import LandingPage from './pages/LandingPage'
import BrandsPage from './pages/BrandsPage'
import OnboardPage from './pages/OnboardPage'
import DashboardPage from './pages/DashboardPage'
import GeneratePage from './pages/GeneratePage'
import EditBrandPage from './pages/EditBrandPage'
import ExportPage from './pages/ExportPage'
import PostHistoryPage from './pages/PostHistoryPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import NotionCallbackPage from './pages/NotionCallbackPage'
import { useAuth } from './hooks/useAuth'

function ProtectedRoute() {
  const { loading, isSignedIn } = useAuth()

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <p style={{ color: '#888', fontSize: 14 }}>Loading...</p>
      </div>
    )
  }

  if (!isSignedIn) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}

export default function App() {
  return (
    <div style={{ minHeight: '100vh', background: '#FAFAF8' }}>
      <NavBar />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/brands" element={<BrandsPage />} />
          <Route path="/onboard" element={<OnboardPage />} />
          <Route path="/dashboard/:brandId" element={<DashboardPage />} />
          <Route path="/edit/:brandId" element={<EditBrandPage />} />
          <Route path="/generate/:planId/:dayIndex" element={<GeneratePage />} />
          <Route path="/export/:brandId" element={<ExportPage />} />
          <Route path="/brands/:brandId/history" element={<PostHistoryPage />} />
          <Route path="/auth/notion/callback" element={<NotionCallbackPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
