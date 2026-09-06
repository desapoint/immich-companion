<script lang="ts">
  import { onMount } from 'svelte';

  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import CollectionFeedback from '../../../lib/components/ui/CollectionFeedback.svelte';
  import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import LayoutModeSwitch from '../../../lib/components/ui/LayoutModeSwitch.svelte';
  import Pagination from '../../../lib/components/ui/Pagination.svelte';
  import StatusNotice from '../../../lib/components/ui/StatusNotice.svelte';
  import {
    createCollectionController,
    createCollectionState,
  } from '../../../lib/state/collectionState';
  import {
    assetMediaUrl,
    getRestoreAssetDetail,
    getRestoreAssets,
    restoreAsset,
    restoreAssets,
  } from '../api/assetApi';
  import type { AssetDetail, AssetSummary } from '../types/assets';
  import AssetViewerDialog from './AssetViewerDialog.svelte';

  type Notice = { tone: 'success' | 'warning' | 'error'; message: string };

  const pageSize = 48;
  let collection = $state(createCollectionState<AssetSummary>(pageSize));
  let notice = $state<Notice | null>(null);
  let restoring = $state<string | null>(null);
  let selectedIds = $state<Set<string>>(new Set());
  let viewerIndex = $state<number | null>(null);
  let detail = $state<AssetDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let layoutMode = $state<'normal' | 'condensed'>('normal');
  let detailController: AbortController | null = null;

  const loadedSelectionCount = $derived(
    collection.items.reduce((count, asset) => count + Number(selectedIds.has(asset.id)), 0),
  );
  const allLoadedSelected = $derived(
    collection.items.length > 0 && loadedSelectionCount === collection.items.length,
  );

  const collectionController = createCollectionController(
    collection,
    async ({ page, pageSize: requestedPageSize, signal }) => {
      const payload = await getRestoreAssets(page, requestedPageSize, signal);
      return {
        items: payload.items,
        page: payload.page,
        pageSize: payload.page_size,
        pages: payload.pages,
        total: payload.total,
      };
    },
    { fallbackError: 'Could not load Restore.', getKey: (asset) => asset.id },
  );

  onMount(() => {
    void collectionController.load();
    return () => {
      collectionController.dispose();
      detailController?.abort();
    };
  });

  function reconcileRestoredIds(ids: string[], restoredCount = ids.length): void {
    const restoredIds = new Set(ids);
    collection.items = collection.items.filter((asset) => !restoredIds.has(asset.id));
    collection.total = Math.max(0, collection.total - restoredCount);
    collection.pages = collection.total === 0 ? 0 : Math.ceil(collection.total / collection.pageSize);
    collection.page = collection.pages === 0 ? 1 : Math.min(collection.page, collection.pages);
  }

  function reconcileRestoredAll(): void {
    collection.items = [];
    collection.total = 0;
    collection.pages = 0;
    collection.page = 1;
  }

  async function restoreOne(asset: AssetSummary): Promise<void> {
    if (restoring !== null) return;
    restoring = asset.id;
    notice = null;
    try {
      await restoreAsset(asset.id);
      reconcileRestoredIds([asset.id], 1);
      const next = new Set(selectedIds);
      next.delete(asset.id);
      selectedIds = next;
      closeViewer();
      notice = { tone: 'success', message: `Restored ${asset.original_file_name}.` };
      await collectionController.reload();
    } catch (reason) {
      notice = {
        tone: 'error',
        message: reason instanceof Error ? reason.message : 'Could not restore the asset.',
      };
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
    const ids = [...selectedIds];
    if (restoring !== null || (!all && ids.length === 0)) return;
    restoring = all ? 'all' : 'selected';
    notice = null;
    try {
      const result = await restoreAssets(all ? { all: true } : { ids });
      if (all) reconcileRestoredAll();
      else reconcileRestoredIds(ids, result.restored);
      selectedIds = new Set();
      closeViewer();
      notice = {
        tone: 'success',
        message: `${result.restored} asset${result.restored === 1 ? '' : 's'} restored.`,
      };
      await collectionController.reload();
    } catch (reason) {
      notice = {
        tone: 'error',
        message: reason instanceof Error
          ? reason.message
          : all ? 'Could not restore the trash.' : 'Could not restore the selected assets.',
      };
    } finally {
      restoring = null;
    }
  }

  async function openViewer(index: number): Promise<void> {
    const asset = collection.items[index];
    if (!asset) return;
    viewerIndex = index;
    detail = null;
    detailError = null;
    detailLoading = true;
    detailController?.abort();
    const controller = new AbortController();
    detailController = controller;
    try {
      const loaded = await getRestoreAssetDetail(asset.id, controller.signal);
      if (!controller.signal.aborted) detail = loaded;
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return;
      if (!controller.signal.aborted) {
        detailError = reason instanceof Error ? reason.message : 'Could not load asset details.';
      }
    } finally {
      if (!controller.signal.aborted) detailLoading = false;
    }
  }

  function closeViewer(): void {
    viewerIndex = null;
    detailController?.abort();
    detailController = null;
    detail = null;
    detailError = null;
    detailLoading = false;
  }

  function changePage(nextPage: number): void {
    closeViewer();
    void collectionController.changePage(nextPage);
  }

  function toggleLoadedSelection(): void {
    const next = new Set(selectedIds);
    for (const asset of collection.items) {
      if (allLoadedSelected) next.delete(asset.id);
      else next.add(asset.id);
    }
    selectedIds = next;
  }
</script>

<section class="restore-page" aria-labelledby="restore-title">
  <header>
    <p class="eyebrow">Recovery area</p>
    <h1 id="restore-title">Restore</h1>
    <p>Restore reads the current trash directly from Immich. Restoring returns an item to the normal workspace and refreshes the companion index from Immich.</p>
  </header>

  {#if notice}
    <StatusNotice tone={notice.tone} message={notice.message} ondismiss={() => (notice = null)} />
  {/if}

  <CollectionFeedback
    hasLoaded={collection.hasLoaded}
    initialLoading={collection.initialLoading}
    refreshing={collection.refreshing}
    error={collection.error}
    empty={collection.hasLoaded && collection.items.length === 0}
    loadingLabel="Loading trashed assets…"
    refreshingLabel="Refreshing trashed assets…"
    emptyLabel="Immich's trash is empty."
    onretry={() => void collectionController.reload()}
  />

  {#if collection.hasLoaded && collection.items.length > 0}
    <div class="bulk-actions">
      <Checkbox checked={allLoadedSelected} label="Select all on this page" onchange={toggleLoadedSelection} />
      <button type="button" disabled={restoring !== null || selectedIds.size === 0} onclick={() => void restoreMany(false)}>
        {restoring === 'selected' ? 'Restoring selected…' : `Restore selected (${selectedIds.size})`}
      </button>
      <button type="button" disabled={restoring !== null} onclick={() => void restoreMany(true)}>
        {restoring === 'all' ? 'Restoring all…' : `Restore all (${collection.total})`}
      </button>
      <div class="layout-toggle"><LayoutModeSwitch mode={layoutMode} onchange={(mode) => (layoutMode = mode)} /></div>
    </div>

    <div class:condensed={layoutMode === 'condensed'} class="grid">
      {#each collection.items as asset, index (asset.id)}
        <article class:selected={selectedIds.has(asset.id)}>
          <div class:overlay={layoutMode === 'condensed'} class="image-wrap">
            <div class="select">
              <Checkbox checked={selectedIds.has(asset.id)} label={`Select ${asset.original_file_name}`} hiddenLabel shape="circle" onchange={() => toggleSelection(asset.id)} />
            </div>
            <button class="preview" type="button" onclick={() => void openViewer(index)} aria-label={`Preview ${asset.original_file_name}`}>
              <img src={assetMediaUrl(asset.id, 'thumbnail')} alt="" loading="lazy" />
            </button>
            {#if layoutMode === 'condensed'}
              <div class="overlay-actions" aria-label={`Actions for ${asset.original_file_name}`}>
                <IconButton icon="view" label={`Preview ${asset.original_file_name}`} size="compact" onclick={() => void openViewer(index)} />
                <IconButton icon="restore" label={`${restoring === asset.id ? 'Restoring' : 'Restore'} ${asset.original_file_name}`} size="compact" tone="accent" disabled={restoring !== null} onclick={() => void restoreOne(asset)} />
              </div>
            {/if}
          </div>
          {#if layoutMode === 'normal'}
            <div>
              <strong>{asset.original_file_name}</strong>
              <small>{asset.restore_path ?? 'Path unavailable'}</small>
            </div>
            <button type="button" disabled={restoring !== null} onclick={() => void restoreOne(asset)}>
              {restoring === asset.id ? 'Restoring…' : 'Restore'}
            </button>
          {/if}
        </article>
      {/each}
    </div>

    <Pagination
      currentPage={collection.page}
      totalPages={collection.pages}
      totalItems={collection.total}
      pageSize={collection.pageSize}
      allowPageSizeChange={false}
      hideWhenSinglePage
      disabled={collection.refreshing || restoring !== null}
      label="Restore pages"
      onpagechange={changePage}
    />
  {/if}
</section>

{#if viewerIndex !== null && collection.items[viewerIndex]}
  <AssetViewerDialog
    assets={collection.items}
    initialIndex={viewerIndex}
    {selectedIds}
    {detail}
    {detailLoading}
    {detailError}
    albums={[]}
    tags={[]}
    actionPlan={null}
    actionSummary={null}
    actionsEnabled={false}
    selectionEnabled={true}
    restoreBusy={restoring !== null}
    apiOnly={true}
    onnavigate={(index) => void openViewer(index)}
    ontoggleselection={toggleSelection}
    onvisiblechange={(assetId) => {
      const index = collection.items.findIndex((asset) => asset.id === assetId);
      if (index >= 0) void openViewer(index);
    }}
    onaction={() => {}}
    onrelationconfirm={() => {}}
    onconfirmaction={() => {}}
    oncancelaction={() => {}}
    onrestore={(assetId) => {
      const asset = collection.items.find((candidate) => candidate.id === assetId);
      if (asset) void restoreOne(asset);
    }}
    onsync={() => {}}
    onclose={closeViewer}
  />
{/if}

<style>
  .restore-page {
    display: grid;
    gap: 1.5rem;
  }

  header {
    max-width: 48rem;
  }

  .eyebrow {
    color: var(--color-accent-strong);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  h1 {
    margin: 0.25rem 0;
    font-size: clamp(2rem, 5vw, 3.5rem);
  }

  p,
  small {
    color: var(--color-ink-muted);
  }

  .bulk-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.7rem;
  }

  .layout-toggle {
    margin-inline-start: auto;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
    gap: 1rem;
  }

  article {
    display: grid;
    min-width: 0;
    gap: 0.65rem;
    padding: 0.7rem;
    overflow: hidden;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
  }

  article.selected {
    border-color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 7%, var(--color-surface-raised));
    box-shadow: 0 0 0 0.18rem color-mix(in srgb, var(--color-accent-strong) 72%, transparent);
  }

  .image-wrap {
    display: grid;
    min-width: 0;
    gap: 0.55rem;
  }

  .image-wrap.overlay {
    position: relative;
  }

  article.selected .image-wrap.overlay::after {
    position: absolute;
    z-index: 0;
    inset: 0;
    border: 0.18rem solid var(--color-accent-strong);
    border-radius: var(--radius-sm);
    content: '';
    pointer-events: none;
  }

  img {
    display: block;
    width: 100%;
    max-width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    border-radius: var(--radius-sm);
    background: var(--color-surface-soft);
  }

  .image-wrap.overlay > .select {
    position: absolute;
    z-index: 1;
    top: 0.5rem;
    left: 0.5rem;
  }

  article > div:not(.image-wrap) {
    min-width: 0;
  }

  strong {
    display: -webkit-box;
    overflow: hidden;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow-wrap: anywhere;
  }

  small {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  button {
    max-width: 100%;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--color-accent-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
    cursor: pointer;
    font: inherit;
    font-size: 0.8rem;
    font-weight: 700;
    justify-self: start;
  }

  button.preview {
    display: block;
    width: 100%;
    padding: 0;
    border: 0;
    background: none;
  }

  .overlay-actions {
    position: absolute;
    z-index: 1;
    right: 0.5rem;
    bottom: 0.5rem;
    display: flex;
    gap: 0.3rem;
    padding: 0.25rem;
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--color-surface-raised) 86%, transparent);
  }

  .overlay-actions :global(.icon-button-wrap button) {
    border-color: color-mix(in srgb, var(--color-ink-inverse) 70%, transparent);
    box-shadow: 0 1px 4px rgb(0 0 0 / 25%);
  }

  .condensed {
    grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
    gap: 0.65rem;
  }

  .condensed article {
    padding: 0.35rem;
  }

  .condensed .image-wrap,
  .condensed img {
    border-radius: var(--radius-sm);
  }

  button:disabled {
    cursor: wait;
    opacity: 0.65;
  }
</style>
