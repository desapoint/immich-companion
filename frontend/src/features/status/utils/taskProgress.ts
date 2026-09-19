export function formatTaskProgressPercent(value: number): string {
  const bounded = Math.min(100, Math.max(0, value));
  const rounded = Math.round(bounded * 100) / 100;
  return `${bounded < 100 ? Math.min(99.99, rounded) : rounded}%`;
}
