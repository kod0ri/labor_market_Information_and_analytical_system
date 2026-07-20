import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  ComposedChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useExperienceLevels } from '../../api/hooks'
import type { DataKind } from '../../api/types'
import { formatNumber, formatUSD } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'

// Два режими: чистий bar chart кількості (withSalary=false) або ComposedChart
// із другою віссю Y праворуч для середньої ЗП по бакету досвіду - обидва
// перевикористовують один запит useExperienceLevels, різниця лише в рендері.
export function ExperienceChart({
  type = 'vacancy',
  withSalary = true,
  height = 280,
}: {
  type?: DataKind
  withSalary?: boolean
  height?: number
}) {
  const { data, isLoading, isError } = useExperienceLevels(type)
  if (isLoading) return <Loading rows={4} />
  if (isError) return <ErrorState />
  if (!data || data.length === 0) return <EmptyState description="Немає даних про досвід" />

  const rows = [...data].sort((a, b) => a.sort_key - b.sort_key)
  const total = rows.reduce((s, r) => s + r.count, 0)
  if (!total) return <EmptyState description="Немає даних про досвід" />

  if (!withSalary) {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="bucket" />
          <YAxis allowDecimals={false} tickFormatter={(v) => formatNumber(v as number)} />
          <Tooltip formatter={(v) => [formatNumber(v as number), 'Кількість']} />
          {/* Спадна прозорість зліва направо (junior→senior) - легкий
              візуальний градієнт замість суцільного однакового кольору стовпців. */}
          <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={38}>
            {rows.map((_, i) => (
              <Cell
                key={i}
                fill={type === 'vacancy' ? 'var(--chart-1)' : 'var(--chart-2)'}
                opacity={1 - i * 0.06}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="bucket" />
        <YAxis yAxisId="count" allowDecimals={false} tickFormatter={(v) => formatNumber(v as number)} />
        <YAxis
          yAxisId="salary"
          orientation="right"
          tickFormatter={(v) => formatUSD(v as number)}
          width={70}
        />
        <Tooltip
          formatter={(v, k) => {
            if (k === 'count') return [formatNumber(v as number), 'Кількість']
            return [formatUSD(v as number), 'Середня ЗП']
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(k) => (k === 'count' ? 'Кількість' : 'Середня ЗП')}
        />
        <Bar
          yAxisId="count"
          dataKey="count"
          fill={type === 'vacancy' ? 'var(--chart-1)' : 'var(--chart-2)'}
          radius={[6, 6, 0, 0]}
          barSize={32}
        />
        <Line
          yAxisId="salary"
          type="monotone"
          dataKey="avg_salary_usd"
          stroke="var(--chart-5)"
          strokeWidth={2}
          dot={{ r: 4, fill: 'var(--chart-5)' }}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
