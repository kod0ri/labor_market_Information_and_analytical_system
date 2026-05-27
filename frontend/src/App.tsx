import { Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { ProtectedRoute } from './components/ProtectedRoute'
import AdminPage from './pages/AdminPage'
import ClientSearchPage from './pages/ClientSearchPage'
import DashboardPage from './pages/DashboardPage'
import GeographyPage from './pages/GeographyPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import SalaryPage from './pages/SalaryPage'
import SkillsPage from './pages/SkillsPage'

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
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={<Layout />} />
      </Routes>
    </AuthProvider>
  )
}
