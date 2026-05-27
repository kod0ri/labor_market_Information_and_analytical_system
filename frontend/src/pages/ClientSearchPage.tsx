import { useEffect, useState } from 'react'
import { useClientResumes, useClientVacancies } from '../api/hooks'
import type { ClientSearchFilters } from '../api/types'
import { Card } from '../components/Card'
import { ListingFiltersCard, useListingFilters } from '../components/ListingFilters'
import { PageHeader } from '../components/PageHeader'
import { SegmentedControl } from '../components/SegmentedControl'
import { EmptyState, ErrorState, Loading } from '../components/States'
import { formatDate, formatNumber, formatSalaryRange } from '../lib/format'

const PAGE_SIZE = 20

const ENGLISH_LEVELS = [
  'Beginner', 'Elementary', 'Pre-Intermediate',
  'Intermediate', 'Upper-Intermediate', 'Advanced', 'Fluent',
]

type Mode = 'vacancies' | 'resumes'

export default function ClientSearchPage() {
  const [mode, setMode] = useState<Mode>('vacancies')
  const { values, setValues, debounced, reset } = useListingFilters()
  const [englishLevel, setEnglishLevel] = useState('')
  const [page, setPage] = useState(1)

  useEffect(() => {
    setPage(1)
  }, [debounced.skill, debounced.location, debounced.minSalary, debounced.experience, englishLevel, mode])

  const baseFilters: ClientSearchFilters = {
    page,
    page_size: PAGE_SIZE,
    skill: debounced.skill.trim() || undefined,
    location: debounced.location.trim() || undefined,
    min_salary_usd: debounced.minSalary ? Number(debounced.minSalary) : undefined,
    english_level: englishLevel || undefined,
  }

  const vacancyFilters: ClientSearchFilters = {
    ...baseFilters,
    experience_max: debounced.experience ? Number(debounced.experience) : undefined,
  }

  const resumeFilters: ClientSearchFilters = {
    ...baseFilters,
    experience_min: debounced.experience ? Number(debounced.experience) : undefined,
  }

  const vacQuery = useClientVacancies(mode === 'vacancies' ? vacancyFilters : {})
  const resQuery = useClientResumes(mode === 'resumes' ? resumeFilters : {})

  const query = mode === 'vacancies' ? vacQuery : resQuery
  const total = query.data?.total ?? 0
  const totalPages = query.data?.pages ?? 1

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Пошук"
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
              <Card className="!p-0 overflow-hidden">
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
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    ← Попередня
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
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
