import { useEffect, useState } from 'react'
import { useClientResumes, useClientVacancies, useSources } from '../api/hooks'
import type { ClientSearchFilters } from '../api/types'
import { Card } from '../components/Card'
import { ListingFiltersCard, useListingFilters } from '../components/ListingFilters'
import { PageHeader } from '../components/PageHeader'
import { SegmentedControl } from '../components/SegmentedControl'
import { EmptyState, ErrorState, Loading } from '../components/States'
import { formatDate, formatNumber, formatSalaryRange } from '../lib/format'
import { useI18n } from '../lib/i18n'

const PAGE_SIZE = 20

const ENGLISH_LEVELS = [
  'Beginner', 'Elementary', 'Pre-Intermediate',
  'Intermediate', 'Upper-Intermediate', 'Advanced', 'Fluent',
]

type Mode = 'vacancies' | 'resumes'

// Пошук по /api/client/{vacancies,resumes}/search. Обидва хуки (useClientVacancies/
// useClientResumes) викликаються ЗАВЖДИ (правило хуків React забороняє умовний
// виклик), і в обох немає `enabled`-прапорця в hooks.ts - тож НЕактивний режим
// теж реально шле запит, лише з порожніми фільтрами {} замість справжніх
// (зайвий, але дешевий HTTP-виклик; не оптимізовано навмисно чи випадково -
// варто мати на увазі при профілюванні мережі).
export default function ClientSearchPage() {
  const { t } = useI18n()
  const [mode, setMode] = useState<Mode>('vacancies')
  const { values, setValues, debounced, reset } = useListingFilters()
  const [englishLevel, setEnglishLevel] = useState('')
  const [page, setPage] = useState(1)
  const sourcesQuery = useSources()
  const sourceNames = sourcesQuery.data?.map((s) => s.source) ?? []   // список назв для select-фільтра "Джерело"

  // Будь-яка зміна фільтра/режиму скидає на 1-шу сторінку - інакше можна
  // застрягти на сторінці 5, змінити фільтр і побачити порожній результат,
  // бо під новим фільтром сторінок може бути менше.
  useEffect(() => {
    setPage(1)
  }, [debounced.skill, debounced.location, debounced.minSalary, debounced.experience, debounced.source, englishLevel, mode])

  const baseFilters: ClientSearchFilters = {   // спільні для обох режимів фільтри (усе, крім семантики experience)
    page,
    page_size: PAGE_SIZE,
    skill: debounced.skill.trim() || undefined,               // порожній рядок → undefined (apiGet пропустить параметр)
    location: debounced.location.trim() || undefined,
    min_salary_usd: debounced.minSalary ? Number(debounced.minSalary) : undefined,   // рядок з інпута → число
    english_level: englishLevel || undefined,
    source: debounced.source || undefined,
  }

  const vacancyFilters: ClientSearchFilters = {
    ...baseFilters,
    // "досвід не більше N років" - окремий query-параметр experience_max
    // (не плутати з experience_min у resumeFilters нижче - різні поля на
    // рівні HTTP-запиту, хоча на бекенді обидва зрештою зводяться до одного
    // internal-ключа "experience_max" через ExperienceFilterStrategy).
    experience_max: debounced.experience ? Number(debounced.experience) : undefined,
  }

  const resumeFilters: ClientSearchFilters = {
    ...baseFilters,
    // "досвід кандидата не менше N років" - окремий параметр experience_min
    experience_min: debounced.experience ? Number(debounced.experience) : undefined,
  }

  const vacQuery = useClientVacancies(mode === 'vacancies' ? vacancyFilters : {})
  const resQuery = useClientResumes(mode === 'resumes' ? resumeFilters : {})

  const query = mode === 'vacancies' ? vacQuery : resQuery   // активний запит для рендеру - другий просто ігнорується
  const total = query.data?.total ?? 0
  const totalPages = query.data?.pages ?? 1                  // з бекенду (ceil(total/page_size)) - не рахуємо самі

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title={t('search.title')}
        description={
          query.data
            ? `Знайдено ${formatNumber(total)} записів${query.isFetching ? ' (оновлюється…)' : ''}`
            : 'Пошук вакансій та резюме з фільтрами'
        }
      />

      <div className="mb-5">
        <SegmentedControl
          segments={[
            { value: 'vacancies', label: 'Вакансії' },
            { value: 'resumes', label: 'Резюме' },
          ]}
          value={mode}
          onChange={(v) => setMode(v as Mode)}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px,minmax(0,1fr)]">
        <div className="space-y-4">
          <ListingFiltersCard
            values={values}
            onChange={setValues}
            onReset={() => {
              reset()
              setEnglishLevel('')
              setPage(1)
            }}
            experienceHint={mode === 'vacancies' ? 'Досвід не більше (років)' : 'Досвід не менше (років)'}
            sources={sourceNames}
          />

          <Card title="Рівень англійської">
            <div className="space-y-1">
              <button
                type="button"
                className={`w-full rounded px-3 py-1.5 text-left text-sm transition-colors ${
                  englishLevel === '' ? 'bg-brand-500 text-white' : 'hover:bg-[var(--card-border)]/40'
                }`}
                onClick={() => setEnglishLevel('')}
              >
                Всі рівні
              </button>
              {ENGLISH_LEVELS.map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  className={`w-full rounded px-3 py-1.5 text-left text-sm transition-colors ${
                    englishLevel === lvl ? 'bg-brand-500 text-white' : 'hover:bg-[var(--card-border)]/40'
                  }`}
                  onClick={() => setEnglishLevel(lvl)}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </Card>
        </div>

        <div className="min-w-0 space-y-4">
          {query.isLoading ? (
            <Card><Loading rows={8} height="h-6" /></Card>
          ) : query.isError ? (
            <Card><ErrorState /></Card>
          ) : !query.data || query.data.items.length === 0 ? (
            <Card>
              <EmptyState title="Нічого не знайдено" description="Спробуйте змінити фільтри" />
            </Card>
          ) : (
            <>
              {/* Два незалежні рендери одних і тих самих даних: картки для
                  <md (таблиця з 7 колонками не влізла б без горизонтального
                  скролу на телефоні) і повна таблиця для md+. Обидва
                  завжди в DOM, Tailwind (`md:hidden`/`hidden md:block`)
                  просто ховає непотрібний варіант через CSS. */}
              <div className="space-y-3 md:hidden">
                {query.data.items.map((item) => (
                  <div key={item.id} className="card p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 font-semibold leading-snug">{item.title}</div>
                      <div className="num shrink-0 text-sm font-bold" style={{ color: 'var(--brand)' }}>
                        {formatSalaryRange(item.min_salary_usd_eq, item.max_salary_usd_eq)}
                      </div>
                    </div>
                    {/* item - об'єднаний тип вакансія|резюме, тож company_name є лише
                        у вакансій; 'in'-перевірка + приведення типу, бо TS не звужує
                        union за рантайм-полем mode самостійно */}
                    {mode === 'vacancies' && 'company_name' in item &&
                      (item as { company_name?: string | null }).company_name && (
                        <div className="muted mt-0.5 truncate text-xs">
                          {(item as { company_name?: string | null }).company_name}
                        </div>
                      )}
                    <div className="muted mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px]">
                      <span>{item.city_name ?? '—'}</span>
                      <span>
                        досвід: {item.experience_years !== null ? `${item.experience_years} р.` : '—'}
                      </span>
                      <span>eng: {item.english_level ?? '—'}</span>
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                    {item.skills.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {item.skills.slice(0, 5).map((s) => (
                          <span key={s} className="chip">{s}</span>
                        ))}
                        {item.skills.length > 5 && (
                          <span className="chip">+{item.skills.length - 5}</span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <Card className="!p-0 hidden overflow-hidden md:block">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[700px] text-sm">
                    <thead className="border-b border-[var(--card-border)] text-left text-xs uppercase tracking-wider muted">
                      <tr>
                        <th className="px-4 py-3 font-medium">
                          {mode === 'vacancies' ? 'Посада' : 'Спеціальність'}
                        </th>
                        {mode === 'vacancies' && (
                          <th className="px-4 py-3 font-medium">Компанія</th>
                        )}
                        <th className="px-4 py-3 font-medium">Місто</th>
                        <th className="px-4 py-3 font-medium whitespace-nowrap">ЗП (USD)</th>
                        <th className="px-4 py-3 font-medium">Досвід</th>
                        <th className="px-4 py-3 font-medium">English</th>
                        <th className="px-4 py-3 font-medium">Дата</th>
                      </tr>
                    </thead>
                    <tbody>
                      {query.data.items.map((item) => (
                        <tr
                          key={item.id}
                          className="border-b border-[var(--card-border)]/70 align-top hover:bg-[var(--card-border)]/20"
                        >
                          <td className="max-w-[280px] px-4 py-3">
                            <div className="font-semibold">{item.title}</div>
                            {item.skills.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                {item.skills.slice(0, 4).map((s) => (
                                  <span key={s} className="chip">{s}</span>
                                ))}
                                {item.skills.length > 4 && (
                                  <span className="chip">+{item.skills.length - 4}</span>
                                )}
                              </div>
                            )}
                          </td>
                          {mode === 'vacancies' && (
                            <td className="max-w-[160px] truncate px-4 py-3">
                              {('company_name' in item && (item as { company_name?: string | null }).company_name) ?? '—'}
                            </td>
                          )}
                          <td className="px-4 py-3">
                            <div>{item.city_name ?? '—'}</div>
                            {item.region && (
                              <div className="text-xs muted">{item.region}</div>
                            )}
                          </td>
                          <td className="px-4 py-3 font-medium whitespace-nowrap">
                            {formatSalaryRange(item.min_salary_usd_eq, item.max_salary_usd_eq)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {item.experience_years !== null ? `${item.experience_years} р.` : '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {item.english_level ?? '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap muted">
                            {formatDate(item.created_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <div className="flex items-center justify-between">
                <div className="text-xs muted">
                  Сторінка {page} з {totalPages}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="btn"
                    disabled={page <= 1}                                    // на 1-й сторінці "назад" неактивна
                    onClick={() => setPage((p) => Math.max(1, p - 1))}       // clamp знизу - про всяк випадок, не має спрацювати при disabled
                  >
                    ← Попередня
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={page >= totalPages}                                  // на останній сторінці "вперед" неактивна
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}     // clamp зверху - симетрично до кнопки "назад"
                  >
                    Наступна →
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
