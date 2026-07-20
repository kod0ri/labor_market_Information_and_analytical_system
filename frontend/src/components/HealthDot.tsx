import { useHealth } from '../api/hooks'

// Індикатор у топбарі, що показує живий статус бекенду (GET /health) -
// пульсуюча крапка кольором сигналізує стан без потреби відкривати консоль.
export function HealthDot() {
  const { data, isError, isLoading } = useHealth()
  const ok = !isError && data?.status === 'ok'
  const color = isLoading ? 'var(--warn)' : ok ? 'var(--ok)' : 'var(--err)'
  const text = isLoading ? 'api:···' : ok ? 'api:ok' : 'api:down'
  const label = isLoading ? 'Перевірка…' : ok ? 'API онлайн' : 'API недоступний'
  return (
    <div
      className="flex items-center gap-2 border border-[var(--card-border)] px-2.5 py-1.5 font-mono text-[11px]"
      style={{ borderRadius: 2, color }}
      title={label}
    >
      <span className="relative inline-flex h-1.5 w-1.5" style={{ background: color }}>
        {ok && (
          <span
            className="absolute inline-flex h-full w-full animate-ping opacity-60"
            style={{ background: color }}
          />
        )}
      </span>
      <span className="hidden sm:inline">{text}</span>
    </div>
  )
}
