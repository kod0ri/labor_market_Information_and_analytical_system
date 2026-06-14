export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="grid h-9 w-9 shrink-0 place-items-center border font-mono text-[13px] font-bold"
        style={{
          color: 'var(--brand)',
          borderColor: 'var(--brand)',
          background: 'var(--brand-soft)',
          borderRadius: 2,
        }}
        aria-hidden
      >
        503
      </div>
      {!collapsed && (
        <div className="flex flex-col leading-tight">
          <span className="font-display text-[15px] font-semibold tracking-tight">503work</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] muted">
            labor·analytics
          </span>
        </div>
      )}
    </div>
  )
}
