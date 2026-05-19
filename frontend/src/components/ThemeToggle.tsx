import { useTheme } from '../lib/theme'
import { IconMoon, IconSun } from './Icon'

export function ThemeToggle() {
  const [theme, , toggle] = useTheme()
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Світла тема' : 'Темна тема'}
      className="btn h-9 w-9 p-0"
      title={theme === 'dark' ? 'Світла тема' : 'Темна тема'}
    >
      {theme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
    </button>
  )
}
