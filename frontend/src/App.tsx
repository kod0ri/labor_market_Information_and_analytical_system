// Корінь застосунку: провайдери (i18n → auth → router) обгортають Layout з
// сайдбаром/топбаром і Suspense-межею довкола лінивих сторінок. /login живе
// ОКРЕМО від Layout (без сайдбара), решта роутів - усередині ProtectedRoute
// там, де потрібна авторизація (лише /admin).

import { lazy, Suspense, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Footer } from './components/Footer'
import { Sidebar } from './components/Sidebar'
import { Loading } from './components/States'
import { Topbar } from './components/Topbar'
import { ProtectedRoute } from './components/ProtectedRoute'
import { I18nProvider } from './lib/i18n'
import { trackVisit } from './lib/track'

// Code splitting: кожна сторінка — окремий чанк, головний бандл без recharts
// для сторінок, які його не використовують.
const AdminPage = lazy(() => import('./pages/AdminPage'))
const ClientSearchPage = lazy(() => import('./pages/ClientSearchPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const GeographyPage = lazy(() => import('./pages/GeographyPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const SalaryPage = lazy(() => import('./pages/SalaryPage'))
const SkillsPage = lazy(() => import('./pages/SkillsPage'))

/**
 * Анонімний трекер відвідувачів: пінгує сервер при заході, зміні роуту та раз
 * на хвилину, поки вкладка активна. Так «онлайн» відпадає за ~5 хв неактивності.
 */
function VisitorTracker() {
  const location = useLocation()   // з react-router - міняється при кожній навігації SPA

  useEffect(() => {
    trackVisit(location.pathname)    // пінг одразу при заході й при кожній зміні шляху
  }, [location.pathname])

  useEffect(() => {
    const ping = () => {
      if (document.visibilityState === 'visible') trackVisit(window.location.pathname)   // не пінгуємо, поки вкладка в фоні
    }
    const interval = window.setInterval(ping, 60_000)             // додатковий пінг раз/хв, поки сторінка відкрита
    document.addEventListener('visibilitychange', ping)           // миттєвий пінг при поверненні у вкладку
    return () => {                                                  // очищення при розмонтуванні компонента
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', ping)
    }
  }, [])   // порожній масив залежностей - інтервал і слухач ставляться один раз на весь час життя застосунку

  return null   // компонент без візуального виводу - лише побічний ефект (beacon)
}

function PageFallback() {
  return (
    <div className="mx-auto max-w-7xl">
      <Loading rows={6} />
    </div>
  )
}

function Layout() {
  return (
    // min-w-0 на flex-1-контейнері - без нього flex-діти (таблиці/графіки
    // з довгим вмістом) можуть розпирати батьківський flex-item за межі
    // viewport замість того, щоб самі отримати внутрішній скрол.
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-6 lg:px-8">
          <ErrorBoundary>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/skills" element={<SkillsPage />} />
                <Route path="/salary" element={<SalaryPage />} />
                <Route path="/geography" element={<GeographyPage />} />
                <Route path="/search" element={<ClientSearchPage />} />
                {/* єдиний роут, що вимагає токен */}
                <Route path="/admin" element={
                  <ProtectedRoute><AdminPage /></ProtectedRoute>
                } />
                <Route path="*" element={<NotFoundPage />} />   {/* будь-який неспівпадаючий шлях - 404 */}
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
        <Footer />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <VisitorTracker />
        <Routes>
          <Route
            path="/login"
            element={
              <Suspense fallback={<PageFallback />}>
                <LoginPage />
              </Suspense>
            }
          />
          <Route path="/*" element={<Layout />} />
        </Routes>
      </AuthProvider>
    </I18nProvider>
  )
}
