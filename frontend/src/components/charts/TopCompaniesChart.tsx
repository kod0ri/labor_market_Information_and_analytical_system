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
import { useTopCompanies } from '../../api/hooks'
import { formatNumber } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'
import { YAxisTruncatedTick } from './YAxisTick'

export function TopCompaniesChart({
  limit = 10,
  height = 320,
}: {
  limit?: number
  height?: number
}) {
  const { data, isLoading, isError } = useTopCompanies(limit)
  if (isLoading) return <Loading rows={6} />
  if (isError) return <ErrorState />
  if (!data || data.length === 0) return <EmptyState description="Немає компаній з вакансіями" />

  return (
    <ResponsiveContainer width="100%" height={Math.max(height, data.length * 30 + 40)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 5, right: 24, left: 8, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tickFormatter={(v) => formatNumber(v as number)} />
        <YAxis
          type="category"
          dataKey="name"
          width={170}
          interval={0}
          tick={<YAxisTruncatedTick maxChars={22} />}
        />
        <Tooltip formatter={(v) => [formatNumber(v as number), 'Вакансій']} />
        {/* Дані вже відсортовані бекендом (ORDER BY count DESC) - опадна
            прозорість зверху вниз лише підсилює вже наявний порядок за рангом. */}
        <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
          {data.map((d, i) => (
            <Cell key={d.name} fill="var(--chart-1)" opacity={1 - i * 0.05} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
