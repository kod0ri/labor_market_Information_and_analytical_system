import { useHealth } from '../api/hooks'

export function HealthDot() {
  const { data, isError, isLoading } = useHealth()
  const ok = !isError && data?.status === 'ok'
  const color = isLoading ? 'bg-amber-400' : ok ? 'bg-emerald-500' : 'bg-red-500'
  const label = isLoading ? 'Перевірка…' : ok ? 'API онлайн' : 'API недоступний'
  return (
    <div className="flex items-center gap-2 text-xs muted" title={label}>
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`}>
        {ok && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        )}
      </span>
      <span className="hidden sm:inline">{label}</span>
    </div>
  )
}
