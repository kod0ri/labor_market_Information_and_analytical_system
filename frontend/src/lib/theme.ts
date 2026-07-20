import { useEffect, useState } from 'react'

// Керування темною/світлою темою через клас `dark` на <html> (Tailwind
// dark-mode стратегія "class") + localStorage, щоб вибір пережив перезавантаження.
// Інлайн-скрипт у index.html застосовує тему ДО React-рендеру (уникає "спалаху"
// неправильної теми при першому кадрі) - ця ж логіка getInitial() тут її
// синхронізує зі станом React після гідратації.

export type Theme = 'light' | 'dark'

const STORAGE_KEY = '503work.theme'

function getInitial(): Theme {
  if (typeof window === 'undefined') return 'dark'
  const saved = window.localStorage.getItem(STORAGE_KEY) as Theme | null
  if (saved === 'light' || saved === 'dark') return saved
  // Немає збереженого вибору - орієнтуємось на системну тему ОС/браузера.
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function apply(theme: Theme) {
  const root = document.documentElement
  if (theme === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
}

export function useTheme(): [Theme, (t: Theme) => void, () => void] {
  const [theme, setThemeState] = useState<Theme>(getInitial)

  useEffect(() => {
    apply(theme)
    window.localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  function setTheme(next: Theme) {
    setThemeState(next)
  }
  function toggle() {
    setThemeState((t) => (t === 'dark' ? 'light' : 'dark'))
  }
  return [theme, setTheme, toggle]
}

export const CHART_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
]
