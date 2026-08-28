<script lang="ts">
  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
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
    condensed?: boolean;
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
    condensed = false,
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

<article class:selected class:condensed class="asset-card" data-asset-id={asset.id}>
  {#if !condensed}
    <header class="card-decision">
      <Checkbox
        checked={selected}
        label={selected ? 'Selected' : 'Select'}
        ariaLabel={`${selected ? 'Deselect' : 'Select'} ${asset.original_file_name}`}
        onclick={(event) => { event.preventDefault(); onselect(event.shiftKey); }}
      />
      <span class="media-type">{asset.type}</span>
    </header>
  {/if}

  <div class="media-wrap">
    {#if condensed}
      <div class="condensed-selection">
        <Checkbox
          checked={selected}
          label={`${selected ? 'Deselect' : 'Select'} ${asset.original_file_name}`}
          hiddenLabel
          onclick={(event) => { event.preventDefault(); onselect(event.shiftKey); }}
        />
      </div>
    {/if}
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
      {#if !condensed}
        <span class="media-facts" aria-hidden="true">
          {#if fileSize}<span>{fileSize}</span>{/if}
          {#if asset.width && asset.height}<span>{asset.width} × {asset.height}</span>{/if}
        </span>
        <span class="selection-cue">{selected ? 'Selected' : 'Select'}</span>
      {/if}
    </div>
    <button
      class="view-cue"
      type="button"
      aria-label={`Open ${asset.original_file_name} in viewer`}
      title="Open viewer"
      onpointerdown={(event) => event.stopPropagation()}
      onclick={(event) => { event.stopPropagation(); onopen(); }}
    ><Icon name="view" size="1.4rem" /><span class="visually-hidden">Open viewer</span></button>
    {#if condensed}
      <div class="condensed-indicators">
        <AssetRelationIndicators
          {asset}
          showAlbums={indicatorConfig.albums}
          showTags={indicatorConfig.tags}
          showStack={indicatorConfig.stack}
          showExternal={indicatorConfig.external}
          showImmich={indicatorConfig.immich}
        />
      </div>
    {/if}
  </div>

  {#if !condensed}
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
  {/if}
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
    z-index: 200;
    border-color: var(--color-border-strong);
    transform: translateY(-0.1rem);
  }

  .asset-card:focus-within {
    z-index: 100;
  }

  .asset-card.selected {
    border-color: var(--color-accent-strong);
    box-shadow: inset 0 0 0 0.12rem var(--color-accent-strong), var(--shadow-card);
  }

  .asset-card.condensed {
    overflow: visible;
    border-radius: var(--radius-sm);
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

  .condensed-selection {
    position: absolute;
    z-index: 12;
    top: 0.5rem;
    left: 0.5rem;
    display: grid;
    width: 2rem;
    height: 2rem;
    place-items: center;
    border: 1px solid rgb(255 255 255 / 28%);
    border-radius: 999px;
    color: white;
    background: rgb(0 0 0 / 70%);
    backdrop-filter: blur(0.35rem);
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

  .condensed .media-stage {
    height: auto;
    aspect-ratio: 1;
    border-radius: var(--radius-sm);
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

  .media-facts span {
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
    display: grid;
    width: 3rem;
    height: 3rem;
    padding: 0;
    place-items: center;
    border: 1px solid rgb(255 255 255 / 28%);
    border-radius: 999px;
    color: #fff;
    background: rgb(0 0 0 / 70%);
    cursor: zoom-in;
    font: inherit;
    opacity: 0.78;
    backdrop-filter: blur(0.35rem);
    transition: opacity 140ms ease, transform 140ms ease, background 140ms ease;
  }

  .condensed .view-cue {
    z-index: 12;
    width: 2rem;
    height: 2rem;
  }

  .condensed-indicators {
    position: absolute;
    z-index: 11;
    right: 0.45rem;
    bottom: 0.45rem;
    left: 0.45rem;
    padding: 0.25rem;
    border-radius: var(--radius-sm);
    background: rgb(0 0 0 / 62%);
    backdrop-filter: blur(0.35rem);
  }

  .condensed-indicators :global(.relation-indicators) {
    flex-wrap: nowrap;
    overflow: visible;
  }

  .condensed-indicators :global(.relation-indicator > button),
  .condensed-indicators :global(.immich-link) {
    min-width: 1.8rem;
    min-height: 1.8rem;
    padding: 0.28rem 0.38rem;
    border-color: rgb(255 255 255 / 24%);
    color: white;
    background: rgb(0 0 0 / 68%);
  }

  .condensed-indicators :global(.immich-link > span) {
    display: none;
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
    transform: scale(1.04);
    background: rgb(0 0 0 / 82%);
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
