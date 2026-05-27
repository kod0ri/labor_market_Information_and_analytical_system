import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { HealthDot } from './HealthDot'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'

const mobileItems = [
  { to: '/', label: 'Дашборд', end: true },
  { to: '/skills', label: 'Навички' },
  { to: '/salary', label: 'Зарплати' },
  { to: '/geography', label: 'Гео' },
  { to: '/search', label: 'Пошук' },
]

export function Topbar() {
  const { token, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-[var(--card-border)] bg-[var(--app-bg)]/85 px-4 backdrop-blur lg:px-6">
      <div className="flex items-center gap-3 lg:hidden">
        <Logo collapsed />
      </div>
      <nav className="flex gap-1 overflow-x-auto lg:hidden">
        {mobileItems.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.end}
            className={({ isActive }) =>
              `rounded-md px-2.5 py-1.5 text-xs font-medium ${
                isActive ? 'bg-brand-500/15 text-brand-500' : 'muted'
              }`
            }
          >
            {it.label}
          </NavLink>
        ))}
      </nav>
      <div className="hidden lg:block" />
      <div className="flex items-center gap-3">
        <HealthDot />
        <ThemeToggle />
        {token && (
          <button type="button" className="btn text-xs" onClick={handleLogout}>
            Вийти
          </button>
        )}
      </div>
    </header>
  )
}
