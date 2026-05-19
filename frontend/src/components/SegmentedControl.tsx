export interface Segment<T extends string> {
  value: T
  label: string
}

export function SegmentedControl<T extends string>({
  value,
  onChange,
  segments,
}: {
  value: T
  onChange: (v: T) => void
  segments: Segment<T>[]
}) {
  return (
    <div className="inline-flex rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] p-0.5 text-xs">
      {segments.map((s) => {
        const active = s.value === value
        return (
          <button
            key={s.value}
            type="button"
            onClick={() => onChange(s.value)}
            className={`rounded-[5px] px-3 py-1.5 font-medium transition-colors ${
              active
                ? 'bg-brand-500 text-white shadow-sm'
                : 'muted hover:text-[var(--app-fg)]'
            }`}
          >
            {s.label}
          </button>
        )
      })}
    </div>
  )
}
