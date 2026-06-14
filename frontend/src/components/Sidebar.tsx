import { NavLink } from 'react-router-dom'
import { Logo } from './Logo'
import { NAV_ITEMS } from './nav'

export function Sidebar() {
  return (
    <aside className="hidden lg:flex lg:w-60 lg:shrink-0 lg:flex-col lg:border-r lg:border-[var(--card-border)]">
      <div className="flex h-16 items-center border-b border-[var(--card-border)] px-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-px py-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : ''}`
            }
          >
            <Icon size={15} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-[var(--card-border)] p-4">
        <div className="font-mono text-[11px] leading-relaxed muted">
          <div className="t-label mb-2">джерело</div>
          <div>
            src: <span className="font-semibold" style={{ color: 'var(--brand)' }}>work.ua</span>
          </div>
          <div>etl: work.ua → llm → sql</div>
        </div>
      </div>
    </aside>
  )
}
