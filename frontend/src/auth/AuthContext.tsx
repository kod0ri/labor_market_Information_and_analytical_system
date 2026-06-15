import { createContext, useContext, useMemo, useState } from 'react'

interface CurrentUser {
  username: string
}

interface AuthContextValue {
  token: string | null
  user: CurrentUser | null
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

/** Читає payload JWT без перевірки підпису — лише для відображення в UI. */
function decodeUser(token: string | null): CurrentUser | null {
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1])) as {
      sub?: string
      exp?: number
    }
    if (payload.exp && payload.exp * 1000 < Date.now()) return null // протермінований
    if (!payload.sub) return null
    return { username: payload.sub }
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('auth_token'))

  const login = (t: string) => {
    localStorage.setItem('auth_token', t)
    setToken(t)
  }

  const logout = () => {
    localStorage.removeItem('auth_token')
    setToken(null)
  }

  const value = useMemo<AuthContextValue>(() => {
    const user = decodeUser(token)
    return {
      token: user ? token : null, // протермінований токен трактуємо як вихід
      user,
      login,
      logout,
    }
  }, [token])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
