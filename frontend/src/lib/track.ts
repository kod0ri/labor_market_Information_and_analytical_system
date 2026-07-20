import { API_BASE_URL } from '../api/client'

// Анонімний ідентифікатор браузера (НЕ персональні дані). Дозволяє рахувати
// унікальних відвідувачів без cookie та без збереження IP на сервері.
const VISITOR_KEY = '503work.visitor_id'

function getVisitorId(): string {
  let id = localStorage.getItem(VISITOR_KEY)   // той самий id при кожному наступному візиті цього браузера
  if (!id) {                                     // перший візит - генеруємо й одразу зберігаємо назавжди
    id =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto   // сучасні браузери - справжній UUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`   // фолбек для старих середовищ без crypto.randomUUID
    localStorage.setItem(VISITOR_KEY, id)
  }
  return id
}

/** Fire-and-forget beacon про візит. Помилки ігноруємо — це не критичний шлях. */
export function trackVisit(path: string): void {
  try {
    const url = new URL('/api/track', API_BASE_URL || window.location.origin).toString()
    const body = JSON.stringify({ visitor_id: getVisitorId(), path })
    void fetch(url, {                     // void - не чекаємо на результат, виклик не блокує рендер/навігацію
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,                      // запит переживе закриття вкладки/перехід на іншу сторінку
    }).catch(() => {})                       // мережева помилка тут не критична - просто ігноруємо
  } catch {
    /* ignore */
  }
}
