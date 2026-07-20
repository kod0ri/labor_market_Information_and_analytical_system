import { useI18n } from '../lib/i18n'

const SOURCES = [    // ті самі 3 джерела, що й у скраперах (src/scrapers/, src/sources/) - лише для посилань у футері
  { name: 'work.ua', url: 'https://www.work.ua' },
  { name: 'robota.ua', url: 'https://robota.ua' },
  { name: 'dou.ua', url: 'https://jobs.dou.ua' },
]

export function Footer() {
  const { t } = useI18n()

  return (
    <footer className="border-t border-[var(--card-border)] px-4 py-8 lg:px-8">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 sm:grid-cols-3">
        <div>
          <div className="t-label mb-3">{t('footer.about.title')}</div>
          <p className="muted text-xs leading-relaxed">{t('footer.about.text')}</p>
        </div>

        <div>
          <div className="t-label mb-3">{t('footer.sources.title')}</div>
          <ul className="space-y-1.5 font-mono text-xs">
            {SOURCES.map((s) => (
              <li key={s.name}>
                <a
                  href={s.url}
                  target="_blank"                          // відкриваємо джерело в новій вкладці
                  rel="noopener noreferrer"                  // безпека: сторінка-джерело не отримує доступ до window.opener
                  className="muted transition-colors hover:text-[var(--brand)]"
                >
                  {s.name} ↗
                </a>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="t-label mb-3">{t('footer.stack.title')}</div>
          <p className="muted text-xs leading-relaxed">{t('footer.stack.text')}</p>
        </div>
      </div>

      <div
        className="mx-auto mt-8 flex max-w-7xl flex-wrap items-center justify-between gap-2
                   border-t border-[var(--card-border)] pt-4 font-mono text-[11px] muted"
      >
        <span>
          © {new Date().getFullYear()}{' '}
          <span className="font-semibold" style={{ color: 'var(--brand)' }}>
            503work
          </span>
        </span>
        <span>{t('footer.note')}</span>
      </div>
    </footer>
  )
}
