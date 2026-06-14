import {
  IconCoins,
  IconDashboard,
  IconMapPin,
  IconSearch,
  IconSettings,
  IconSparkles,
} from './Icon'

import type { ReactElement, SVGProps } from 'react'

export interface NavItem {
  to: string
  label: string
  icon: (p: SVGProps<SVGSVGElement> & { size?: number }) => ReactElement
  end?: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Дашборд', icon: IconDashboard, end: true },
  { to: '/skills', label: 'Навички', icon: IconSparkles },
  { to: '/salary', label: 'Зарплати', icon: IconCoins },
  { to: '/geography', label: 'Географія', icon: IconMapPin },
  { to: '/search', label: 'Пошук', icon: IconSearch },
  { to: '/admin', label: 'Адмін', icon: IconSettings },
]
