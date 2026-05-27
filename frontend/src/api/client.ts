export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function apiPatch<T>(path: string): Promise<T> {
  const url = new URL(path, API_BASE_URL)
  const res = await fetch(url, {
    method: 'PATCH',
    headers: { Accept: 'application/json', ...authHeaders() },
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new ApiError(body || res.statusText, res.status)
  }
  return res.json() as Promise<T>
}

export async function apiGet<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(path, API_BASE_URL)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue
      url.searchParams.set(k, String(v))
    }
  }
  const res = await fetch(url, { headers: { Accept: 'application/json', ...authHeaders() } })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new ApiError(body || res.statusText, res.status)
  }
  return res.json() as Promise<T>
}
