export function formatBytes(bytes: number | null | undefined, unavailable = '—'): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return unavailable;
  const absolute = Math.abs(bytes);
  if (absolute < 1024) return `${absolute} B`;
  const units = ['KB', 'MB', 'GB', 'TB'] as const;
  let value = absolute / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unit]}`;
}

export function formatByteDifference(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '—';
  const sign = bytes > 0 ? '+' : bytes < 0 ? '−' : '';
  return `${sign}${formatBytes(Math.abs(bytes))}`;
}
