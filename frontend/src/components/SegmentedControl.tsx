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
    <div
      className="inline-flex border border-[var(--card-border)] bg-[var(--app-bg)] p-0.5"
      style={{ borderRadius: 2 }}
      role="group"
    >
      {segments.map((s) => {
        const active = s.value === value
        return (
          <button
            key={s.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(s.value)}
            className={`min-h-[32px] px-2.5 font-mono text-[11px] font-medium uppercase tracking-wider
                        transition-colors sm:px-3 ${
                          active
                            ? 'text-white'
                            : 'muted hover:text-[var(--app-fg)]'
                        }`}
            style={{
              borderRadius: 1,
              background: active ? 'var(--brand)' : 'transparent',
            }}
          >
            {s.label}
          </button>
        )
      })}
    </div>
  )
}
