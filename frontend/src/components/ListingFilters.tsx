import { useEffect, useState } from 'react'
import { Card } from './Card'

export interface ListingFilterValues {
  skill: string
  location: string
  minSalary: string
  experience: string
  source: string
}

const EMPTY: ListingFilterValues = {
  skill: '',
  location: '',
  minSalary: '',
  experience: '',
  source: '',
}

// Затримує поширення значення на `delay` мс від ОСТАННЬОЇ зміни - кожен новий
// value скидає попередній таймер (cleanup у useEffect), тож користувач може
// друкувати вільно, і запит на бекенд летить лише після паузи в наборі тексту.
function useDebounced<T>(value: T, delay = 400): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setV(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return v
}

// values - те, що показує форма (оновлюється миттєво, інпут не гальмує);
// debounced - те, що йде у фільтри API-запиту (з паузою) - розділення
// запобігає новому HTTP-запиту на КОЖНЕ натискання клавіші в полі пошуку.
export function useListingFilters() {
  const [values, setValues] = useState<ListingFilterValues>(EMPTY)
  const debounced = {
    skill: useDebounced(values.skill),
    location: useDebounced(values.location),
    minSalary: useDebounced(values.minSalary),
    experience: useDebounced(values.experience),
    source: values.source, // select — застосовуємо одразу, без debounce
  }
  return {
    values,
    setValues,
    debounced,
    reset: () => setValues(EMPTY),
  }
}

export function ListingFiltersCard({
  values,
  onChange,
  onReset,
  experienceHint,
  sources,
}: {
  values: ListingFilterValues
  onChange: (v: ListingFilterValues) => void
  onReset: () => void
  experienceHint?: string
  sources?: string[]
}) {
  function set<K extends keyof ListingFilterValues>(key: K, val: string) {
    onChange({ ...values, [key]: val })
  }
  return (
    <Card
      title="Фільтри"
      actions={
        <button type="button" onClick={onReset} className="btn h-8 text-xs">
          Скинути
        </button>
      }
    >
      <div className="space-y-4">
        <Field label="Навичка">
          <input
            className="input"
            placeholder="Наприклад, Python"
            value={values.skill}
            onChange={(e) => set('skill', e.target.value)}
          />
        </Field>
        <Field label="Місто">
          <input
            className="input"
            placeholder="Київ"
            value={values.location}
            onChange={(e) => set('location', e.target.value)}
          />
        </Field>
        <Field label="Мін. зарплата (USD)">
          <input
            className="input"
            type="number"
            min={0}
            placeholder="1000"
            value={values.minSalary}
            onChange={(e) => set('minSalary', e.target.value)}
          />
        </Field>
        <Field label={experienceHint ?? 'Досвід (років)'}>
          <input
            className="input"
            type="number"
            min={0}
            max={50}
            placeholder="3"
            value={values.experience}
            onChange={(e) => set('experience', e.target.value)}
          />
        </Field>
        {sources && sources.length > 0 && (
          <Field label="Джерело">
            <select
              className="input"
              value={values.source}
              onChange={(e) => set('source', e.target.value)}
            >
              <option value="">Усі джерела</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
    </Card>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1.5 text-xs font-medium muted">{label}</div>
      {children}
    </label>
  )
}
