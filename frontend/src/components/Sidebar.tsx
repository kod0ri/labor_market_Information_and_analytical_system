import { NavLink } from 'react-router-dom'
import {
  IconCoins,
  IconDashboard,
  IconMapPin,
  IconSearch,
  IconSettings,
  IconSparkles,
} from './Icon'
import { Logo } from './Logo'

const items = [
  { to: '/', label: 'Дашборд', icon: IconDashboard, end: true },
  { to: '/skills', label: 'Навички', icon: IconSparkles },
  { to: '/salary', label: 'Зарплати', icon: IconCoins },
  { to: '/geography', label: 'Географія', icon: IconMapPin },
  { to: '/search', label: 'Пошук', icon: IconSearch },
  { to: '/admin', label: 'Адмін', icon: IconSettings },
]

export function Sidebar() {
  return (
    <aside className="hidden lg:flex lg:w-64 lg:shrink-0 lg:flex-col lg:border-r lg:border-[var(--card-border)]">
      <div className="flex h-16 items-center px-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : ''}`
            }
          >
            <Icon size={16} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="p-4">
        <div className="rounded-lg border border-[var(--card-border)] p-3 text-xs muted">
          Джерело даних: <span className="font-semibold text-brand-500">work.ua</span>
          <div className="mt-1">Дані оновлюються через ETL-пайплайн</div>
        </div>
      </div>
    </aside>
  )
}
