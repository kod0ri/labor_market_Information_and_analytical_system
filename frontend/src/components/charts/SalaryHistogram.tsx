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
import { useSalaryDistribution } from '../../api/hooks'
import { formatNumber } from '../../lib/format'
import { EmptyState, ErrorState, Loading } from '../States'

interface Props {
  showResumes?: boolean
  height?: number
}

// Той самий порядок бакетів, що будує бекенд (analytics.py get_salary_distribution) -
// підтримується вручну тут, бо API повертає лише бакети З ДАНИМИ (може
// бракувати проміжного діапазону), а графіку потрібні всі 6 колонок завжди на своєму місці.
const ORDER = ['<$500', '$500–1k', '$1k–2k', '$2k–3k', '$3k–5k', '>$5k']

export function SalaryHistogram({ showResumes = true, height = 320 }: Props) {
  // Два незалежні запити (вакансії й резюме) замість одного - бекенд віддає
  // розподіл окремо на type=vacancy/resume; об'єднуємо результати нижче в один графік.
  const vacQ = useSalaryDistribution('vacancy')
  const resQ = useSalaryDistribution('resume')

  if (vacQ.isLoading || (showResumes && resQ.isLoading))
    return <Loading rows={6} height="h-4" />
  if (vacQ.isError || (showResumes && resQ.isError)) return <ErrorState />

  const vacMap = new Map((vacQ.data ?? []).map((b) => [b.range_label, b.count]))
  const resMap = new Map((resQ.data ?? []).map((b) => [b.range_label, b.count]))

  // ORDER.map (не vacMap.entries()) - гарантує стабільний порядок і присутність
  // усіх 6 бакетів навіть якщо якийсь із них відсутній у відповіді API (0 замість пропуску).
  const rows = ORDER.map((label) => ({
    label,
    vacancies: vacMap.get(label) ?? 0,
    resumes: resMap.get(label) ?? 0,
  }))
  const hasData = rows.some((r) => r.vacancies > 0 || r.resumes > 0)
  if (!hasData) return <EmptyState description="Поки немає даних про зарплати" />

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" />
        <YAxis allowDecimals={false} tickFormatter={(v) => formatNumber(v as number)} />
        <Tooltip formatter={(v) => formatNumber(v as number)} />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(v) => (v === 'vacancies' ? 'Вакансії' : 'Резюме')}
        />
        <Bar dataKey="vacancies" fill="var(--chart-1)" radius={[6, 6, 0, 0]} />
        {showResumes && (
          <Bar dataKey="resumes" fill="var(--chart-2)" radius={[6, 6, 0, 0]} />
        )}
      </BarChart>
    </ResponsiveContainer>
  )
}
