<script lang="ts">
  import { formatAssetBytes, formatAssetDate } from '../state/assetViewModel';
  import type { AssetViewerMedia } from '../types/assets';

  interface Props {
    asset: AssetViewerMedia;
    position: number;
    total: number;
    selectedId: string;
    visibleId: string;
  }

  let {
    asset,
    position,
    total,
    selectedId,
    visibleId,
  }: Props = $props();
  const fileSize = $derived(formatAssetBytes(asset.file_size_bytes ?? null));
</script>

<footer class="viewer-footer">
  <div class="footer-summary">
    <div class="footer-facts" aria-label="Visible image information">
      <span>{asset.type}</span>
      {#if asset.width && asset.height}<span>{asset.width} × {asset.height}</span>{/if}
      {#if fileSize}<span>{fileSize}</span>{/if}
      {#if asset.taken_at}<span>{formatAssetDate(asset.taken_at)}</span>{/if}
      {#if selectedId !== visibleId}<span class="comparison-state">Previewing stack member</span>{/if}
    </div>
    <strong>{position} of {total} images</strong>
  </div>
</footer>

<style>
  .viewer-footer {
    display: grid;
    flex: none;
    min-width: 0;
    border-top: 1px solid var(--color-border-subtle);
    background: var(--color-surface-raised);
  }

  .footer-summary {
    display: flex;
    align-items: center;
  }

  .footer-summary {
    justify-content: space-between;
    gap: 1rem;
    min-height: 3rem;
    padding: 0.62rem 0.9rem;
  }

  .footer-facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .footer-facts span {
    padding: 0.22rem 0.42rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    font-size: 0.65rem;
  }

  .footer-facts .comparison-state {
    color: var(--color-warning-ink);
    border-color: var(--color-warning-border);
    background: var(--color-warning-surface);
  }

  .footer-summary > strong {
    flex: 0 0 auto;
    font-size: 0.72rem;
  }

  @media (max-width: 38rem) {
    .footer-summary {
      align-items: flex-start;
      flex-direction: column;
      gap: 0.45rem;
    }
  }
</style>
