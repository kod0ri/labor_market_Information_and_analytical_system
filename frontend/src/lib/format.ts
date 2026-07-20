// Централізовані форматери чисел/дат/розміру для всього дашборду - єдине
// місце локалі (uk-UA) і "—" як прочерк для відсутніх значень, щоб кожен
// компонент графіка/картки не писав свій `value ?? '—'` окремо.

const UA = 'uk-UA'

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString(UA)
}

export function formatUSD(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `$${Math.round(value).toLocaleString(UA)}`
}

export function formatSalaryRange(
  min: number | null,
  max: number | null,
): string {
  if (min === null && max === null) return '—'
  if (min !== null && max !== null) {
    if (min === max) return formatUSD(min)
    return `${formatUSD(min)} – ${formatUSD(max)}`
  }
  if (min !== null) return `від ${formatUSD(min)}`
  if (max !== null) return `до ${formatUSD(max)}`
  return '—'
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(UA, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
  } catch {
    return iso
  }
}

export function formatPercent(value: number, total: number): string {
  if (!total) return '0%'
  return `${((value / total) * 100).toFixed(1)}%`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['КБ', 'МБ', 'ГБ', 'ТБ', 'ПБ']
  let value = bytes / 1024
  let i = 0
  // Ділимо на 1024, поки влазить у наступну одиницю - той самий алгоритм,
  // що системний `df`/`du -h`, лише з українськими назвами одиниць.
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i++
  }
  // 0 знаків після коми для великих чисел (100+ ГБ виглядає чистіше без .0),
  // 1 знак для менших - точність важливіша при малих значеннях.
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[i]}`
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(UA, {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}д ${h}г`
  if (h > 0) return `${h}г ${m}хв`
  return `${m}хв`
}
