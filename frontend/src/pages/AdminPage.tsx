import { useAdminStats, useFailures, usePipelineStatus, useResolveFailure } from '../api/hooks'
import { Card } from '../components/Card'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, Loading } from '../components/States'
import { formatDate, formatNumber } from '../lib/format'

function StatGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{children}</div>
}

function StatItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[var(--card-border)] px-4 py-3">
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

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        title="Адміністративна панель"
        description="Моніторинг стану системи та управління пайплайном обробки даних"
      />
      <StatsSection />
      <PipelineSection />
      <FailuresSection />
    </div>
  )
}
