<script lang="ts">
  import { assetMediaUrl } from '../api/assetApi';
  import { formatAssetBytes, formatAssetDate } from '../state/assetViewModel';
  import type { AssetSummary } from '../types/assets';
  import AssetStateChips from './AssetStateChips.svelte';

  interface Props {
    asset: AssetSummary;
    selected: boolean;
    onopen: () => void;
    ontoggle: () => void;
  }

  let { asset, selected, onopen, ontoggle }: Props = $props();
  const fileSize = $derived(formatAssetBytes(asset.file_size_bytes));
</script>

<article class:selected class="asset-card" data-asset-id={asset.id}>
  <header class="card-decision">
    <label class="selection-control">
      <input type="checkbox" checked={selected} onchange={ontoggle} />
      <span>{selected ? 'Selected' : 'Select'}</span>
    </label>
    <span class="media-type">{asset.type}</span>
  </header>

  <button class="media-stage" type="button" onclick={onopen} aria-label={`Open ${asset.original_file_name} in viewer`}>
    <img src={assetMediaUrl(asset.id, 'thumbnail')} alt="" loading="lazy" decoding="async" />
    <span class="media-facts" aria-hidden="true">
      {#if fileSize}<span>{fileSize}</span>{/if}
      {#if asset.width && asset.height}<span>{asset.width} × {asset.height}</span>{/if}
    </span>
    <span class="view-cue">View</span>
  </button>

  <div class="card-content">
    <div class="identity">
      <strong title={asset.original_file_name}>{asset.original_file_name}</strong>
      <span>{formatAssetDate(asset.taken_at)}</span>
    </div>

    <AssetStateChips {asset} />

    <details>
      <summary>Details</summary>
      <dl>
        <div><dt>Immich ID</dt><dd title={asset.id}>{asset.id}</dd></div>
        <div><dt>Modified</dt><dd>{formatAssetDate(asset.file_modified_at)}</dd></div>
        {#if asset.original_mime_type}<div><dt>MIME type</dt><dd>{asset.original_mime_type}</dd></div>{/if}
        {#if asset.visibility}<div><dt>Visibility</dt><dd>{asset.visibility}</dd></div>{/if}
      </dl>
    </details>
  </div>
</article>

<style>
  .asset-card {
    min-width: 0;
    overflow: hidden;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
    transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
  }

  .asset-card:hover {
    border-color: var(--color-border-strong);
    transform: translateY(-0.1rem);
  }

  .asset-card.selected {
    border-color: var(--color-accent-strong);
    box-shadow: inset 0 0 0 0.12rem var(--color-accent-strong), var(--shadow-card);
  }

  .card-decision {
    display: flex;
    min-height: 2.75rem;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.55rem 0.65rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  .selection-control {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    cursor: pointer;
    font-size: 0.72rem;
    font-weight: 760;
  }

  .selection-control input {
    width: 1rem;
    height: 1rem;
    accent-color: var(--color-accent-strong);
  }

  .media-type {
    color: var(--color-ink-muted);
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 760;
  }

  .media-stage {
    position: relative;
    display: block;
    width: 100%;
    height: 13.5rem;
    padding: 0;
    overflow: hidden;
    border: 0;
    color: white;
    background: #080b09;
    cursor: zoom-in;
  }

  .media-stage img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    transition: filter 140ms ease, transform 180ms ease;
  }

  .media-stage:hover img {
    filter: brightness(0.86);
    transform: scale(1.015);
  }

  .media-facts {
    position: absolute;
    right: 0.55rem;
    bottom: 0.5rem;
    display: flex;
    gap: 0.3rem;
  }

  .media-facts span,
  .view-cue {
    padding: 0.24rem 0.42rem;
    border: 1px solid rgb(255 255 255 / 18%);
    border-radius: 999px;
    color: #fff;
    background: rgb(0 0 0 / 66%);
    font-size: 0.62rem;
    font-weight: 720;
    backdrop-filter: blur(0.25rem);
  }

  .view-cue {
    position: absolute;
    top: 0.55rem;
    right: 0.55rem;
    opacity: 0;
    transition: opacity 140ms ease;
  }

  .media-stage:hover .view-cue,
  .media-stage:focus-visible .view-cue {
    opacity: 1;
  }

  .card-content {
    display: grid;
    gap: 0.7rem;
    padding: 0.8rem;
  }

  .identity {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
  }

  .identity strong {
    overflow: hidden;
    font-size: 0.86rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .identity span {
    color: var(--color-ink-muted);
    font-size: 0.7rem;
  }

  details {
    border-top: 1px solid var(--color-border-subtle);
    padding-top: 0.55rem;
  }

  summary {
    width: fit-content;
    color: var(--color-ink-muted);
    cursor: pointer;
    font-size: 0.7rem;
    font-weight: 740;
  }

  dl {
    display: grid;
    gap: 0.4rem;
    margin: 0.6rem 0 0;
  }

  dl div {
    display: grid;
    grid-template-columns: 4.5rem minmax(0, 1fr);
    gap: 0.45rem;
    font-size: 0.65rem;
  }

  dt {
    color: var(--color-ink-muted);
  }

  dd {
    min-width: 0;
    margin: 0;
    overflow: hidden;
    font-family: var(--font-mono);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
