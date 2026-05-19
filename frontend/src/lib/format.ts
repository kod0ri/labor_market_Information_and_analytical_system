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
