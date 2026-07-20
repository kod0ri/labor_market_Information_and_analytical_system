import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiPost } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Logo } from '../components/Logo'

interface LoginResponse {
  access_token: string
  username: string
}

// Єдина форма входу в застосунку - немає публічної реєстрації (акаунти
// заводить адмін через CLI, src/auth/router.py), тож ця сторінка веде
// лише до /admin, більше нікуди захищеного немає.
export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')       // текст помилки під формою - порожній рядок означає "нема помилки"
  const [loading, setLoading] = useState(false)  // блокує кнопку й показує "Вхід…" на час запиту

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()          // без цього браузер сам перезавантажив би сторінку (стандартна поведінка <form>)
    setLoading(true)
    setError('')                // скидаємо попередню помилку перед новою спробою
    try {
      const data = await apiPost<LoginResponse>('/api/auth/login', { username, password })
      login(data.access_token)                    // кладе токен у контекст авторизації (і localStorage - див. AuthContext.tsx)
      navigate('/admin', { replace: true })         // replace - щоб "назад" не повертало на /login з уже валідним токеном
    } catch (err) {
      // 401 від бекенду навмисно НЕ розрізняє "нема такого логіна" від
      // "невірний пароль" (user enumeration захист, src/auth/router.py) -
      // фронтенд так само показує один спільний текст для обох випадків.
      if (err instanceof ApiError) {
        setError(err.status === 401 ? 'Невірний логін або пароль' : err.message)
      } else {
        setError('Не вдалося підключитись до сервера')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--app-bg)] px-4">
      <div className="reveal w-full max-w-sm">
        <div className="mb-6 flex justify-center">
          <Logo />
        </div>

        <div className="card">
          {/* статус-рядок термінала */}
          <div
            className="flex items-center justify-between border-b border-[var(--card-border)] px-5 py-2.5
                       font-mono text-[11px] uppercase tracking-[0.18em] muted"
          >
            <span>/api/admin</span>
            <span style={{ color: 'var(--brand)' }}>401 → auth</span>
          </div>

          <div className="p-5 sm:p-7">
            <h1 className="font-display text-lg font-semibold tracking-tight">
              Вхід в адмінку
            </h1>
            <p className="muted mt-1 text-xs">Доступ лише для оператора системи</p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <label className="block">
                <div className="t-label mb-1.5">логін</div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input font-mono"
                  autoComplete="username"
                  required
                  autoFocus
                />
              </label>
              <label className="block">
                <div className="t-label mb-1.5">пароль</div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input font-mono"
                  autoComplete="current-password"
                  required
                />
              </label>
              {error && (
                <p className="font-mono text-xs" style={{ color: 'var(--err)' }} role="alert">
                  err: {error}
                </p>
              )}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? 'Вхід…' : '→ Увійти'}
              </button>
            </form>
          </div>
        </div>

        <p className="mt-4 text-center font-mono text-[11px] muted">
          503work · labor·analytics
        </p>
      </div>
    </div>
  )
}
