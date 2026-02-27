import { Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './components/NavBar'
import LandingPage from './pages/LandingPage'
import OnboardPage from './pages/OnboardPage'
import DashboardPage from './pages/DashboardPage'
import GeneratePage from './pages/GeneratePage'
import EditBrandPage from './pages/EditBrandPage'
import ExportPage from './pages/ExportPage'

export default function App() {
  return (
    <div style={{ minHeight: '100vh', background: '#FAFAF8' }}>
      <NavBar />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/onboard" element={<OnboardPage />} />
        <Route path="/dashboard/:brandId" element={<DashboardPage />} />
        <Route path="/edit/:brandId" element={<EditBrandPage />} />
        <Route path="/generate/:planId/:dayIndex" element={<GeneratePage />} />
        <Route path="/export/:brandId" element={<ExportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
