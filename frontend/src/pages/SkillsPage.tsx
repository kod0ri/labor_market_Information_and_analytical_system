import { useState } from 'react'
import { useSkillGap, useTopSkills } from '../api/hooks'
import type { DataKind, SkillCategory, SkillGap, SkillStat } from '../api/types'
import { Card } from '../components/Card'
import { TopSkillsChart } from '../components/charts/TopSkillsChart'
import { SkillGapChart } from '../components/charts/SkillGapChart'
import { PageHeader } from '../components/PageHeader'
import { SegmentedControl } from '../components/SegmentedControl'
import { ErrorState, Loading } from '../components/States'
import { formatNumber, formatPercent } from '../lib/format'
import { useI18n } from '../lib/i18n'

// Три вкладки поверх двох різних ендпоінтів: demand/supply перемикають лише
// `type` параметр одного useTopSkills-запиту (той самий графік, інші дані),
// а gap - зовсім окремий useSkillGap-запит із власним графіком праворуч.
type Tab = 'demand' | 'supply' | 'gap'
type Cat = 'all' | SkillCategory

export default function SkillsPage() {
  const { t } = useI18n()
  const [tab, setTab] = useState<Tab>('demand')
  const [category, setCategory] = useState<Cat>('all')

  const isList = tab !== 'gap'                                 // demand/supply рендерять один layout, gap - інший
  const type: DataKind = tab === 'supply' ? 'resume' : 'vacancy'  // supply-вкладка читає резюме, решта (demand) - вакансії

  const topQ = useTopSkills(
    type,
    20,
    category === 'all' ? undefined : category,   // 'all' → undefined, бекенд тоді не фільтрує за категорією
  )
  const gapQ = useSkillGap(20)   // завжди виконується, навіть на demand/supply вкладках (хук не можна викликати умовно)

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title={t('skills.title')}
        description={t('skills.desc')}
        actions={
          <SegmentedControl<Tab>
            value={tab}
            onChange={setTab}
            segments={[
              { value: 'demand', label: t('skills.seg.demand') },
              { value: 'supply', label: t('skills.seg.supply') },
              { value: 'gap', label: t('skills.seg.gap') },
            ]}
          />
        }
      />

      {isList ? (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <Card
            className="xl:col-span-2"
            title={tab === 'demand' ? 'Топ навичок у вакансіях' : 'Топ навичок у резюме'}
            description="Кількість згадок у відповідних оголошеннях"
            actions={
              <SegmentedControl<Cat>
                value={category}
                onChange={setCategory}
                segments={[
                  { value: 'all', label: 'Усі' },
                  { value: 'Hard', label: 'Hard' },
                  { value: 'Soft', label: 'Soft' },
                ]}
              />
            }
          >
            <TopSkillsChart
              type={type}
              limit={20}
              category={category === 'all' ? undefined : category}
              height={560}
            />
          </Card>

          <div className="space-y-6">
            <CategorySplit data={topQ.data} isLoading={topQ.isLoading} />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <Card
            className="xl:col-span-2"
            title="Gap-аналіз: попит vs пропозиція"
            description="Порівняння кількості згадок у вакансіях та резюме"
          >
            <SkillGapChart limit={20} height={560} />
          </Card>

          <div className="space-y-6">
            <GapHighlights data={gapQ.data} isLoading={gapQ.isLoading} isError={gapQ.isError} />
          </div>
        </div>
      )}
    </div>
  )
}

function CategorySplit({
  data,
  isLoading,
}: {
  data: SkillStat[] | undefined
  isLoading: boolean
}) {
  if (isLoading) return <Card title="Hard vs Soft"><Loading rows={2} /></Card>

  const rows = data ?? []
  const hard = rows.filter((r) => r.category === 'Hard').reduce((s, r) => s + r.count, 0)   // сума згадок Hard-навичок у поточному топі
  const soft = rows.filter((r) => r.category === 'Soft').reduce((s, r) => s + r.count, 0)   // -"- Soft
  const total = hard + soft                                                                  // база для відсотків смужки нижче

  if (!total) {
    return (
      <Card title="Hard vs Soft">
        <div className="muted py-4 text-center text-sm">Немає даних</div>
      </Card>
    )
  }

  const hardPct = (hard / total) * 100   // ширина Hard-сегмента смужки у %, Soft = решта (100 - hardPct)
  return (
    <Card title="Hard vs Soft" description="Розподіл у поточному топі">
      <div className="space-y-3 text-sm">
        <div className="flex h-2 overflow-hidden rounded-full bg-[var(--card-border)]">
          <div className="h-full bg-brand-500" style={{ width: `${hardPct}%` }} />
          <div className="h-full bg-[var(--chart-3)]" style={{ width: `${100 - hardPct}%` }} />
        </div>
        <div className="flex justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-brand-500" />
            <span className="muted">Hard</span>
          </div>
          <span className="tabular-nums">
            {formatNumber(hard)} <span className="muted">({formatPercent(hard, total)})</span>
          </span>
        </div>
        <div className="flex justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[var(--chart-3)]" />
            <span className="muted">Soft</span>
          </div>
          <span className="tabular-nums">
            {formatNumber(soft)} <span className="muted">({formatPercent(soft, total)})</span>
          </span>
        </div>
      </div>
    </Card>
  )
}

function GapHighlights({
  data,
  isLoading,
  isError,
}: {
  data: SkillGap[] | undefined
  isLoading: boolean
  isError: boolean
}) {
  if (isLoading) return <Card><Loading rows={4} /></Card>
  if (isError) return <Card><ErrorState /></Card>

  // Топ-5 у КОЖНОМУ напрямку окремо (найбільший дефіцит і найбільше
  // перенасичення), а не топ-10 за модулем - дає читачеві одразу дві чіткі
  // категорії замість одного змішаного списку.
  const rows = data ?? []
  const deficits = [...rows].filter((g) => g.gap > 0).sort((a, b) => b.gap - a.gap).slice(0, 5)   // gap>0: попит>пропозиція, найбільший спершу
  const surplus = [...rows].filter((g) => g.gap < 0).sort((a, b) => a.gap - b.gap).slice(0, 5)     // gap<0: сортуємо за зростанням - найвід'ємніше (найбільший надлишок) спершу

  return (
    <>
      <Card title="Найбільший дефіцит" description="Попит сильно перевищує пропозицію">
        {deficits.length === 0 ? (
          <div className="muted py-3 text-center text-sm">Немає</div>
        ) : (
          <ul className="space-y-2 text-sm">
            {deficits.map((g) => (
              <li key={g.name} className="flex items-center justify-between gap-3">
                <span className="truncate font-medium" title={g.name}>{g.name}</span>
                <span className="shrink-0 rounded-sm bg-red-500/15 px-2 py-0.5 text-xs font-bold text-red-500 tabular-nums">
                  +{formatNumber(g.gap)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Найбільше перенасичення" description="Пропозиція перевищує попит">
        {surplus.length === 0 ? (
          <div className="muted py-3 text-center text-sm">Немає</div>
        ) : (
          <ul className="space-y-2 text-sm">
            {surplus.map((g) => (
              <li key={g.name} className="flex items-center justify-between gap-3">
                <span className="truncate font-medium" title={g.name}>{g.name}</span>
                <span className="shrink-0 rounded-sm bg-emerald-500/15 px-2 py-0.5 text-xs font-bold text-emerald-500 tabular-nums">
                  {formatNumber(g.gap)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Як читати">
        <ul className="space-y-2 text-sm">
          <li className="flex gap-2">
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--chart-1)]" />
            <span><strong>Попит</strong> — кількість вакансій з цією навичкою</span>
          </li>
          <li className="flex gap-2">
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--chart-2)]" />
            <span><strong>Пропозиція</strong> — кількість резюме з цією навичкою</span>
          </li>
          <li className="muted text-xs">
            <span className="font-semibold text-red-500">gap &gt; 0</span> — на ринку не вистачає
            спеціалістів.{' '}
            <span className="font-semibold text-emerald-500">gap &lt; 0</span> — є надлишок.
          </li>
        </ul>
      </Card>
    </>
  )
}
