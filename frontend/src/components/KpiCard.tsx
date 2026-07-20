import type { ReactNode } from 'react'

// Компактна картка-показник (велике число + підпис + опційна іконка/підказка) -
// 4 такі картки формують верхній ряд KPI на DashboardPage.
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
    <div className="card card-pad relative overflow-hidden">
      <div className="flex items-start justify-between gap-2">
        <div className="t-label">{label}</div>
        {icon && (
          <div
            className="grid h-8 w-8 shrink-0 place-items-center border"
            style={{
              borderRadius: 2,
              borderColor: accent ? 'var(--brand)' : 'var(--card-border)',
              color: accent ? 'var(--brand)' : 'var(--muted-fg)',
              background: accent ? 'var(--brand-soft)' : 'transparent',
            }}
          >
            {icon}
          </div>
        )}
      </div>
      <div
        className={`num mt-3 text-2xl font-bold tracking-tight sm:text-3xl ${accent ? 'caret' : ''}`}
        style={accent ? { color: 'var(--brand)' } : undefined}
      >
        {value}
      </div>
      {hint && <div className="muted mt-1 font-mono text-[11px]">{hint}</div>}
    </div>
  )
}
