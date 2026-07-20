import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

// Обгортає лише /admin (єдиний захищений роут - публічна аналітика доступна
// без входу за задумом). Це UX-зручність, не безпека: реальний захист - на
// бекенді (JWT-перевірка в get_current_user), цей компонент лише не показує
// адмінку тому, хто явно не залогинений, замість того щоб дати їй впасти на API-помилках.
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}
