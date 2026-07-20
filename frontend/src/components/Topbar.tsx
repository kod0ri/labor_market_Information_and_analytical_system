import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useI18n } from '../lib/i18n'
import type { Lang } from '../lib/i18n'
import { HealthDot } from './HealthDot'
import { IconClose, IconMenu } from './Icon'
import { Logo } from './Logo'
import { NAV_ITEMS } from './nav'
import { SegmentedControl } from './SegmentedControl'
import { ThemeToggle } from './ThemeToggle'

// Верхня панель: адаптивна навігація (мобільна шухляда <lg, статичний Sidebar
// >=lg), перемикачі мови/теми, health-індикатор і, якщо залогинений, вихід.
export function Topbar() {
  const { token, user, logout } = useAuth()
  const { lang, setLang, t } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)

  // закрити drawer при зміні роуту
  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  // Escape + блокування скролу під відкритим drawer
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open])

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <header
        className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b
                   border-[var(--card-border)] bg-[var(--app-bg)]/90 px-3 backdrop-blur lg:h-16 lg:px-6"
        style={{ borderTop: '2px solid var(--topline)' }}
      >
        <div className="flex min-w-0 items-center gap-2 lg:hidden">
          <button
            type="button"
            className="btn h-10 w-10 p-0"
            aria-label={open ? t('topbar.closeMenu') : t('topbar.openMenu')}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <IconClose size={18} /> : <IconMenu size={18} />}
          </button>
          <Logo collapsed />
        </div>

        <div className="hidden font-mono text-[11px] uppercase tracking-[0.18em] muted lg:block">
          {t('topbar.tagline')}
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <HealthDot />
          <SegmentedControl<Lang>
            value={lang}
            onChange={setLang}
            segments={[
              { value: 'uk', label: 'UA' },
              { value: 'en', label: 'EN' },
            ]}
          />
          <ThemeToggle />
          {token && user && (
            <>
              <span
                className="hidden items-center gap-1.5 font-mono text-[11px] uppercase
                           tracking-[0.16em] muted sm:flex"
                title={t('topbar.admin')}
              >
                <span style={{ color: 'var(--brand)' }}>◆</span>
                {user.username}
              </span>
              <button type="button" className="btn" onClick={handleLogout}>
                {t('topbar.logout')}
              </button>
            </>
          )}
        </div>
      </header>

      {/* мобільний drawer - завжди в DOM (для transition при відкритті/закритті),
          pointer-events-none у закритому стані, щоб невидимий шар не
          перехоплював кліки по контенту під ним. */}
      <div
        className={`fixed inset-0 z-30 lg:hidden ${open ? '' : 'pointer-events-none'}`}
        aria-hidden={!open}
      >
        <div
          className={`absolute inset-0 bg-black/55 transition-opacity duration-200 ${
            open ? 'opacity-100' : 'opacity-0'
          }`}
          onClick={() => setOpen(false)}
        />
        <nav
          className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col border-r
                      border-[var(--card-border)] bg-[var(--app-bg)] transition-transform
                      duration-250 ease-out ${open ? 'translate-x-0' : '-translate-x-full'}`}
          style={{ borderTop: '2px solid var(--topline)' }}
          aria-label="Навігація"
        >
          <div className="flex h-14 items-center border-b border-[var(--card-border)] px-4">
            <Logo />
          </div>
          <div className="flex-1 space-y-px overflow-y-auto py-3">
            {NAV_ITEMS.map(({ to, labelKey, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `nav-link min-h-[44px] ${isActive ? 'nav-link-active' : ''}`
                }
              >
                <Icon size={16} />
                <span>{t(labelKey)}</span>
              </NavLink>
            ))}
          </div>
          <div className="border-t border-[var(--card-border)] p-4 font-mono text-[11px] muted">
            work.ua · robota.ua · dou.ua
          </div>
        </nav>
      </div>
    </>
  )
}
