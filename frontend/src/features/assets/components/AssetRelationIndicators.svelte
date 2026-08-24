<script lang="ts">
  import AssetPreviewStrip from '../../../lib/components/domain/AssetPreviewStrip.svelte';
  import { buildAssetPreviewItems } from '../api/assetApi';
  import { stackMembersForAsset } from '../state/assetViewModel';
  import type { AssetSummary } from '../types/assets';
  import AssetIcon from './AssetIcon.svelte';
  import AssetRelationIndicator from './AssetRelationIndicator.svelte';

  interface Props {
    asset: AssetSummary;
    showAlbums?: boolean;
    showTags?: boolean;
    showStack?: boolean;
    showExternal?: boolean;
    showImmich?: boolean;
  }

  let {
    asset,
    showAlbums = true,
    showTags = true,
    showStack = true,
    showExternal = true,
    showImmich = true,
  }: Props = $props();

  const stackMembers = $derived(stackMembersForAsset(asset));
  const stackItems = $derived(buildAssetPreviewItems(stackMembers));
</script>

<div class="relation-indicators" aria-label="Asset relationships and actions">
  {#if showAlbums && asset.albums.length}
    <AssetRelationIndicator kind="album" label="Albums" count={asset.albums.length}>
      <ul class="name-list">
        {#each asset.albums as album (album.id)}
          <li>{album.name}</li>
        {/each}
      </ul>
    </AssetRelationIndicator>
  {/if}

  {#if showTags && asset.tags.length}
    <AssetRelationIndicator kind="tag" label="Tags" count={asset.tags.length}>
      <ul class="tag-list">
        {#each asset.tags as tag (tag.id)}
          <li><span aria-hidden="true"></span>{tag.name}</li>
        {/each}
      </ul>
    </AssetRelationIndicator>
  {/if}

  {#if showStack && asset.stack}
    <AssetRelationIndicator kind="stack" label="Stack images" count={asset.stack.asset_count}>
      <AssetPreviewStrip
        items={stackItems}
        selectedId={asset.id}
        visibleId={asset.id}
        source="stack"
        interactive={false}
        compact
      />
      {#if stackMembers.length < asset.stack.asset_count}
        <p>Run metadata sync to load every stack preview.</p>
      {/if}
    </AssetRelationIndicator>
  {/if}

  {#if showExternal && asset.source.kind === 'external'}
    <AssetRelationIndicator kind="external" label="External-library source">
      <dl>
        <div><dt>Source</dt><dd>External library</dd></div>
        {#if asset.source.library_id}<div><dt>Library</dt><dd title={asset.source.library_id}>{asset.source.library_id}</dd></div>{/if}
        {#if asset.source.original_path}<div><dt>Path</dt><dd title={asset.source.original_path}>{asset.source.original_path}</dd></div>{/if}
      </dl>
    </AssetRelationIndicator>
  {/if}

  {#if showImmich}
    {#if asset.immich_url}
      <a
        class="immich-link"
        href={asset.immich_url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Open ${asset.original_file_name} in Immich`}
        title="Open in Immich"
      >
        <AssetIcon kind="immich" />
        <span>Immich</span>
      </a>
    {:else}
      <span class="immich-link disabled" title="Configure IMMICH_PUBLIC_URL to open this asset in Immich">
        <AssetIcon kind="immich" />
        <span>Immich</span>
      </span>
    {/if}
  {/if}
</div>

<style>
  .relation-indicators {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
  }

  .name-list,
  .tag-list {
    display: grid;
    gap: 0.35rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .name-list li,
  .tag-list li {
    padding: 0.32rem 0.42rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: calc(var(--radius-sm) - 0.15rem);
    background: var(--color-surface-soft);
  }

  .tag-list li {
    display: flex;
    align-items: center;
    gap: 0.38rem;
  }

  .tag-list li span {
    width: 0.52rem;
    height: 0.52rem;
    border-radius: 50%;
    background: var(--color-accent-strong);
  }

  p {
    margin: 0.4rem 0 0;
    font-size: 0.62rem;
  }

  dl {
    display: grid;
    gap: 0.4rem;
    margin: 0;
  }

  dl div {
    display: grid;
    grid-template-columns: 3.5rem minmax(0, 1fr);
    gap: 0.45rem;
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

  .immich-link {
    display: inline-flex;
    min-height: 2rem;
    align-items: center;
    gap: 0.32rem;
    padding: 0.36rem 0.5rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
    font-size: 0.62rem;
    font-weight: 800;
    text-decoration: none;
  }

  .immich-link:hover,
  .immich-link:focus-visible {
    border-color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 8%, var(--color-surface-soft));
  }

  .immich-link.disabled {
    color: var(--color-ink-muted);
    cursor: not-allowed;
    opacity: 0.45;
  }
</style>
