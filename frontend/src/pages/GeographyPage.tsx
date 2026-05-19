import { useState } from 'react'
import { useLocations } from '../api/hooks'
import type { DataKind } from '../api/types'
import { Card } from '../components/Card'
import { LocationsChart } from '../components/charts/LocationsChart'
import { PageHeader } from '../components/PageHeader'
import { SegmentedControl } from '../components/SegmentedControl'
import { EmptyState, ErrorState, Loading } from '../components/States'
import { formatNumber, formatPercent } from '../lib/format'

export default function GeographyPage() {
  const [type, setType] = useState<DataKind>('vacancy')
  const { data, isLoading, isError } = useLocations(type, 20)
  const total = (data ?? []).reduce((s, l) => s + l.count, 0)

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Географія"
        description="Розподіл вакансій та резюме по містах України"
        actions={
          <SegmentedControl<DataKind>
            value={type}
            onChange={setType}
            segments={[
              { value: 'vacancy', label: 'Вакансії' },
              { value: 'resume', label: 'Резюме' },
            ]}
          />
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr,360px]">
        <Card
          title="Топ-20 міст"
          description={type === 'vacancy' ? 'За кількістю вакансій' : 'За кількістю резюме'}
        >
          <LocationsChart type={type} limit={20} height={560} />
        </Card>

        <Card title="Деталізація" description={total ? `Загалом ${formatNumber(total)}` : undefined}>
          {isLoading ? (
            <Loading rows={8} />
          ) : isError ? (
            <ErrorState />
          ) : !data || data.length === 0 ? (
            <EmptyState description="Дані з'являться після ETL" />
          ) : (
            <ol className="space-y-2 text-sm">
              {data.map((l, i) => (
                <li
                  key={`${l.city_name}-${i}`}
                  className="flex items-center justify-between gap-3 border-b border-[var(--card-border)]/60 pb-2 last:border-0"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-brand-500/10 text-[11px] font-bold text-brand-500">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <div className="truncate font-medium">{l.city_name}</div>
                      {l.region && <div className="truncate text-xs muted">{l.region}</div>}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold">{formatNumber(l.count)}</div>
                    <div className="text-xs muted">{formatPercent(l.count, total)}</div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  )
}
