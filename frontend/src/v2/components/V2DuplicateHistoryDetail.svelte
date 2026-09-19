<script lang="ts">
  import { onMount } from 'svelte';

  import type { AssetRecord, TrashAssetRecord } from '../data/contracts';
  import { libraryData } from '../../app/data/currentDataSource.svelte';
  import {
    duplicateResolutionHistoryDetail,
    type DuplicateResolutionHistoryItem,
  } from '../../features/duplicates/api/duplicateResolutionHistory';
  import { errorMessage } from '../../lib/api/mutationFeedback';
  import V2Badge from '../../lib/components/ui/Badge.svelte';
  import V2Button from '../../lib/components/ui/Button.svelte';
  import V2LazyAssetMedia from './V2LazyAssetMedia.svelte';
  import V2Modal from '../../lib/components/ui/Modal.svelte';

  type HistoryAsset = {
    id: string;
    state: 'active' | 'trash' | 'missing' | 'error';
    asset: AssetRecord | TrashAssetRecord | null;
    error: string | null;
  };

  let {
    resolutionId,
    onclose,
  }: {
    resolutionId: string;
    onclose: () => void;
  } = $props();

  let detail = $state<DuplicateResolutionHistoryItem | null>(null);
  let assets = $state<HistoryAsset[]>([]);
  let loading = $state(true);
  let loadError = $state('');

  const sourceLabel = $derived(
    detail?.discovery_source === 'immich_duplicate' ? 'Immich duplicates' : 'Similarity engine',
  );

  function reviewLabel(value: DuplicateResolutionHistoryItem['review_status']): string {
    if (value === 'reviewed_keep_all') return 'Kept all';
    if (value === 'reviewed_stack_all') return 'Stacked all';
    if (value === 'reviewed_mixed') return 'Mixed resolution';
    return 'Resolved';
  }

  function actionLabel(value: string | null): string {
    if (!value) return 'No explicit action';
    return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  async function resolveAsset(id: string): Promise<HistoryAsset> {
    try {
      const trash = await libraryData.assets.getTrashById(id);
      if (trash) return { id, state: 'trash', asset: trash, error: null };
      const active = await libraryData.assets.getById(id);
      if (active) return { id, state: 'active', asset: active, error: null };
      return { id, state: 'missing', asset: null, error: null };
    } catch (error) {
      return {
        id,
        state: 'error',
        asset: null,
        error: errorMessage(error, 'Current asset state could not be loaded.'),
      };
    }
  }

  async function resolveAssets(ids: readonly string[]): Promise<HistoryAsset[]> {
    const resolved: HistoryAsset[] = [];
    for (let index = 0; index < ids.length; index += 8) {
      resolved.push(...await Promise.all(ids.slice(index, index + 8).map(resolveAsset)));
    }
    return resolved;
  }

  onMount(() => {
    let active = true;
    void (async () => {
      loading = true;
      loadError = '';
      try {
        const loaded = await duplicateResolutionHistoryDetail(resolutionId);
        const resolved = await resolveAssets(loaded.member_asset_ids);
        if (!active) return;
        detail = loaded;
        assets = resolved;
      } catch (error) {
        if (active) loadError = errorMessage(error, 'Resolution details could not be loaded.');
      } finally {
        if (active) loading = false;
      }
    })();
    return () => { active = false; };
  });
</script>

<V2Modal
  id={`duplicate-resolution-history-${resolutionId}`}
  title="Resolution details"
  description="Recorded Companion resolution and the current availability of its affected assets."
  size="xl"
  {onclose}
>
  {#if loading}
    <div class="v2-history-detail-state">Loading resolution details…</div>
  {:else if loadError}
    <div class="v2-history-detail-state" data-error="true">{loadError}</div>
  {:else if detail}
    <div class="v2-history-detail">
      <div class="v2-history-summary">
        <div class="v2-history-summary-badges">
          <V2Badge text={reviewLabel(detail.review_status)} />
          <V2Badge text={sourceLabel} />
          <V2Badge text={`${detail.member_count} affected ${detail.member_count === 1 ? 'asset' : 'assets'}`} />
        </div>
        <dl>
          <div><dt>Resolved</dt><dd>{new Date(detail.occurred_at).toLocaleString()}</dd></div>
          <div><dt>Action</dt><dd>{actionLabel(detail.manual_action)}</dd></div>
          <div><dt>Provider group</dt><dd><code>{detail.provider_group_id}</code></dd></div>
        </dl>
      </div>

      <div class="v2-history-assets" aria-label="Affected assets">
        {#each assets as item (item.id)}
          <article class="v2-history-asset" data-state={item.state}>
            <div class="v2-history-asset-preview">
              {#if item.asset}
                <V2LazyAssetMedia
                  cacheKey={`duplicate-history:${item.id}`}
                  resolve={() => libraryData.media.thumbnail(item.asset!)}
                  alt={item.asset.original_file_name}
                />
              {:else}
                <span class="v2-history-asset-missing">Preview unavailable</span>
              {/if}
              <span class="v2-history-asset-state">
                {#if item.state === 'trash'}
                  <V2Badge tone="bad" text="Trash" />
                {:else if item.state === 'active'}
                  <V2Badge tone="ok" text="Available" />
                {:else if item.state === 'error'}
                  <V2Badge tone="bad" text="Lookup failed" />
                {:else}
                  <V2Badge tone="warn" text="Unavailable" />
                {/if}
              </span>
            </div>
            <div class="v2-history-asset-copy">
              <b title={item.asset?.original_file_name ?? item.id}>{item.asset?.original_file_name ?? item.id}</b>
              <small>{item.id}</small>
              {#if item.state === 'trash'}<small>Currently in Immich trash</small>{/if}
              {#if item.state === 'missing'}<small>No longer available from active assets or trash</small>{/if}
              {#if item.state === 'error'}<small title={item.error ?? ''}>{item.error}</small>{/if}
            </div>
          </article>
        {/each}
      </div>
    </div>
  {/if}

  {#snippet footer()}
    <V2Button onclick={onclose}>Close</V2Button>
  {/snippet}
</V2Modal>

<style>
  .v2-history-detail{display:grid;gap:18px;min-width:0}
  .v2-history-detail-state{min-height:160px;display:grid;place-items:center;color:var(--v2-muted)}
  .v2-history-detail-state[data-error='true']{color:var(--v2-red)}
  .v2-history-summary{display:grid;gap:12px}
  .v2-history-summary-badges{display:flex;gap:8px;flex-wrap:wrap}
  dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0}
  dl div{min-width:0;padding:10px;border:1px solid var(--v2-border);border-radius:10px;background:var(--v2-surface-2)}
  dt{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--v2-muted)}
  dd{margin:5px 0 0;min-width:0;overflow-wrap:anywhere}
  code{font-size:11px}
  .v2-history-assets{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}
  .v2-history-asset{min-width:0;overflow:hidden;border:1px solid var(--v2-border);border-radius:12px;background:var(--v2-surface-2)}
  .v2-history-asset-preview{position:relative;aspect-ratio:4/3;overflow:hidden;background:#0d141d}
  .v2-history-asset-state{position:absolute;z-index:3;top:8px;right:8px;display:inline-flex;border:1px solid rgba(255,255,255,.2);border-radius:999px;background:rgba(5,10,16,.76);box-shadow:0 2px 8px rgba(0,0,0,.38);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
  .v2-history-asset-missing{position:absolute;inset:0;display:grid;place-items:center;padding:12px;color:var(--v2-muted);text-align:center}
  .v2-history-asset-copy{display:grid;gap:3px;padding:10px;min-width:0}
  .v2-history-asset-copy b,.v2-history-asset-copy small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-history-asset-copy small{color:var(--v2-muted);font-size:11px}
  @media(max-width:760px){dl{grid-template-columns:1fr}}
</style>
