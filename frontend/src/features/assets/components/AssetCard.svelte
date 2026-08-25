<script lang="ts">
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import { assetMediaUrl } from '../api/assetApi';
  import {
    formatAssetBytes,
    formatAssetDate,
    inlineTagsForAsset,
  } from '../state/assetViewModel';
  import type {
    AssetCardIndicatorConfig,
    AssetSummary,
  } from '../types/assets';
  import AssetRelationIndicators from './AssetRelationIndicators.svelte';
  import AssetStateChips from './AssetStateChips.svelte';
  import AssetTagChips from './AssetTagChips.svelte';

  interface Props {
    asset: AssetSummary;
    selected: boolean;
    selectionActive: boolean;
    indicatorConfig: AssetCardIndicatorConfig;
    matchingTagIds: ReadonlySet<string>;
    onopen: () => void;
    onselect: (shiftKey: boolean) => void;
    ondragstart: (event: PointerEvent) => void;
    ondragenter: (event: PointerEvent) => void;
  }

  let {
    asset,
    selected,
    selectionActive,
    indicatorConfig,
    matchingTagIds,
    onopen,
    onselect,
    ondragstart,
    ondragenter,
  }: Props = $props();
  const fileSize = $derived(formatAssetBytes(asset.file_size_bytes));
  const inlineTags = $derived(
    inlineTagsForAsset(asset.tags, indicatorConfig.inlineTags, matchingTagIds),
  );

  function handleMediaKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    if (selectionActive) onselect(event.shiftKey);
    else onopen();
  }

  function handleMediaPointerDown(event: PointerEvent): void {
    if (!selectionActive || event.pointerType !== 'mouse' || event.button !== 0) return;
    event.preventDefault();
    ondragstart(event);
  }
</script>

<article class:selected class="asset-card" data-asset-id={asset.id}>
  <header class="card-decision">
    <label class="selection-control">
      <input
        type="checkbox"
        checked={selected}
        onclick={(event) => onselect(event.shiftKey)}
      />
      <span>{selected ? 'Selected' : 'Select'}</span>
    </label>
    <span class="media-type">{asset.type}</span>
  </header>

  <div class="media-wrap">
    <div
      class:selection-active={selectionActive}
      class="media-stage"
      role="button"
      tabindex="0"
      aria-label={selectionActive
        ? `${selected ? 'Deselect' : 'Select'} ${asset.original_file_name}`
        : `Open ${asset.original_file_name} in viewer`}
      aria-pressed={selectionActive ? selected : undefined}
      onpointerdown={handleMediaPointerDown}
      onpointerenter={ondragenter}
      onclick={() => { if (!selectionActive) onopen(); }}
      onkeydown={handleMediaKeydown}
    >
      <img src={assetMediaUrl(asset.id, 'thumbnail')} alt="" loading="lazy" decoding="async" />
      <span class="media-facts" aria-hidden="true">
        {#if fileSize}<span>{fileSize}</span>{/if}
        {#if asset.width && asset.height}<span>{asset.width} × {asset.height}</span>{/if}
      </span>
      <span class="selection-cue">{selected ? 'Selected' : 'Select'}</span>
    </div>
    {#if selectionActive}
      <button
        class="view-cue"
        type="button"
        aria-label={`Open ${asset.original_file_name} in viewer`}
        title="Open viewer"
        onpointerdown={(event) => event.stopPropagation()}
        onclick={(event) => { event.stopPropagation(); onopen(); }}
      ><Icon name="view" /><span class="visually-hidden">Open viewer</span></button>
    {:else}
      <span class="view-cue">View</span>
    {/if}
  </div>

  <div class="card-content">
    <div class="identity">
      <strong title={asset.original_file_name}>{asset.original_file_name}</strong>
      <span>{formatAssetDate(asset.taken_at)}</span>
    </div>

    {#if inlineTags.length}
      <AssetTagChips
        tags={inlineTags}
        maxVisible={indicatorConfig.inlineTags === 'matching' ? inlineTags.length : 3}
      />
    {/if}

    <AssetRelationIndicators
      {asset}
      showAlbums={indicatorConfig.albums}
      showTags={indicatorConfig.tags}
      showStack={indicatorConfig.stack}
      showExternal={indicatorConfig.external}
      showImmich={indicatorConfig.immich}
    />

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
    position: relative;
    min-width: 0;
    overflow: visible;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
    transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
  }

  .asset-card:hover {
    z-index: 10;
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

  .media-wrap {
    position: relative;
  }

  .media-stage {
    display: block;
    width: 100%;
    height: 13.5rem;
    padding: 0;
    overflow: hidden;
    border: 0;
    color: white;
    background: #080b09;
    cursor: zoom-in;
    border-radius: 0;
  }

  .media-stage.selection-active {
    cursor: cell;
    touch-action: manipulation;
    user-select: none;
  }

  .media-stage img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    -webkit-user-drag: none;
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

  button.view-cue {
    min-height: auto;
    cursor: zoom-in;
    font: inherit;
  }

  .selection-cue {
    position: absolute;
    top: 0.55rem;
    left: 0.55rem;
    display: none;
    padding: 0.24rem 0.42rem;
    border: 1px solid rgb(255 255 255 / 22%);
    border-radius: 999px;
    color: #fff;
    background: rgb(0 0 0 / 66%);
    font-size: 0.62rem;
    font-weight: 760;
  }

  .selection-active .selection-cue {
    display: block;
  }

  .media-wrap:hover .view-cue,
  .media-wrap:focus-within .view-cue {
    opacity: 1;
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
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
