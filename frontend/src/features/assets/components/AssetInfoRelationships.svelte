<script lang="ts">
  import type { AssetSummary } from '../types/assets';
  import AssetStateChips from './AssetStateChips.svelte';
  import AssetTagChips from './AssetTagChips.svelte';

  interface Props {
    asset: AssetSummary;
  }

  let { asset }: Props = $props();
  const hasState = $derived(
    asset.is_favorite
      || asset.is_archived
      || asset.is_trashed
      || asset.is_offline
      || asset.is_edited
      || Boolean(asset.live_photo_video_id)
      || asset.people_count > 0,
  );
</script>

<section class="relationship-details" aria-labelledby="asset-relationships-title">
  <h3 id="asset-relationships-title">Relationships and state</h3>

  <dl>
    <div>
      <dt>Albums</dt>
      <dd>
        {#if asset.albums.length}
          <ul class="album-list">
            {#each asset.albums as album (album.id)}
              <li>{album.name}</li>
            {/each}
          </ul>
        {:else}
          <span class="empty-value">None</span>
        {/if}
      </dd>
    </div>

    <div>
      <dt>Tags</dt>
      <dd>
        {#if asset.tags.length}
          <AssetTagChips tags={asset.tags} maxVisible={asset.tags.length} />
        {:else}
          <span class="empty-value">None</span>
        {/if}
      </dd>
    </div>

    <div>
      <dt>Stack</dt>
      <dd>
        {#if asset.stack}
          <span>{asset.stack.asset_count} images</span>
          {#if asset.stack.primary_asset_id === asset.id}<small>Primary asset</small>{/if}
        {:else}
          <span class="empty-value">Not stacked</span>
        {/if}
      </dd>
    </div>

    <div>
      <dt>Source</dt>
      <dd>
        <span>{asset.source.kind === 'external' ? 'External library' : 'Immich upload'}</span>
        {#if asset.source.library_id}<small title={asset.source.library_id}>Library: {asset.source.library_id}</small>{/if}
        {#if asset.source.original_path}<small title={asset.source.original_path}>{asset.source.original_path}</small>{/if}
      </dd>
    </div>

    <div>
      <dt>People</dt>
      <dd>{asset.people_count || 'None detected'}</dd>
    </div>
  </dl>

  {#if hasState}
    <div class="state-summary">
      <strong>State</strong>
      <AssetStateChips {asset} />
    </div>
  {/if}
</section>

<style>
  .relationship-details {
    padding-block: 0.8rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  h3 {
    margin: 0 0 0.65rem;
    color: var(--color-accent-strong);
    font-size: 0.72rem;
  }

  dl {
    display: grid;
    gap: 0.55rem;
    margin: 0;
  }

  dl > div {
    display: grid;
    grid-template-columns: minmax(5rem, 0.38fr) minmax(0, 1fr);
    gap: 0.65rem;
    align-items: start;
  }

  dt,
  dd,
  small {
    font-size: 0.7rem;
  }

  dt,
  .empty-value {
    color: var(--color-ink-muted);
  }

  dd {
    display: grid;
    min-width: 0;
    gap: 0.3rem;
    margin: 0;
    overflow-wrap: anywhere;
  }

  small {
    min-width: 0;
    overflow: hidden;
    color: var(--color-ink-muted);
    font-family: var(--font-mono);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .album-list {
    display: flex;
    min-width: 0;
    flex-wrap: wrap;
    gap: 0.32rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .album-list li {
    max-width: 100%;
    padding: 0.24rem 0.42rem;
    overflow: hidden;
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    font-size: 0.62rem;
    font-weight: 720;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .state-summary {
    display: grid;
    gap: 0.45rem;
    margin-top: 0.7rem;
  }

  .state-summary > strong {
    color: var(--color-ink-muted);
    font-size: 0.7rem;
    font-weight: 600;
  }
</style>
