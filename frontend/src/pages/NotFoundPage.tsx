import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="reveal grid place-items-center py-24 text-center">
      <div>
        <div className="font-display text-7xl font-bold tracking-tight" style={{ color: 'var(--brand)' }}>
          404
        </div>
        <p className="mt-3 font-mono text-xs uppercase tracking-[0.18em] muted">
          очікували 503? цього разу — not found
        </p>
        <p className="muted mt-1 text-sm">Такої сторінки не існує</p>
        <Link to="/" className="btn-primary mt-6 inline-flex">
          → на дашборд
        </Link>
      </div>
    </div>
  )
}
