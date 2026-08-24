<script lang="ts">
  import { formatAssetBytes, formatAssetDate } from '../state/assetViewModel';
  import type { AssetSummary } from '../types/assets';

  interface Props {
    asset: AssetSummary;
    position: number;
    total: number;
  }

  let { asset, position, total }: Props = $props();
  const fileSize = $derived(formatAssetBytes(asset.file_size_bytes));
</script>

<footer class="viewer-footer">
  <div class="footer-facts" aria-label="Current image information">
    <span>{asset.type}</span>
    {#if asset.width && asset.height}<span>{asset.width} × {asset.height}</span>{/if}
    {#if fileSize}<span>{fileSize}</span>{/if}
    <span>{formatAssetDate(asset.taken_at)}</span>
  </div>
  <strong>{position} of {total} images</strong>
</footer>

<style>
  .viewer-footer {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    min-height: 3rem;
    padding: 0.62rem 0.9rem;
    border-top: 1px solid var(--color-border-subtle);
    background: var(--color-surface-raised);
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

  strong {
    flex: 0 0 auto;
    font-size: 0.72rem;
  }

  @media (max-width: 38rem) {
    .viewer-footer {
      align-items: flex-start;
      flex-direction: column;
      gap: 0.45rem;
    }
  }
</style>
