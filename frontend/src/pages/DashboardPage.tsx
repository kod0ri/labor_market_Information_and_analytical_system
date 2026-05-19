import { useState } from 'react'
import { useOverview } from '../api/hooks'
import type { BucketSize } from '../api/types'
import { Card } from '../components/Card'
import { ActivityChart } from '../components/charts/ActivityChart'
import { EnglishLevelDonut } from '../components/charts/EnglishLevelDonut'
import { ExperienceChart } from '../components/charts/ExperienceChart'
import { ExperienceTimelineChart } from '../components/charts/ExperienceTimelineChart'
import { LocationsChart } from '../components/charts/LocationsChart'
import { SalaryHistogram } from '../components/charts/SalaryHistogram'
import { TopCompaniesChart } from '../components/charts/TopCompaniesChart'
import { TopSkillsChart } from '../components/charts/TopSkillsChart'
import { IconActivity, IconBriefcase, IconCoins, IconSparkles } from '../components/Icon'
import { KpiCard } from '../components/KpiCard'
import { PageHeader } from '../components/PageHeader'
import { SegmentedControl } from '../components/SegmentedControl'
import { ErrorState, Loading } from '../components/States'
import { formatNumber, formatUSD } from '../lib/format'

type Range = '30' | '90' | '180'
type ActivityMetric = 'count' | 'salary'
type ExpMode = 'count' | 'share'

const RANGE_DAYS: Record<Range, number> = { '30': 30, '90': 90, '180': 180 }

export default function DashboardPage() {
  const overview = useOverview()
  const [range, setRange] = useState<Range>('90')
  const [bucket, setBucket] = useState<BucketSize>('week')
  const [metric, setMetric] = useState<ActivityMetric>('count')
  const [expMode, setExpMode] = useState<ExpMode>('share')

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Дашборд"
        description="Зведена статистика ринку IT-вакансій та резюме в Україні"
      />

      {overview.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card card-pad">
              <Loading rows={2} />
            </div>
          ))}
        </div>
      ) : overview.isError ? (
        <ErrorState message="Перевірте чи запущений API на localhost:8000" />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Вакансії"
            value={formatNumber(overview.data?.total_vacancies)}
            icon={<IconBriefcase size={18} />}
            accent
          />
          <KpiCard
            label="Резюме"
            value={formatNumber(overview.data?.total_resumes)}
            icon={<IconSparkles size={18} />}
          />
          <KpiCard
            label="Сер. ЗП вакансій"
            value={formatUSD(overview.data?.avg_vacancy_salary_usd)}
            hint="USD / місяць"
            icon={<IconCoins size={18} />}
          />
          <KpiCard
            label="Сер. ЗП резюме"
            value={formatUSD(overview.data?.avg_resume_salary_usd)}
            hint="USD / місяць"
            icon={<IconActivity size={18} />}
          />
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card
          className="xl:col-span-2"
          title="Активність ринку"
          description={
            metric === 'count'
              ? 'Кількість нових вакансій та резюме у кожному періоді'
              : 'Середня зарплата вакансій та резюме у кожному періоді'
          }
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <SegmentedControl<ActivityMetric>
                value={metric}
                onChange={setMetric}
                segments={[
                  { value: 'count', label: 'Нові' },
                  { value: 'salary', label: 'ЗП' },
                ]}
              />
              <SegmentedControl<BucketSize>
                value={bucket}
                onChange={setBucket}
                segments={[
                  { value: 'day', label: 'Д' },
                  { value: 'week', label: 'Т' },
                  { value: 'month', label: 'М' },
                ]}
              />
              <SegmentedControl<Range>
                value={range}
                onChange={setRange}
                segments={[
                  { value: '30', label: '30д' },
                  { value: '90', label: '90д' },
                  { value: '180', label: '180д' },
                ]}
              />
            </div>
          }
        >
          <ActivityChart bucket={bucket} days={RANGE_DAYS[range]} metric={metric} height={320} />
        </Card>

        <Card title="Розподіл зарплат" description="Вакансії vs резюме у діапазонах USD">
          <SalaryHistogram height={300} />
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6">
        <Card
          title="Структура досвіду в часі"
          description="Як розподіляється попит на junior/middle/senior за період"
          actions={
            <div className="flex items-center gap-2">
              <SegmentedControl<ExpMode>
                value={expMode}
                onChange={setExpMode}
                segments={[
                  { value: 'share', label: 'Частка %' },
                  { value: 'count', label: 'Кількість' },
                ]}
              />
            </div>
          }
        >
          <ExperienceTimelineChart
            type="vacancy"
            bucket={bucket}
            days={RANGE_DAYS[range]}
            mode={expMode}
            height={320}
          />
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Топ навичок" description="Найбільш популярні навички у вакансіях">
          <TopSkillsChart type="vacancy" limit={10} height={340} />
        </Card>

        <Card title="Топ міст" description="Географія активних вакансій">
          <LocationsChart type="vacancy" limit={10} height={340} />
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card title="Досвід та зарплата" description="Кількість вакансій + середня ЗП по рівнях">
          <ExperienceChart type="vacancy" withSalary height={280} />
        </Card>
        <Card title="Рівень англійської" description="Вимоги у вакансіях">
          <EnglishLevelDonut type="vacancy" height={280} />
        </Card>
        <Card title="Топ роботодавців" description="Компанії з найбільшою кількістю вакансій">
          <TopCompaniesChart limit={10} height={280} />
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Досвід кандидатів" description="Рівні досвіду у резюме та середня очікувана ЗП">
          <ExperienceChart type="resume" withSalary height={280} />
        </Card>
        <Card title="Топ навичок у резюме" description="Що знають кандидати">
          <TopSkillsChart type="resume" limit={10} height={340} />
        </Card>
      </div>
    </div>
  )
}
