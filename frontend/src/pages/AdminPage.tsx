import {
  useAdminStats,
  useFailures,
  usePipelineStatus,
  useResolveFailure,
  useSystemMetrics,
} from '../api/hooks'
import { Card } from '../components/Card'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, Loading } from '../components/States'
import {
  formatBytes,
  formatDate,
  formatDateTime,
  formatDuration,
  formatNumber,
} from '../lib/format'

function StatGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{children}</div>
}

function StatItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-sm border border-[var(--card-border)] px-4 py-3">
      <div className="text-xs muted">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  )
}

function StatsSection() {
  const { data, isLoading, isError } = useAdminStats()
  if (isLoading) return <Card title="Статистика системи"><Loading rows={3} /></Card>
  if (isError || !data) return <Card title="Статистика системи"><ErrorState /></Card>

  return (
    <Card title="Статистика системи" description="Поточний стан бази даних">
      <div className="space-y-4">
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wider muted">Оброблено</div>
          <StatGrid>
            <StatItem label="Вакансій" value={formatNumber(data.processed.vacancies)} />
            <StatItem label="Резюме" value={formatNumber(data.processed.resumes)} />
          </StatGrid>
        </div>
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wider muted">Словники</div>
          <StatGrid>
            <StatItem label="Навичок" value={formatNumber(data.dictionaries.skills)} />
            <StatItem label="Компаній" value={formatNumber(data.dictionaries.companies)} />
            <StatItem label="Локацій" value={formatNumber(data.dictionaries.locations)} />
          </StatGrid>
        </div>
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wider muted">Черга пайплайну</div>
          <StatGrid>
            <StatItem
              label="Вакансій в черзі"
              value={
                <span className={data.pipeline_queue.vacancies_pending > 0 ? 'text-amber-500' : ''}>
                  {formatNumber(data.pipeline_queue.vacancies_pending)}
                </span>
              }
            />
            <StatItem
              label="Резюме в черзі"
              value={
                <span className={data.pipeline_queue.resumes_pending > 0 ? 'text-amber-500' : ''}>
                  {formatNumber(data.pipeline_queue.resumes_pending)}
                </span>
              }
            />
          </StatGrid>
        </div>
      </div>
    </Card>
  )
}

function PipelineSection() {
  const { data, isLoading, isError } = usePipelineStatus()
  if (isLoading) return <Card title="Стан пайплайну"><Loading rows={4} /></Card>
  if (isError || !data) return <Card title="Стан пайплайну"><ErrorState /></Card>

  const byType = Object.entries(data.failures.by_type)

  return (
    <Card title="Стан пайплайну" description="Обробка даних через LLM">
      <div className="space-y-4">
        <StatGrid>
          <StatItem label="Вакансій в черзі" value={formatNumber(data.queue.vacancies_pending)} />
          <StatItem label="Резюме в черзі" value={formatNumber(data.queue.resumes_pending)} />
          <StatItem
            label="Активних помилок"
            value={
              <span className={data.failures.total_unresolved > 0 ? 'text-red-500' : 'text-green-500'}>
                {formatNumber(data.failures.total_unresolved)}
              </span>
            }
          />
        </StatGrid>

        {byType.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-medium uppercase tracking-wider muted">Помилки за типами</div>
            <div className="flex flex-wrap gap-2">
              {byType.map(([type, count]) => (
                <span key={type} className="chip text-xs">
                  {type}: {count}
                </span>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wider muted">Останнє записано</div>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="muted">Вакансія</span>
              <span>{data.last_processed.vacancy_at ? formatDate(data.last_processed.vacancy_at) : '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="muted">Резюме</span>
              <span>{data.last_processed.resume_at ? formatDate(data.last_processed.resume_at) : '—'}</span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}

function FailuresSection() {
  const { data, isLoading, isError } = useFailures(50)
  const resolve = useResolveFailure()

  if (isLoading) return <Card title="Помилки пайплайну"><Loading rows={6} /></Card>
  if (isError) return <Card title="Помилки пайплайну"><ErrorState /></Card>

  const items = data ?? []

  return (
    <Card
      title="Помилки пайплайну"
      description={items.length === 0 ? 'Нема нерозвязаних помилок' : `${items.length} нерозвязаних`}
    >
      {items.length === 0 ? (
        <div className="py-8 text-center text-sm muted">Всі записи оброблені успішно</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="border-b border-[var(--card-border)] text-left text-xs uppercase tracking-wider muted">
              <tr>
                <th className="px-3 py-2 font-medium">ID</th>
                <th className="px-3 py-2 font-medium">Тип</th>
                <th className="px-3 py-2 font-medium">Тип помилки</th>
                <th className="px-3 py-2 font-medium">Деталі</th>
                <th className="px-3 py-2 font-medium">Спроби</th>
                <th className="px-3 py-2 font-medium">Дата</th>
                <th className="px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((f) => (
                <tr
                  key={f.id}
                  className="border-b border-[var(--card-border)]/70 align-middle hover:bg-[var(--card-border)]/20"
                >
                  <td className="px-3 py-2 font-mono text-xs muted">#{f.staging_id}</td>
                  <td className="px-3 py-2">
                    <span className="chip">{f.record_type}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`chip ${f.error_type === 'validation' ? 'text-amber-600' : 'text-red-500'}`}>
                      {f.error_type}
                    </span>
                  </td>
                  <td className="max-w-[240px] truncate px-3 py-2 text-xs muted" title={f.error_detail}>
                    {f.error_detail}
                  </td>
                  <td className="px-3 py-2 text-center">{f.attempt_count}</td>
                  <td className="px-3 py-2 whitespace-nowrap muted">
                    {f.failed_at ? formatDate(f.failed_at) : '—'}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="btn text-xs"
                      disabled={resolve.isPending}
                      onClick={() => resolve.mutate(f.id)}
                    >
                      Вирішити
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function barColor(percent: number): string {
  if (percent >= 85) return 'var(--err)'
  if (percent >= 60) return 'var(--warn)'
  return 'var(--ok)'
}

function UsageBar({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent))
  return (
    <div className="mt-2 h-1.5 overflow-hidden rounded-sm bg-[var(--card-border)]">
      <div
        className="h-full transition-[width] duration-500"
        style={{ width: `${clamped}%`, background: barColor(clamped) }}
      />
    </div>
  )
}

function MetricTile({
  label,
  value,
  sub,
  percent,
}: {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  percent?: number
}) {
  return (
    <div className="rounded-sm border border-[var(--card-border)] px-4 py-3">
      <div className="t-label">{label}</div>
      <div className="num mt-1 text-xl font-semibold">{value}</div>
      {sub && <div className="mt-0.5 font-mono text-[11px] muted">{sub}</div>}
      {percent !== undefined && <UsageBar percent={percent} />}
    </div>
  )
}

function SystemSection() {
  const { data, isLoading, isError } = useSystemMetrics()
  if (isLoading) return <Card title="Сервер та користувачі"><Loading rows={4} /></Card>
  if (isError || !data) return <Card title="Сервер та користувачі"><ErrorState /></Card>

  const { visitors, users, server } = data
  const { disk, memory, load_average: load } = server

  return (
    <div className="space-y-6">
      <Card
        title="Відвідувачі"
        description="Усі відвідувачі сайту, включно з незареєстрованими"
      >
        <StatGrid>
          <MetricTile
            label="Зараз на сайті"
            value={
              <span className="inline-flex items-center gap-2" style={{ color: 'var(--ok)' }}>
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--ok)' }} />
                {formatNumber(visitors.online)}
              </span>
            }
            sub="за останні 5 хв"
          />
          <MetricTile label="За 24 години" value={formatNumber(visitors.last_24h)} sub="унікальних" />
          <MetricTile label="За тиждень" value={formatNumber(visitors.last_7d)} sub="унікальних" />
          <MetricTile
            label="Середній онлайн"
            value={visitors.avg_online_24h.toFixed(1)}
            sub={`за 24 год · пік ${formatNumber(visitors.peak_online_24h)}`}
          />
        </StatGrid>
      </Card>

      <Card title="Акаунти" description={`${users.online} онлайн зараз`}>
        <StatGrid>
          <StatItem label="Усього" value={formatNumber(users.total)} />
          <StatItem
            label="Онлайн"
            value={
              <span className="inline-flex items-center gap-2" style={{ color: 'var(--ok)' }}>
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--ok)' }} />
                {formatNumber(users.online)}
              </span>
            }
          />
          <StatItem label="Нових за 7 днів" value={formatNumber(users.new_7d)} />
        </StatGrid>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead className="border-b border-[var(--card-border)] text-left text-xs uppercase tracking-wider muted">
              <tr>
                <th className="px-3 py-2 font-medium">Акаунт</th>
                <th className="px-3 py-2 font-medium">Статус</th>
                <th className="px-3 py-2 font-medium">Остання активність</th>
                <th className="px-3 py-2 font-medium">Створено</th>
              </tr>
            </thead>
            <tbody>
              {users.list.map((u) => (
                <tr
                  key={u.id}
                  className="border-b border-[var(--card-border)]/70 align-middle hover:bg-[var(--card-border)]/20"
                >
                  <td className="px-3 py-2 font-medium">{u.username}</td>
                  <td className="px-3 py-2">
                    <span
                      className="inline-flex items-center gap-1.5 font-mono text-xs"
                      style={{ color: u.is_online ? 'var(--ok)' : 'var(--muted, inherit)' }}
                    >
                      <span
                        className="inline-block h-2 w-2 rounded-full"
                        style={{ background: u.is_online ? 'var(--ok)' : 'var(--card-border)' }}
                      />
                      {u.is_online ? 'online' : 'offline'}
                    </span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap muted">{formatDateTime(u.last_seen_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap muted">{formatDateTime(u.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Сервер" description={`uptime ${formatDuration(server.uptime_seconds)}`}>
        <StatGrid>
          <MetricTile
            label="Диск"
            value={`${disk.used_percent}%`}
            sub={`${formatBytes(disk.used_bytes)} / ${formatBytes(disk.total_bytes)}`}
            percent={disk.used_percent}
          />
          {memory && (
            <MetricTile
              label="Память"
              value={`${memory.used_percent}%`}
              sub={`${formatBytes(memory.used_bytes)} / ${formatBytes(memory.total_bytes)}`}
              percent={memory.used_percent}
            />
          )}
          <MetricTile
            label="Розмір БД"
            value={formatBytes(server.database_size_bytes)}
            sub="postgres"
          />
          <MetricTile
            label="Навантаження"
            value={load ? load['1m'].toFixed(2) : '—'}
            sub={
              load
                ? `5хв ${load['5m'].toFixed(2)} · 15хв ${load['15m'].toFixed(2)}${
                    server.cpu_count ? ` · ${server.cpu_count} CPU` : ''
                  }`
                : 'недоступно'
            }
            percent={load && server.cpu_count ? (load['1m'] / server.cpu_count) * 100 : undefined}
          />
        </StatGrid>
      </Card>
    </div>
  )
}

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        title="Адміністративна панель"
        description="Моніторинг стану системи та управління пайплайном обробки даних"
      />
      <SystemSection />
      <StatsSection />
      <PipelineSection />
      <FailuresSection />
    </div>
  )
}
