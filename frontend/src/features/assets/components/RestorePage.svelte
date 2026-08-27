<script lang="ts">
  import { onMount } from 'svelte';
  import type { AssetSummary } from '../types/assets';

  let items = $state<AssetSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let restoring = $state<string | null>(null);

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
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not restore the asset.';
    } finally {
      restoring = null;
    }
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
    <div class="grid">
      {#each items as asset (asset.id)}
        <article>
          <img src={`/api/assets/${asset.id}/thumbnail`} alt="" loading="lazy" />
          <div><strong>{asset.original_file_name}</strong><small>{asset.source.original_path ?? 'Path unavailable'}</small></div>
          <button type="button" disabled={restoring !== null} onclick={() => void restore(asset)}>{restoring === asset.id ? 'Restoring…' : 'Restore'}</button>
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .restore-page { display: grid; gap: 1.5rem; }
  header { max-width: 48rem; } .eyebrow { color: var(--color-accent-strong); font-size: .7rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
  h1 { margin: .25rem 0; font-size: clamp(2rem, 5vw, 3.5rem); } p, small { color: var(--color-ink-muted); } .error { color: var(--color-danger); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr)); gap: 1rem; } article { display: grid; gap: .65rem; padding: .7rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); } img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: var(--radius-sm); background: var(--color-surface-soft); } small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } button { justify-self: start; padding: .45rem .7rem; border: 1px solid var(--color-accent-strong); border-radius: var(--radius-sm); color: var(--color-ink-inverse); background: var(--color-accent-strong); font: inherit; font-size: .8rem; font-weight: 700; cursor: pointer; } button:disabled { opacity: .65; cursor: wait; }
</style>
