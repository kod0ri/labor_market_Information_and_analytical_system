import { Link } from 'react-router-dom'
import { useI18n } from '../lib/i18n'

export default function NotFoundPage() {
  const { t } = useI18n()
  return (
    <div className="reveal grid place-items-center py-24 text-center">
      <div>
        <div className="font-display text-7xl font-bold tracking-tight" style={{ color: 'var(--brand)' }}>
          404
        </div>
        <p className="mt-3 font-mono text-xs uppercase tracking-[0.18em] muted">
          {t('notfound.quip')}
        </p>
        <p className="muted mt-1 text-sm">{t('notfound.text')}</p>
        <Link to="/" className="btn-primary mt-6 inline-flex">
          {t('notfound.back')}
        </Link>
      </div>
    </div>
  )
}
