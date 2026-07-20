import type { ReactNode } from 'react'

// Базовий контейнер картки-панелі, яким побудовано майже весь дашборд -
// заголовок+опис зліва, довільні дії (SegmentedControl тощо) справа,
// довільний вміст (графік/таблиця) нижче.
export function Card({
  title,
  description,
  actions,
  children,
  className = '',
}: {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`card card-pad ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            {title && <h2 className="t-label">{title}</h2>}
            {description && <p className="muted mt-1 text-xs">{description}</p>}
          </div>
          {/* min-w-0 (не shrink-0) - дозволяє рядку дій перенестись на кілька
              рядків на вузьких екранах замість вилізти за межі картки. */}
          {actions && <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
