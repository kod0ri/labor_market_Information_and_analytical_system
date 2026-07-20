// Тонка обгортка над fetch() для REST API 503Work - без axios чи іншого
// HTTP-клієнта, бо потреб (auth-заголовок, JSON, базові помилки) вистачає
// на нативний fetch. useQuery/useMutation-хуки (hooks.ts) викликають ці
// функції як queryFn - саме тому apiGet/apiPost/apiPatch кидають ApiError
// замість повернення {ok, error} - react-query сам ловить кинуті помилки.

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

function resolveUrl(path: string): URL {
  // Порожній API_BASE_URL (прод, той самий origin через nginx-проксі /api) →
  // резолвимо відносно поточної сторінки; у dev VITE_API_BASE_URL вказує на
  // окремий бекенд-порт.
  return new URL(path, API_BASE_URL || window.location.origin)
}

function authHeaders(): Record<string, string> {
  // Токен додається до КОЖНОГО запиту (навіть публічних аналітичних) - для
  // публічних ендпоінтів бекенд його просто ігнорує, а для адмінських він
  // уже готовий у заголовку без окремої гілки коду тут.
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

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const url = resolveUrl(path)
  const res = await fetch(url, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,   // без тіла для запитів без body (напр. деякі POST)
  })
  if (!res.ok) {
    let message = res.statusText                                            // фолбек, якщо тіло не JSON
    const data = await res.json().catch(() => null) as { detail?: string } | null   // FastAPI кладе текст помилки в detail
    if (data?.detail) message = data.detail
    throw new ApiError(message, res.status)
  }
  return res.json() as Promise<T>
}

export async function apiPatch<T>(path: string): Promise<T> {   // без параметра body - усі PATCH-виклики API безтільні (лише шлях з id)
  const url = resolveUrl(path)
  const res = await fetch(url, {
    method: 'PATCH',
    headers: { Accept: 'application/json', ...authHeaders() },
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')    // читаємо як звичайний текст, а не JSON (простіший шлях помилок)
    throw new ApiError(body || res.statusText, res.status)
  }
  return res.json() as Promise<T>
}

export async function apiGet<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = resolveUrl(path)
  if (params) {
    // Пропускаємо undefined/null/'' - неактивні фільтри (напр. "не задано
    // мінімальну ЗП") не потрапляють у query-рядок замість перетворення
    // на буквальні "undefined"/"null" в URL.
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
