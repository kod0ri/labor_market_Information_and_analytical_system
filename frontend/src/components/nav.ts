import {
  IconCoins,
  IconDashboard,
  IconMapPin,
  IconSearch,
  IconSparkles,
} from './Icon'

import type { ReactElement, SVGProps } from 'react'
import type { TKey } from '../lib/i18n'

export interface NavItem {
  to: string
  labelKey: TKey        // ключ i18n-словника, не готовий рядок - Sidebar/Topbar перекладають самі
  icon: (p: SVGProps<SVGSVGElement> & { size?: number }) => ReactElement
  end?: boolean          // NavLink `end`: точний збіг шляху (лише для "/", інакше він завжди "активний")
}

// Єдине джерело пунктів меню - Sidebar (десктоп) і мобільна шухляда в Topbar
// рендерять той самий масив, тож додавання сторінки не вимагає правок у двох місцях.
export const NAV_ITEMS: NavItem[] = [
  { to: '/', labelKey: 'nav.dashboard', icon: IconDashboard, end: true },
  { to: '/skills', labelKey: 'nav.skills', icon: IconSparkles },
  { to: '/salary', labelKey: 'nav.salary', icon: IconCoins },
  { to: '/geography', labelKey: 'nav.geography', icon: IconMapPin },
  { to: '/search', labelKey: 'nav.search', icon: IconSearch },
]
