import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useEnglishLevels } from '../../api/hooks'
import type { DataKind } from '../../api/types'
import { formatNumber, formatPercent } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'

const ORDER = [
  'Beginner',
  'Elementary',
  'Pre-Intermediate',
  'Intermediate',
  'Upper-Intermediate',
  'Advanced',
  'Proficient',
  'Fluent',
]

const COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  '#ec4899',
  '#a855f7',
  '#3b82f6',
]

function rank(level: string | null): number {
  if (!level) return 999
  const i = ORDER.indexOf(level)
  return i < 0 ? 998 : i
}

export function EnglishLevelDonut({
  type = 'vacancy',
  height = 240,
}: {
  type?: DataKind
  height?: number
}) {
  const { data, isLoading, isError } = useEnglishLevels(type)
  if (isLoading) return <Loading rows={3} />
  if (isError) return <ErrorState />
  if (!data || data.length === 0) return <EmptyState description="Немає даних про англійську" />

  const named = data.filter((r) => r.level)
  if (named.length === 0)
    return <EmptyState description="Рівень англійської не заповнений" />

  const rows = [...named]
    .map((r) => ({ name: r.level ?? '—', value: r.count }))
    .sort((a, b) => rank(a.name) - rank(b.name))

  const total = rows.reduce((s, r) => s + r.value, 0)

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={rows}
          dataKey="value"
          nameKey="name"
          innerRadius="55%"
          outerRadius="85%"
          paddingAngle={1}
          stroke="var(--card-bg)"
        >
          {rows.map((r, i) => (
            <Cell key={r.name} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(v) => [
            `${formatNumber(v as number)} (${formatPercent(v as number, total)})`,
            'Кількість',
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(v) => v as string}
          iconType="circle"
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
