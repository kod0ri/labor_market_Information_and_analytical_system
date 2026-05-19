import type { ReactNode } from 'react'
import { IconAlert } from './Icon'

export function Loading({ rows = 4, height = 'h-4' }: { rows?: number; height?: string }) {
  return (
    <div className="space-y-3" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`${height} animate-pulse rounded bg-[var(--card-border)] opacity-60`}
        />
      ))}
    </div>
  )
}

export function ErrorState({ message }: { message?: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500">
      <IconAlert size={18} />
      <div>
        <div className="font-semibold">Не вдалося завантажити дані</div>
        <div className="muted text-xs">{message ?? 'Перевірте API за адресою /health'}</div>
      </div>
    </div>
  )
}

export function EmptyState({
  title = 'Немає даних',
  description = 'Запустіть ETL-пайплайн або перевірте фільтри',
  icon,
}: {
  title?: string
  description?: string
  icon?: ReactNode
}) {
  return (
    <div className="grid place-items-center rounded-lg border border-dashed border-[var(--card-border)] py-10 text-center">
      {icon}
      <div className="mt-2 font-semibold">{title}</div>
      <div className="muted text-sm">{description}</div>
    </div>
  )
}
