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
import { useTopSkills } from '../../api/hooks'
import type { DataKind, SkillCategory } from '../../api/types'
import { formatNumber } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'

interface Props {
  type?: DataKind
  limit?: number
  category?: SkillCategory
  height?: number
}

const MAX_LABEL_CHARS = 22

function truncate(s: string): string {
  return s.length > MAX_LABEL_CHARS ? s.slice(0, MAX_LABEL_CHARS - 1) + '…' : s
}

// Локальна копія того самого рішення, що й components/charts/YAxisTick.tsx
// (YAxisTruncatedTick) - тут не перевикористана з тим модулем, хоча логіка
// ідентична; історично написана незалежно, коли додавали цей графік.
interface TickProps {
  x?: number
  y?: number
  payload?: { value?: string }
}

function YAxisTick(props: TickProps) {
  const { x = 0, y = 0, payload } = props
  const raw = payload?.value ?? ''
  const text = truncate(raw)
  return (
    <g transform={`translate(${x},${y})`}>
      <title>{raw}</title>
      <text
        x={-8}
        y={0}
        dy={4}
        textAnchor="end"
        fill="var(--muted-fg)"
        fontSize={12}
      >
        {text}
      </text>
    </g>
  )
}

export function TopSkillsChart({
  type = 'vacancy',
  limit = 12,
  category,
  height = 360,
}: Props) {
  const { data, isLoading, isError } = useTopSkills(type, limit, category)

  if (isLoading) return <Loading rows={6} height="h-4" />
  if (isError) return <ErrorState />
  if (!data || data.length === 0)
    return <EmptyState description="Навичок ще не зібрано" />

  const dynamicHeight = Math.max(height, data.length * 30 + 40)

  return (
    <ResponsiveContainer width="100%" height={dynamicHeight}>
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
          tick={<YAxisTick />}
        />
        <Tooltip
          formatter={(v) => [
            formatNumber(v as number),
            type === 'vacancy' ? 'Вакансій' : 'Резюме',
          ]}
        />
        {/* Колір за категорією навички (Hard/Soft), не за рангом - на
            відміну від інших горизонтальних bar chart'ів тут прозорість
            лише вторинна ознака рангу поверх основного розрізнення кольором. */}
        <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
          {data.map((d, i) => (
            <Cell
              key={d.name}
              fill={d.category === 'Soft' ? 'var(--chart-3)' : 'var(--chart-1)'}
              opacity={1 - i * 0.035}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
