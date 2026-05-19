import { NavLink } from 'react-router-dom'
import { HealthDot } from './HealthDot'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'

const mobileItems = [
  { to: '/', label: 'Дашборд', end: true },
  { to: '/vacancies', label: 'Вакансії' },
  { to: '/resumes', label: 'Резюме' },
  { to: '/skills', label: 'Навички' },
  { to: '/salary', label: 'Зарплати' },
  { to: '/geography', label: 'Гео' },
]

export function Topbar() {
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
      </div>
    </header>
  )
}
