import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { ProtectedRoute } from './components/ProtectedRoute'
import { trackVisit } from './lib/track'
import AdminPage from './pages/AdminPage'
import ClientSearchPage from './pages/ClientSearchPage'
import DashboardPage from './pages/DashboardPage'
import GeographyPage from './pages/GeographyPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import SalaryPage from './pages/SalaryPage'
import SkillsPage from './pages/SkillsPage'

/**
 * Анонімний трекер відвідувачів: пінгує сервер при заході, зміні роуту та раз
 * на хвилину, поки вкладка активна. Так «онлайн» відпадає за ~5 хв неактивності.
 */
function VisitorTracker() {
  const location = useLocation()

  useEffect(() => {
    trackVisit(location.pathname)
  }, [location.pathname])

  useEffect(() => {
    const ping = () => {
      if (document.visibilityState === 'visible') trackVisit(window.location.pathname)
    }
    const interval = window.setInterval(ping, 60_000)
    document.addEventListener('visibilitychange', ping)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', ping)
    }
  }, [])

  return null
}

function Layout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-6 lg:px-8">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/salary" element={<SalaryPage />} />
            <Route path="/geography" element={<GeographyPage />} />
            <Route path="/search" element={<ClientSearchPage />} />
            <Route path="/admin" element={
              <ProtectedRoute><AdminPage /></ProtectedRoute>
            } />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <VisitorTracker />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={<Layout />} />
      </Routes>
    </AuthProvider>
  )
}
