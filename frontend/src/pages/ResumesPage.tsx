import { useEffect, useState } from 'react'
import { useResumes } from '../api/hooks'
import type { ResumeFilters } from '../api/types'
import { Card } from '../components/Card'
import {
  ListingFiltersCard,
  useListingFilters,
} from '../components/ListingFilters'
import { PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, Loading } from '../components/States'
import { formatDate, formatNumber, formatSalaryRange } from '../lib/format'

const PAGE_SIZE = 20

export default function ResumesPage() {
  const { values, setValues, debounced, reset } = useListingFilters()
  const [page, setPage] = useState(1)

  useEffect(() => {
    setPage(1)
  }, [debounced.skill, debounced.location, debounced.minSalary, debounced.experience])

  const filters: ResumeFilters = {
    page,
    limit: PAGE_SIZE,
    skill: debounced.skill.trim() || undefined,
    location: debounced.location.trim() || undefined,
    min_salary_usd: debounced.minSalary ? Number(debounced.minSalary) : undefined,
    experience_years: debounced.experience ? Number(debounced.experience) : undefined,
  }

  const { data, isLoading, isError, isFetching } = useResumes(filters)
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Резюме"
        description={
          data
            ? `Знайдено ${formatNumber(total)} резюме${isFetching ? ' (оновлюється…)' : ''}`
            : 'Перегляд резюме з фільтрами'
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
          experienceHint="Досвід не менше (років)"
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
                  <table className="w-full min-w-[720px] text-sm">
                    <thead className="border-b border-[var(--card-border)] text-left text-xs uppercase tracking-wider muted">
                      <tr>
                        <th className="px-4 py-3 font-medium">Позиція</th>
                        <th className="px-4 py-3 font-medium">Місто</th>
                        <th className="px-4 py-3 font-medium whitespace-nowrap">ЗП (USD)</th>
                        <th className="px-4 py-3 font-medium">Досвід</th>
                        <th className="px-4 py-3 font-medium">English</th>
                        <th className="px-4 py-3 font-medium">Дата</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((r) => (
                        <tr
                          key={r.id}
                          className="border-b border-[var(--card-border)]/70 align-top hover:bg-[var(--card-border)]/20"
                        >
                          <td className="max-w-[340px] px-4 py-3">
                            <div className="font-semibold">{r.title}</div>
                            {r.skills.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                {r.skills.slice(0, 4).map((s) => (
                                  <span key={s} className="chip">
                                    {s}
                                  </span>
                                ))}
                                {r.skills.length > 4 && (
                                  <span className="chip">+{r.skills.length - 4}</span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div>{r.city_name ?? '—'}</div>
                            {r.region && <div className="text-xs muted">{r.region}</div>}
                          </td>
                          <td className="px-4 py-3 font-medium whitespace-nowrap">
                            {formatSalaryRange(r.min_salary_usd_eq, r.max_salary_usd_eq)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {r.experience_years !== null ? `${r.experience_years} р.` : '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap muted">
                            {r.english_level ?? '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap muted">{formatDate(r.created_at)}</td>
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
