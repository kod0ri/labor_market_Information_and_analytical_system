import { useEffect, useState } from 'react'
import { useVacancies } from '../api/hooks'
import type { VacancyFilters } from '../api/types'
import { Card } from '../components/Card'
import {
  ListingFiltersCard,
  useListingFilters,
} from '../components/ListingFilters'
import { PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, Loading } from '../components/States'
import { formatDate, formatNumber, formatSalaryRange } from '../lib/format'

const PAGE_SIZE = 20

export default function VacanciesPage() {
  const { values, setValues, debounced, reset } = useListingFilters()
  const [page, setPage] = useState(1)

  useEffect(() => {
    setPage(1)
  }, [debounced.skill, debounced.location, debounced.minSalary, debounced.experience])

  const filters: VacancyFilters = {
    page,
    limit: PAGE_SIZE,
    skill: debounced.skill.trim() || undefined,
    location: debounced.location.trim() || undefined,
    min_salary_usd: debounced.minSalary ? Number(debounced.minSalary) : undefined,
    experience_years: debounced.experience ? Number(debounced.experience) : undefined,
  }

  const { data, isLoading, isError, isFetching } = useVacancies(filters)
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Вакансії"
        description={
          data
            ? `Знайдено ${formatNumber(total)} вакансій${isFetching ? ' (оновлюється…)' : ''}`
            : 'Перегляд вакансій з фільтрами'
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px,minmax(0,1fr)]">
        <ListingFiltersCard
          values={values}
          onChange={setValues}
          onReset={() => {
            reset()
            setPage(1)
          }}
          experienceHint="Досвід не більше (років)"
        />

        <div className="min-w-0 space-y-4">
          {isLoading ? (
            <Card>
              <Loading rows={8} height="h-6" />
            </Card>
          ) : isError ? (
            <Card>
              <ErrorState />
            </Card>
          ) : !data || data.items.length === 0 ? (
            <Card>
              <EmptyState title="Нічого не знайдено" description="Спробуйте змінити фільтри" />
            </Card>
          ) : (
            <>
              <Card className="!p-0 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-sm">
                    <thead className="border-b border-[var(--card-border)] text-left text-xs uppercase tracking-wider muted">
                      <tr>
                        <th className="px-4 py-3 font-medium">Посада</th>
                        <th className="px-4 py-3 font-medium">Компанія</th>
                        <th className="px-4 py-3 font-medium">Місто</th>
                        <th className="px-4 py-3 font-medium whitespace-nowrap">ЗП (USD)</th>
                        <th className="px-4 py-3 font-medium">Досвід</th>
                        <th className="px-4 py-3 font-medium">Дата</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((v) => (
                        <tr
                          key={v.id}
                          className="border-b border-[var(--card-border)]/70 align-top hover:bg-[var(--card-border)]/20"
                        >
                          <td className="max-w-[320px] px-4 py-3">
                            <div className="font-semibold">{v.title}</div>
                            {v.skills.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                {v.skills.slice(0, 4).map((s) => (
                                  <span key={s} className="chip">
                                    {s}
                                  </span>
                                ))}
                                {v.skills.length > 4 && (
                                  <span className="chip">+{v.skills.length - 4}</span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className="max-w-[180px] truncate px-4 py-3">{v.company_name ?? '—'}</td>
                          <td className="px-4 py-3">
                            <div>{v.city_name ?? '—'}</div>
                            {v.region && <div className="text-xs muted">{v.region}</div>}
                          </td>
                          <td className="px-4 py-3 font-medium whitespace-nowrap">
                            {formatSalaryRange(v.min_salary_usd_eq, v.max_salary_usd_eq)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {v.experience_years !== null ? `${v.experience_years} р.` : '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap muted">{formatDate(v.created_at)}</td>
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
