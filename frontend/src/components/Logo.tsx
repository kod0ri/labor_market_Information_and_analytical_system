export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="grid h-9 w-9 place-items-center rounded-lg bg-brand-500/15 font-extrabold text-brand-500
                   ring-1 ring-brand-500/40"
        aria-hidden
      >
        503
      </div>
      {!collapsed && (
        <div className="flex flex-col leading-tight">
          <span className="text-base font-extrabold tracking-tight">503Work</span>
          <span className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--muted-fg)' }}>
            labor analytics
          </span>
        </div>
      )}
    </div>
  )
}
