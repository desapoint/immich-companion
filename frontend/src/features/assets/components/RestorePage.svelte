<script lang="ts">
  import { onMount } from 'svelte';
  import { getRestoreAssetDetail } from '../api/assetApi';
  import AssetViewerDialog from './AssetViewerDialog.svelte';
  import type { AssetDetail, AssetSummary } from '../types/assets';

  let items = $state<AssetSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let restoring = $state<string | null>(null);
  let selectedIds = $state<Set<string>>(new Set());
  let viewerIndex = $state<number | null>(null);
  let detail = $state<AssetDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);

  onMount(async () => {
    try {
      const response = await fetch('/api/restore');
      if (!response.ok) throw new Error(`Could not load Restore (${response.status}).`);
      const payload = (await response.json()) as { items: AssetSummary[] };
      items = payload.items;
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not load Restore.';
    } finally {
      loading = false;
    }
  });

  async function restore(asset: AssetSummary): Promise<void> {
    restoring = asset.id;
    error = null;
    try {
      const response = await fetch(`/api/restore/${asset.id}`, { method: 'POST' });
      if (!response.ok) throw new Error(`Could not restore ${asset.original_file_name} (${response.status}).`);
      items = items.filter((item) => item.id !== asset.id);
      selectedIds.delete(asset.id);
      selectedIds = new Set(selectedIds);
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not restore the asset.';
    } finally {
      restoring = null;
    }
  }

  function toggleSelection(assetId: string): void {
    const next = new Set(selectedIds);
    if (next.has(assetId)) next.delete(assetId);
    else next.add(assetId);
    selectedIds = next;
  }

  async function restoreMany(all: boolean): Promise<void> {
    const targets = all ? items : items.filter((item) => selectedIds.has(item.id));
    if (targets.length === 0) return;
    restoring = all ? 'all' : 'selected';
    error = null;
    try {
      const response = await fetch('/api/restore', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(all ? { all: true } : { ids: targets.map((asset) => asset.id) }),
      });
      if (!response.ok) throw new Error(`Could not restore ${targets.length} assets (${response.status}).`);
      const restored = new Set(targets.map((asset) => asset.id));
      items = items.filter((asset) => !restored.has(asset.id));
      selectedIds = new Set();
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not restore the selected assets.';
    } finally {
      restoring = null;
    }
  }

  async function openViewer(index: number): Promise<void> {
    const asset = items[index];
    if (!asset) return;
    viewerIndex = index;
    detail = null;
    detailError = null;
    detailLoading = true;
    try {
      detail = await getRestoreAssetDetail(asset.id);
    } catch (reason) {
      detailError = reason instanceof Error ? reason.message : 'Could not load asset details.';
    } finally {
      detailLoading = false;
    }
  }

  function closeViewer(): void {
    viewerIndex = null;
    detail = null;
    detailError = null;
  }
</script>

<section class="restore-page" aria-labelledby="restore-title">
  <header>
    <p class="eyebrow">Recovery area</p>
    <h1 id="restore-title">Restore</h1>
    <p>Trashed assets are kept as lightweight records with a thumbnail and path. Restoring returns an item to the normal workspace and refreshes its details.</p>
  </header>
  {#if loading}
    <p>Loading trashed assets…</p>
  {:else if error}
    <p class="error" role="alert">{error}</p>
  {:else if items.length === 0}
    <p>No trashed assets are currently synchronized.</p>
  {:else}
    <div class="bulk-actions">
      <label><input type="checkbox" checked={items.length > 0 && selectedIds.size === items.length} onchange={() => selectedIds = selectedIds.size === items.length ? new Set() : new Set(items.map((asset) => asset.id))} /> Select all loaded</label>
      <button type="button" disabled={restoring !== null || selectedIds.size === 0} onclick={() => void restoreMany(false)}>{restoring === 'selected' ? 'Restoring selected…' : `Restore selected (${selectedIds.size})`}</button>
      <button type="button" disabled={restoring !== null} onclick={() => void restoreMany(true)}>{restoring === 'all' ? 'Restoring all…' : `Restore all (${items.length})`}</button>
    </div>
    <div class="grid">
      {#each items as asset, index (asset.id)}
        <article>
          <label class="select"><input type="checkbox" checked={selectedIds.has(asset.id)} onchange={() => toggleSelection(asset.id)} /><span>Select {asset.original_file_name}</span></label>
          <button class="preview" type="button" onclick={() => void openViewer(index)} aria-label={`Preview ${asset.original_file_name}`}><img src={`/api/assets/${asset.id}/thumbnail`} alt="" loading="lazy" /></button>
          <div><strong>{asset.original_file_name}</strong><small>{asset.restore_path ?? 'Path unavailable'}</small></div>
          <button type="button" disabled={restoring !== null} onclick={() => void restore(asset)}>{restoring === asset.id ? 'Restoring…' : 'Restore'}</button>
        </article>
      {/each}
    </div>
  {/if}
</section>

{#if viewerIndex !== null && items[viewerIndex]}
  <AssetViewerDialog
    assets={items}
    initialIndex={viewerIndex}
    selectedIds={new Set()}
    {detail}
    {detailLoading}
    {detailError}
    albums={[]}
    tags={[]}
    actionPlan={null}
    actionSummary={null}
    actionsEnabled={false}
    onnavigate={(index) => void openViewer(index)}
    ontoggleselection={() => {}}
    onvisiblechange={(assetId) => { const index = items.findIndex((asset) => asset.id === assetId); if (index >= 0) void openViewer(index); }}
    onaction={() => {}}
    onrelationconfirm={() => {}}
    onconfirmaction={() => {}}
    oncancelaction={() => {}}
    onsync={() => {}}
    onclose={closeViewer}
  />
{/if}

<style>
  .restore-page { display: grid; gap: 1.5rem; }
  header { max-width: 48rem; } .eyebrow { color: var(--color-accent-strong); font-size: .7rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
  h1 { margin: .25rem 0; font-size: clamp(2rem, 5vw, 3.5rem); } p, small { color: var(--color-ink-muted); } .error { color: var(--color-danger); }
  .bulk-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .7rem; } .bulk-actions label, .select { color: var(--color-ink-muted); font-size: .8rem; font-weight: 700; } .select span { position: absolute; inline-size: 1px; block-size: 1px; overflow: hidden; clip: rect(0 0 0 0); } .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr)); gap: 1rem; } article { display: grid; gap: .65rem; padding: .7rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); } img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: var(--radius-sm); background: var(--color-surface-soft); } small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } button { justify-self: start; padding: .45rem .7rem; border: 1px solid var(--color-accent-strong); border-radius: var(--radius-sm); color: var(--color-ink-inverse); background: var(--color-accent-strong); font: inherit; font-size: .8rem; font-weight: 700; cursor: pointer; } button.preview { display: block; width: 100%; padding: 0; border: 0; background: none; } button:disabled { opacity: .65; cursor: wait; }
</style>
