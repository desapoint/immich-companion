export function viewerPageForPosition(position: number | null, pageSize: number): number | null {
  if (position === null || !Number.isFinite(position) || position < 1) return null;
  return Math.max(1, Math.ceil(position / Math.max(1, Math.floor(pageSize))));
}

export function scrollViewedAssetIntoView(container: HTMLElement | null, assetId: string | null): boolean {
  if (!container || !assetId) return false;
  const tile = Array.from(container.querySelectorAll<HTMLElement>('[data-asset-id]'))
    .find((element) => element.dataset.assetId === assetId);
  if (!tile) return false;
  tile.scrollIntoView({ block: 'center', inline: 'nearest' });
  tile.querySelector<HTMLElement>('.v2-asset-main')?.focus({ preventScroll: true });
  return true;
}
