import type { ReactNode } from 'react'
import { IconAlert } from './Icon'

export function Loading({ rows = 4, height = 'h-4' }: { rows?: number; height?: string }) {
  return (
    <div className="space-y-3" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`${height} animate-pulse bg-[var(--card-border)] opacity-60`}
          style={{ borderRadius: 2, animationDelay: `${i * 90}ms` }}
        />
      ))}
    </div>
  )
}

export function ErrorState({ message }: { message?: string }) {
  return (
    <div
      className="flex items-start gap-3 border p-4 text-sm"
      style={{
        borderRadius: 2,
        borderColor: 'var(--err)',
        background: 'color-mix(in srgb, var(--err) 7%, transparent)',
        color: 'var(--err)',
      }}
      role="alert"
    >
      <IconAlert size={18} />
      <div className="min-w-0">
        <div className="font-mono text-xs font-semibold uppercase tracking-wider">
          err: дані недоступні
        </div>
        <div className="muted mt-1 text-xs">{message ?? 'Перевірте API за адресою /health'}</div>
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
    <div
      className="grid place-items-center border border-dashed border-[var(--card-border)] px-4 py-10 text-center"
      style={{ borderRadius: 2 }}
    >
      {icon}
      <div className="mt-2 font-mono text-sm font-semibold uppercase tracking-wider muted">
        ∅ {title}
      </div>
      <div className="muted mt-1 text-xs">{description}</div>
    </div>
  )
}
