function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function formatTime(iso: string): string {
  if (!iso) return ''
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return ''
  return `${pad2(dt.getHours())}:${pad2(dt.getMinutes())}`
}

export function formatDateTime(iso: string): string {
  if (!iso) return ''
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return ''
  const y = dt.getFullYear()
  const m = pad2(dt.getMonth() + 1)
  const d = pad2(dt.getDate())
  const hh = pad2(dt.getHours())
  const mm = pad2(dt.getMinutes())
  const ss = pad2(dt.getSeconds())
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
}

export function formatTimeSeconds(iso: string): string {
  if (!iso) return ''
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return ''
  return `${pad2(dt.getHours())}:${pad2(dt.getMinutes())}:${pad2(dt.getSeconds())}`
}
