import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useLocations } from '../../api/hooks'
import type { DataKind } from '../../api/types'
import { formatNumber } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'
import { YAxisTruncatedTick } from './YAxisTick'

interface Props {
  type?: DataKind
  limit?: number
  height?: number
}

export function LocationsChart({ type = 'vacancy', limit = 10, height = 340 }: Props) {
  const { data, isLoading, isError } = useLocations(type, limit)

  if (isLoading) return <Loading rows={6} height="h-4" />
  if (isError) return <ErrorState />
  if (!data || data.length === 0) return <EmptyState description="Поки немає даних географії" />

  return (
    <ResponsiveContainer width="100%" height={Math.max(height, data.length * 28 + 40)}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 24, left: 8, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tickFormatter={(v) => formatNumber(v as number)} />
        <YAxis
          type="category"
          dataKey="city_name"
          width={140}
          interval={0}
          tick={<YAxisTruncatedTick maxChars={18} />}
        />
        <Tooltip
          formatter={(v) => [
            formatNumber(v as number),
            type === 'vacancy' ? 'Вакансій' : 'Резюме',
          ]}
          labelFormatter={(name, payload) => {
            const row = payload?.[0]?.payload as { city_name?: string; region?: string | null } | undefined
            return row?.region ? `${row.city_name}, ${row.region}` : (name as string)
          }}
        />
        <Bar
          dataKey="count"
          radius={[0, 6, 6, 0]}
          barSize={18}
          fill={type === 'vacancy' ? 'var(--chart-1)' : 'var(--chart-2)'}
        >
          {data.map((d, i) => (
            <Cell key={d.city_name} opacity={1 - i * 0.05} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
