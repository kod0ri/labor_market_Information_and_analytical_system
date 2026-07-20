import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useSources } from '../../api/hooks'
import { formatNumber } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'
import { YAxisTruncatedTick } from './YAxisTick'

export function SourcesBreakdown({ height = 320 }: { height?: number }) {
  const { data, isLoading, isError } = useSources()
  if (isLoading) return <Loading rows={6} />
  if (isError) return <ErrorState />
  if (!data || data.length === 0) return <EmptyState description="Немає даних по джерелах" />

  return (
    // висота росте з кількістю джерел (34px на рядок + 56px запас під заголовки осей),
    // а не фіксована - на випадок, якщо список джерел колись стане довшим за 3
    <ResponsiveContainer width="100%" height={Math.max(height, data.length * 34 + 56)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 5, right: 24, left: 8, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tickFormatter={(v) => formatNumber(v as number)} />
        <YAxis
          type="category"
          dataKey="source"
          width={150}
          interval={0}
          tick={<YAxisTruncatedTick maxChars={20} />}
        />
        <Tooltip
          formatter={(v, name) => [
            formatNumber(v as number),
            name === 'vacancies' ? 'Вакансій' : 'Резюме',
          ]}
        />
        <Legend
          formatter={(value) => (value === 'vacancies' ? 'Вакансії' : 'Резюме')}
        />
        {/* stackId="a" на обох Bar - вакансії й резюме одного джерела в ОДНОМУ
            стовпці (не поряд), закруглення лише на зовнішньому (правому) краю. */}
        <Bar dataKey="vacancies" stackId="a" fill="var(--chart-1)" radius={[0, 0, 0, 0]} barSize={16} />
        <Bar dataKey="resumes" stackId="a" fill="var(--chart-2)" radius={[0, 6, 6, 0]} barSize={16} />
      </BarChart>
    </ResponsiveContainer>
  )
}
