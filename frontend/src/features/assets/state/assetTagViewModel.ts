const FALLBACK_TAG_COLOR = 'var(--color-accent-strong)';

export function safeAssetTagColor(color: string | null): string {
  return color && /^#[0-9a-f]{6}$/i.test(color) ? color : FALLBACK_TAG_COLOR;
}
