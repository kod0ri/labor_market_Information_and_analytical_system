import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { useI18n } from '../lib/i18n'

interface FallbackTexts {
  title: string
  text: string
  reload: string
}

interface Props {
  texts: FallbackTexts
  children: ReactNode
}

interface State {
  hasError: boolean
}

/** Class-компонент: хуки тут недоступні, тексти приходять пропсами з обгортки. */
class Boundary extends Component<Props, State> {
  state: State = { hasError: false }    // початковий стан - помилки ще не було

  static getDerivedStateFromError(): State {
    // Викликається React ПІД ЧАС рендеру, коли дочірній компонент кинув помилку.
    // Повертає новий state - React одразу перемальовує з hasError=true (fallback UI).
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Викликається ПІСЛЯ рендеру - тут лише побічний ефект (логування),
    // не можна міняти state звідси (для цього є getDerivedStateFromError вище).
    console.error('ErrorBoundary:', error, info.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    const { title, text, reload } = this.props.texts
    return (
      <div className="grid place-items-center px-4 py-24 text-center">
        <div>
          <div className="font-display text-5xl font-bold tracking-tight" style={{ color: 'var(--err)' }}>
            500
          </div>
          <p className="mt-3 font-mono text-xs uppercase tracking-[0.18em] muted">{title}</p>
          <p className="muted mt-1 text-sm">{text}</p>
          <button
            type="button"
            className="btn-primary mt-6 inline-flex"
            onClick={() => window.location.reload()}
          >
            {reload}
          </button>
        </div>
      </div>
    )
  }
}

export function ErrorBoundary({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  return (
    <Boundary
      texts={{ title: t('boundary.title'), text: t('boundary.text'), reload: t('boundary.reload') }}
    >
      {children}
    </Boundary>
  )
}
