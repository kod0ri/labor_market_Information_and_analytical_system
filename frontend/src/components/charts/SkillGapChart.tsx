import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useSkillGap } from '../../api/hooks'
import { formatNumber } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'
import { YAxisTruncatedTick } from './YAxisTick'

interface Props {
  limit?: number
  height?: number
}

export function SkillGapChart({ limit = 15, height = 460 }: Props) {
  const { data, isLoading, isError } = useSkillGap(limit)

  if (isLoading) return <Loading rows={8} height="h-4" />
  if (isError) return <ErrorState />
  if (!data || data.length === 0) return <EmptyState description="Замало даних для gap-аналізу" />

  // Сортуємо за модулем розриву (не за самим gap) - найбільший дефіцит
  // (gap>>0) і найбільше перенасичення (gap<<0) однаково цікаві на графіку,
  // а сортування лише за gap сховало б перенасичені навички в самий низ.
  const rows = [...data].sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap))

  return (
    <ResponsiveContainer width="100%" height={Math.max(height, rows.length * 38 + 60)}>
      <BarChart
        data={rows}
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
        <Tooltip
          formatter={(value, key) => {
            const label =
              key === 'vacancy_count'
                ? 'Попит (вакансії)'
                : key === 'resume_count'
                ? 'Пропозиція (резюме)'
                : 'Gap'
            return [formatNumber(value as number), label]
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(k) =>
            k === 'vacancy_count'
              ? 'Попит (вакансії)'
              : k === 'resume_count'
              ? 'Пропозиція (резюме)'
              : k
          }
        />
        <Bar dataKey="vacancy_count" fill="var(--chart-1)" radius={[0, 4, 4, 0]} barSize={10}>
          {rows.map((d) => (
            <Cell key={`v-${d.name}`} />
          ))}
        </Bar>
        <Bar dataKey="resume_count" fill="var(--chart-2)" radius={[0, 4, 4, 0]} barSize={10} />
      </BarChart>
    </ResponsiveContainer>
  )
}
