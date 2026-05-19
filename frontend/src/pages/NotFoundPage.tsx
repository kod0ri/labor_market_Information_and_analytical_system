import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="grid place-items-center py-24 text-center">
      <div>
        <div className="text-6xl font-extrabold text-brand-500">404</div>
        <p className="muted mt-2">Сторінку не знайдено</p>
        <Link to="/" className="btn-primary mt-6 inline-flex">
          На дашборд
        </Link>
      </div>
    </div>
  )
}
