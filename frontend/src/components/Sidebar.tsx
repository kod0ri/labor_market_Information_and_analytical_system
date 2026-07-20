import { NavLink } from 'react-router-dom'
import { useI18n } from '../lib/i18n'
import { Logo } from './Logo'
import { NAV_ITEMS } from './nav'

export function Sidebar() {
  const { t } = useI18n()

  // hidden lg:flex - десктопна навігація; на вужчих екранах Topbar показує
  // ті самі NAV_ITEMS у висувній шухляді (мобільне меню не дублюється тут).
  return (
    <aside className="hidden lg:flex lg:w-60 lg:shrink-0 lg:flex-col lg:border-r lg:border-[var(--card-border)]">
      <div className="flex h-16 items-center border-b border-[var(--card-border)] px-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-px py-3">
        {NAV_ITEMS.map(({ to, labelKey, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : ''}`
            }
          >
            <Icon size={15} />
            <span>{t(labelKey)}</span>
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-[var(--card-border)] p-4">
        <div className="font-mono text-[11px] leading-relaxed muted">
          <div className="t-label mb-2">{t('sidebar.sourceLabel')}</div>
          <div>
            <span className="font-semibold" style={{ color: 'var(--brand)' }}>work.ua</span>
            {' · robota.ua · dou.ua'}
          </div>
          <div>{t('sidebar.etl')}</div>
        </div>
      </div>
    </aside>
  )
}
