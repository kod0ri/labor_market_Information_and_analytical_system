import { useOverview, useSalaryDistribution } from '../api/hooks'
import type { DataKind } from '../api/types'
import { Card } from '../components/Card'
import { ExperienceChart } from '../components/charts/ExperienceChart'
import { SalaryHistogram } from '../components/charts/SalaryHistogram'
import { IconCoins } from '../components/Icon'
import { KpiCard } from '../components/KpiCard'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, Loading } from '../components/States'
import { formatNumber, formatPercent, formatUSD } from '../lib/format'
import { useI18n } from '../lib/i18n'

// Зарплатна аналітика: KPI зверху (з /api/analytics/overview), гістограма
// розподілу і деталізовані таблиці знизу (по /api/analytics/salary-distribution,
// окремо для вакансій і резюме - DetailTable перевикористовується для обох).
export default function SalaryPage() {
  const { t } = useI18n()
  const overview = useOverview()

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title={t('salary.title')} description={t('salary.desc')} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label={t('kpi.avgVacSalary')}
          value={overview.isLoading ? '…' : formatUSD(overview.data?.avg_vacancy_salary_usd)}
          icon={<IconCoins size={18} />}
          accent
        />
        <KpiCard
          label={t('kpi.avgResSalary')}
          value={overview.isLoading ? '…' : formatUSD(overview.data?.avg_resume_salary_usd)}
          icon={<IconCoins size={18} />}
        />
        <KpiCard
          label={t('salary.kpi.vacWith')}
          value={overview.isLoading ? '…' : formatNumber(overview.data?.vacancies_with_salary)}
          hint={
            overview.data
              // частка вакансій, де ЗП вдалось розпарсити/сконвертувати - решта не вказала зарплату взагалі
              ? `${formatPercent(overview.data.vacancies_with_salary, overview.data.total_vacancies)} ${t('salary.ofAll')}`
              : undefined
          }
        />
        <KpiCard
          label={t('salary.kpi.resWith')}
          value={overview.isLoading ? '…' : formatNumber(overview.data?.resumes_with_salary)}
          hint={
            overview.data
              ? `${formatPercent(overview.data.resumes_with_salary, overview.data.total_resumes)} ${t('salary.ofAll')}`
              : undefined
          }
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6">
        <Card
          title="Розподіл зарплат"
          description="Кількість оголошень у кожному діапазоні USD"
        >
          <SalaryHistogram height={420} />
        </Card>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card
            title="Зарплата по рівнях досвіду — вакансії"
            description="Кількість + середня ЗП у кожному бакеті"
          >
            <ExperienceChart type="vacancy" withSalary height={300} />
          </Card>
          <Card
            title="Зарплата по рівнях досвіду — резюме"
            description="Що очікують кандидати"
          >
            <ExperienceChart type="resume" withSalary height={300} />
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <DetailTable type="vacancy" />
          <DetailTable type="resume" />
        </div>
      </div>
    </div>
  )
}

function DetailTable({ type }: { type: DataKind }) {
  const { data, isLoading, isError } = useSalaryDistribution(type)
  const total = (data ?? []).reduce((s, b) => s + b.count, 0)   // сума по всіх бакетах - база для колонки "Частка"

  return (
    <Card
      title={type === 'vacancy' ? 'Деталізація — вакансії' : 'Деталізація — резюме'}
      description={total ? `Загалом ${formatNumber(total)}` : undefined}
    >
      {isLoading ? (
        <Loading rows={6} height="h-4" />
      ) : isError ? (
        <ErrorState />
      ) : !data || data.length === 0 ? (
        <div className="muted py-6 text-center text-sm">Поки немає даних</div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wider muted">
            <tr>
              <th className="py-2 font-medium">Діапазон</th>
              <th className="py-2 text-right font-medium">Кількість</th>
              <th className="py-2 text-right font-medium">Частка</th>
            </tr>
          </thead>
          <tbody>
            {data.map((b) => (
              <tr key={b.range_label} className="border-t border-[var(--card-border)]/60">
                <td className="py-2 font-medium">{b.range_label}</td>
                <td className="py-2 text-right">{formatNumber(b.count)}</td>
                <td className="py-2 text-right muted">{formatPercent(b.count, total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}
