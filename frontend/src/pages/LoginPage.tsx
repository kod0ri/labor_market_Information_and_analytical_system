import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_BASE_URL } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Logo } from '../components/Logo'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch(new URL('/api/auth/login', API_BASE_URL).toString(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as { detail?: string }
        setError(data.detail ?? 'Помилка входу')
        return
      }
      const data = await res.json() as { access_token: string }
      login(data.access_token)
      navigate('/admin', { replace: true })
    } catch {
      setError('Не вдалося підключитись до сервера')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--app-bg)]">
      <div className="w-full max-w-sm px-4">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-8 shadow-sm">
          <h1 className="mb-6 text-xl font-semibold">Вхід в адмінку</h1>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium">Логін</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-lg border border-[var(--card-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-brand-500"
                required
                autoFocus
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">Пароль</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-[var(--card-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-brand-500"
                required
              />
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="btn w-full justify-center bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-60"
            >
              {loading ? 'Вхід…' : 'Увійти'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
