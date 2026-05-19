import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useExperienceTimeline } from '../../api/hooks'
import type { BucketSize, DataKind } from '../../api/types'
import { formatNumber, formatPercent } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'

interface Props {
  type?: DataKind
  bucket?: BucketSize
  days?: number
  mode?: 'count' | 'share'
  height?: number
}

const LEVELS = [
  { key: 'junior', label: 'Junior (0–1р)', color: 'var(--chart-2)' },
  { key: 'middle', label: 'Middle (2–4р)', color: 'var(--chart-1)' },
  { key: 'senior', label: 'Senior (5+р)', color: 'var(--chart-3)' },
  { key: 'unknown', label: 'Не вказано', color: 'var(--chart-5)' },
] as const

function tickFmt(s: string, bucket: BucketSize) {
  const d = new Date(s)
  if (bucket === 'month') {
    return d.toLocaleDateString('uk-UA', { month: 'short', year: '2-digit' })
  }
  return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' })
}

export function ExperienceTimelineChart({
  type = 'vacancy',
  bucket = 'week',
  days = 90,
  mode = 'count',
  height = 300,
}: Props) {
  const { data, isLoading, isError } = useExperienceTimeline(type, bucket, days)
  if (isLoading) return <Loading rows={6} height="h-3" />
  if (isError) return <ErrorState />
  if (!data || data.length === 0)
    return <EmptyState description="Поки немає даних за обраний період" />

  const fmt = (s: string) => tickFmt(s, bucket)

  const rows = data.map((d) => {
    const total = d.junior + d.middle + d.senior + d.unknown
    if (mode === 'share' && total > 0) {
      return {
        bucket_start: d.bucket_start,
        junior: (d.junior / total) * 100,
        middle: (d.middle / total) * 100,
        senior: (d.senior / total) * 100,
        unknown: (d.unknown / total) * 100,
        _total: total,
      }
    }
    return { ...d, _total: total }
  })

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="bucket_start" tickFormatter={fmt} minTickGap={24} />
        <YAxis
          tickFormatter={(v) =>
            mode === 'share' ? `${Math.round(v as number)}%` : formatNumber(v as number)
          }
          width={50}
        />
        <Tooltip
          labelFormatter={(l) => fmt(l as string)}
          formatter={(v, k, item) => {
            const label =
              LEVELS.find((l) => l.key === k)?.label ?? (k as string)
            if (mode === 'share') {
              const n = v as number
              const total = (item?.payload as { _total?: number } | undefined)?._total ?? 0
              return [`${n.toFixed(1)}% (${formatNumber(Math.round((n * total) / 100))})`, label]
            }
            return [
              `${formatNumber(v as number)} (${formatPercent(
                v as number,
                (item?.payload as { _total?: number } | undefined)?._total ?? 0,
              )})`,
              label,
            ]
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(k) => LEVELS.find((l) => l.key === k)?.label ?? (k as string)}
        />
        {LEVELS.map((l) => (
          <Area
            key={l.key}
            type="monotone"
            dataKey={l.key}
            stackId="1"
            stroke={l.color}
            fill={l.color}
            fillOpacity={0.7}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}
