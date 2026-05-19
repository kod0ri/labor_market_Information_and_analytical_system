import type { ReactNode } from 'react'

export function KpiCard({
  label,
  value,
  hint,
  icon,
  accent = false,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  accent?: boolean
}) {
  return (
    <div
      className={`card card-pad relative overflow-hidden ${
        accent ? 'ring-1 ring-brand-500/30' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="text-xs font-medium uppercase tracking-wider muted">{label}</div>
        {icon && (
          <div
            className={`grid h-9 w-9 place-items-center rounded-lg ${
              accent
                ? 'bg-brand-500/15 text-brand-500'
                : 'bg-[var(--card-border)]/60 muted'
            }`}
          >
            {icon}
          </div>
        )}
      </div>
      <div className="mt-3 text-3xl font-extrabold tracking-tight">{value}</div>
      {hint && <div className="muted mt-1 text-xs">{hint}</div>}
      {accent && (
        <div className="pointer-events-none absolute -bottom-12 -right-12 h-32 w-32 rounded-full bg-brand-500/15 blur-2xl" />
      )}
    </div>
  )
}
