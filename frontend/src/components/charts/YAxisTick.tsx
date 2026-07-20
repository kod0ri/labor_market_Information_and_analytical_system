// Кастомний recharts tick-компонент для горизонтальних bar chart'ів (топ
// навичок/компаній/міст), де назви можуть бути значно довшими за виділений
// простір осі Y - без обрізання довгі назви або накладались би одна на одну,
// або розпирали графік. `<title>` дає повний текст у tooltip браузера при наведенні.
interface TickProps {
  x?: number
  y?: number
  payload?: { value?: string }
  maxChars?: number
}

export function YAxisTruncatedTick({ x = 0, y = 0, payload, maxChars = 22 }: TickProps) {
  const raw = payload?.value ?? ''
  const text = raw.length > maxChars ? raw.slice(0, maxChars - 1) + '…' : raw
  return (
    <g transform={`translate(${x},${y})`}>
      <title>{raw}</title>
      <text
        x={-8}
        y={0}
        dy={4}
        textAnchor="end"
        fill="var(--muted-fg)"
        fontSize={12}
      >
        {text}
      </text>
    </g>
  )
}
