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
import { SourcesBreakdown } from '../components/charts/SourcesBreakdown'
import { TopCompaniesChart } from '../components/charts/TopCompaniesChart'
import { TopSkillsChart } from '../components/charts/TopSkillsChart'
import { IconActivity, IconBriefcase, IconCoins, IconSparkles } from '../components/Icon'
import { KpiCard } from '../components/KpiCard'
import { PageHeader } from '../components/PageHeader'
import { SegmentedControl } from '../components/SegmentedControl'
import { ErrorState, Loading } from '../components/States'
import { formatNumber, formatUSD } from '../lib/format'
import { useI18n } from '../lib/i18n'

// Головна сторінка дашборду - огляд усього ринку в одному скролі: 4 KPI
// зверху, потім ряди карток із графіками. `range`/`bucket` - спільний стан
// для ActivityChart і ExperienceTimelineChart (обидва графіки часового ряду
// синхронно реагують на один і той самий перемикач періоду в шапці "Активність ринку").
type Range = '30' | '90' | '180'
type ActivityMetric = 'count' | 'salary'
type ExpMode = 'count' | 'share'

const RANGE_DAYS: Record<Range, number> = { '30': 30, '90': 90, '180': 180 }

export default function DashboardPage() {
  const { t } = useI18n()
  const overview = useOverview()                              // окремий запит для 4 верхніх KPI-карток
  const [range, setRange] = useState<Range>('90')              // 30/90/180 днів - спільний для activity+timeline
  const [bucket, setBucket] = useState<BucketSize>('week')     // день/тиждень/місяць - теж спільний
  const [metric, setMetric] = useState<ActivityMetric>('count')  // "Нові"/"ЗП" - перемикач в картці Активність ринку
  const [expMode, setExpMode] = useState<ExpMode>('share')     // "частка"/"кількість" - перемикач лише в картці таймлайну досвіду

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title={t('dash.title')} description={t('dash.desc')} />

      {overview.isLoading ? (
        // 4 skeleton-картки замість реальних KPI, поки /overview ще вантажиться
        <div className="reveal reveal-1 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card card-pad">
              <Loading rows={2} />
            </div>
          ))}
        </div>
      ) : overview.isError ? (
        <ErrorState message={t('dash.err.api')} />
      ) : (
        <div className="reveal reveal-1 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label={t('kpi.vacancies')}
            value={formatNumber(overview.data?.total_vacancies)}
            icon={<IconBriefcase size={18} />}
            accent
          />
          <KpiCard
            label={t('kpi.resumes')}
            value={formatNumber(overview.data?.total_resumes)}
            icon={<IconSparkles size={18} />}
          />
          <KpiCard
            label={t('kpi.avgVacSalary')}
            value={formatUSD(overview.data?.avg_vacancy_salary_usd)}
            hint={t('kpi.usdMonth')}
            icon={<IconCoins size={18} />}
          />
          <KpiCard
            label={t('kpi.avgResSalary')}
            value={formatUSD(overview.data?.avg_resume_salary_usd)}
            hint={t('kpi.usdMonth')}
            icon={<IconActivity size={18} />}
          />
        </div>
      )}

      <div className="reveal reveal-2 mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* 2/3 ширини на xl+ - головна картка ряду, гістограма ЗП поруч займає лишню 1/3 */}
        <Card
          className="xl:col-span-2"
          title={t('card.activity.title')}
          description={
            metric === 'count' ? t('card.activity.descCount') : t('card.activity.descSalary')
          }
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {/* три незалежні перемикачі в одному ряду: метрика графіка, розмір бакета, діапазон днів */}
              <SegmentedControl<ActivityMetric>
                value={metric}
                onChange={setMetric}
                segments={[
                  { value: 'count', label: t('seg.new') },
                  { value: 'salary', label: t('seg.salary') },
                ]}
              />
              <SegmentedControl<BucketSize>
                value={bucket}
                onChange={setBucket}
                segments={[
                  { value: 'day', label: t('seg.day') },
                  { value: 'week', label: t('seg.week') },
                  { value: 'month', label: t('seg.month') },
                ]}
              />
              <SegmentedControl<Range>
                value={range}
                onChange={setRange}
                segments={[
                  { value: '30', label: t('seg.30d') },
                  { value: '90', label: t('seg.90d') },
                  { value: '180', label: t('seg.180d') },
                ]}
              />
            </div>
          }
        >
          <ActivityChart bucket={bucket} days={RANGE_DAYS[range]} metric={metric} height={320} />
        </Card>

        <Card title={t('card.salaryDist.title')} description={t('card.salaryDist.desc')}>
          <SalaryHistogram height={300} />
        </Card>
      </div>

      <div className="reveal reveal-3 mt-6 grid grid-cols-1 gap-6">
        <Card
          title={t('card.expTime.title')}
          description={t('card.expTime.desc')}
          actions={
            <div className="flex items-center gap-2">
              <SegmentedControl<ExpMode>
                value={expMode}
                onChange={setExpMode}
                segments={[
                  { value: 'share', label: t('seg.share') },
                  { value: 'count', label: t('seg.count') },
                ]}
              />
            </div>
          }
        >
          {/* bucket/range тут ті самі, що й у картці "Активність ринку" вище -
              один спільний стан керує обома графіками часового ряду */}
          <ExperienceTimelineChart
            type="vacancy"
            bucket={bucket}
            days={RANGE_DAYS[range]}
            mode={expMode}
            height={320}
          />
        </Card>
      </div>

      <div className="reveal reveal-4 mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title={t('card.topSkills.title')} description={t('card.topSkills.desc')}>
          <TopSkillsChart type="vacancy" limit={10} height={340} />
        </Card>

        <Card title={t('card.topCities.title')} description={t('card.topCities.desc')}>
          <LocationsChart type="vacancy" limit={10} height={340} />
        </Card>
      </div>

      <div className="reveal reveal-4 mt-6 grid grid-cols-1 gap-6">
        <Card title={t('card.sources.title')} description={t('card.sources.desc')}>
          <SourcesBreakdown height={320} />
        </Card>
      </div>

      <div className="reveal reveal-5 mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card title={t('card.expSalary.title')} description={t('card.expSalary.desc')}>
          <ExperienceChart type="vacancy" withSalary height={280} />
        </Card>
        <Card title={t('card.english.title')} description={t('card.english.desc')}>
          <EnglishLevelDonut type="vacancy" height={280} />
        </Card>
        <Card title={t('card.topEmployers.title')} description={t('card.topEmployers.desc')}>
          <TopCompaniesChart limit={10} height={280} />
        </Card>
      </div>

      <div className="reveal reveal-6 mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title={t('card.candExp.title')} description={t('card.candExp.desc')}>
          <ExperienceChart type="resume" withSalary height={280} />
        </Card>
        <Card title={t('card.resumeSkills.title')} description={t('card.resumeSkills.desc')}>
          <TopSkillsChart type="resume" limit={10} height={340} />
        </Card>
      </div>
    </div>
  )
}
