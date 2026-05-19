import { Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import DashboardPage from './pages/DashboardPage'
import GeographyPage from './pages/GeographyPage'
import NotFoundPage from './pages/NotFoundPage'
import ResumesPage from './pages/ResumesPage'
import SalaryPage from './pages/SalaryPage'
import SkillsPage from './pages/SkillsPage'
import VacanciesPage from './pages/VacanciesPage'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-6 lg:px-8">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/vacancies" element={<VacanciesPage />} />
            <Route path="/resumes" element={<ResumesPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/salary" element={<SalaryPage />} />
            <Route path="/geography" element={<GeographyPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
