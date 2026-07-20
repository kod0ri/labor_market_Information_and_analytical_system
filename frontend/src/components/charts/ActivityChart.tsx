import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useActivity } from '../../api/hooks'
import type { BucketSize } from '../../api/types'
import { formatNumber, formatUSD } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'

// Один графік, дві "особистості" залежно від `metric`: area-chart нових
// вакансій/резюме (count) або line-chart середньої ЗП (salary) - обидва
// живляться тим самим useActivity(bucket, days) хуком/ендпоінтом, лише
// рендерять різні поля відповіді.
interface Props {
  bucket: BucketSize
  days: number
  metric: 'count' | 'salary'
  height?: number
}

function tickFormatter(s: string, bucket: BucketSize) {
  const d = new Date(s)             // s - ISO-дата bucket_start з відповіді API
  if (bucket === 'month') {
    return d.toLocaleDateString('uk-UA', { month: 'short', year: '2-digit' })   // "січ. 26" - місяць+рік для великого масштабу
  }
  return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' })    // "20.07" - день+місяць для day/week
}

export function ActivityChart({ bucket, days, metric, height = 320 }: Props) {
  const { data, isLoading, isError } = useActivity(bucket, days)   // один запит, обидва metric-режими читають ті самі дані
  if (isLoading) return <Loading rows={6} height="h-3" />
  if (isError) return <ErrorState />
  if (!data || data.length === 0)
    return <EmptyState description="Поки немає даних за обраний період" />

  const tickFmt = (s: string) => tickFormatter(s, bucket)   // прив'язуємо поточний bucket до форматера для XAxis/Tooltip

  if (metric === 'count') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
          {/* Вертикальний градієнт від кольору лінії (55% opacity зверху) до
              прозорого знизу - класична заливка area-графіка "затуханням". */}
          <defs>
            <linearGradient id="actVac" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.55} />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="actRes" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-2)" stopOpacity={0.55} />
              <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="bucket_start" tickFormatter={tickFmt} minTickGap={24} />
          <YAxis allowDecimals={false} tickFormatter={(v) => formatNumber(v as number)} width={50} />
          <Tooltip
            labelFormatter={(l) => tickFmt(l as string)}
            formatter={(v, k) => [
              formatNumber(v as number),
              k === 'new_vacancies' ? 'Нові вакансії' : 'Нові резюме',
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            formatter={(k) => (k === 'new_vacancies' ? 'Нові вакансії' : 'Нові резюме')}
          />
          <Area
            type="monotone"
            dataKey="new_vacancies"
            stroke="var(--chart-1)"
            fill="url(#actVac)"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="new_resumes"
            stroke="var(--chart-2)"
            fill="url(#actRes)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  // salary
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="bucket_start" tickFormatter={tickFmt} minTickGap={24} />
        <YAxis tickFormatter={(v) => formatUSD(v as number)} width={70} />
        <Tooltip
          labelFormatter={(l) => tickFmt(l as string)}
          formatter={(v, k) => [
            v === null ? '—' : formatUSD(v as number),
            k === 'avg_vacancy_salary_usd' ? 'ЗП вакансій' : 'ЗП резюме',
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(k) =>
            k === 'avg_vacancy_salary_usd' ? 'ЗП вакансій' : 'ЗП резюме'
          }
        />
        <Line
          type="monotone"
          dataKey="avg_vacancy_salary_usd"
          stroke="var(--chart-1)"
          strokeWidth={2}
          dot={{ r: 3, fill: 'var(--chart-1)' }}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="avg_resume_salary_usd"
          stroke="var(--chart-2)"
          strokeWidth={2}
          dot={{ r: 3, fill: 'var(--chart-2)' }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
