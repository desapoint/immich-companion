<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '../../lib/components/ui/LoadingSpinner.svelte';
  import {
    immichDuplicateSyncRepository,
    type ImmichDuplicateSyncStatus,
  } from '../data/api/immichDuplicateSyncRepository';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Notice from './V2Notice.svelte';
  import V2Stack from './V2Stack.svelte';

  let status = $state<ImmichDuplicateSyncStatus | null>(null);
  let loading = $state(true);
  let starting = $state(false);
  let error = $state<string | null>(null);
  let active = true;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const busy = $derived(Boolean(status && ['queued', 'running', 'retrying', 'recovering', 'pause_requested', 'cancel_requested'].includes(status.state)));

  function formatDate(value: string | null): string {
    return value ? new Date(value).toLocaleString() : 'Never';
  }

  function badge(): { text: string; tone: 'default' | 'ok' | 'warn' | 'bad' } {
    if (!status || status.state === 'never_synced') return { text: 'Not synchronized', tone: 'warn' };
    if (status.state === 'failed') return { text: 'Last refresh failed', tone: 'bad' };
    if (busy) return { text: 'Synchronizing', tone: 'default' };
    return { text: 'Up to date', tone: 'ok' };
  }

  function message(value: unknown, fallback: string): string {
    return value instanceof Error ? value.message : fallback;
  }

  function scheduleRefresh(delay = 1000): void {
    if (!active) return;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      void refresh(false);
    }, delay);
  }

  async function refresh(showLoading = true): Promise<void> {
    if (showLoading) loading = true;
    error = null;
    try {
      status = await immichDuplicateSyncRepository.status();
      if (status && ['queued', 'running', 'retrying', 'recovering', 'pause_requested', 'cancel_requested'].includes(status.state)) {
        scheduleRefresh();
      }
    } catch (value) {
      if (active) error = message(value, 'Could not load Immich duplicate synchronization status.');
    } finally {
      if (active && showLoading) loading = false;
    }
  }

  async function start(): Promise<void> {
    if (starting || busy) return;
    starting = true;
    error = null;
    try {
      await immichDuplicateSyncRepository.start();
      await refresh(false);
      scheduleRefresh(500);
    } catch (value) {
      if (active) error = message(value, 'Could not start Immich duplicate synchronization.');
    } finally {
      if (active) starting = false;
    }
  }

  onMount(() => {
    active = true;
    void refresh();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  });
</script>

<V2Card title="Immich duplicate index">
  {#snippet actions()}
    {@const stateBadge = badge()}
    <V2Badge tone={stateBadge.tone} text={stateBadge.text} />
  {/snippet}
  <V2Stack gap="sm">
    <span class="v2-small v2-muted">Immich-reported duplicate groups are synchronized into Companion's database. Opening or paging the duplicate review does not refresh Immich.</span>

    {#if loading && !status}
      <span class="duplicate-sync-pending"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Loading duplicate index status…</span>
    {:else}
      <div class="duplicate-sync-summary">
        <div><span>Groups</span><strong>{status?.groupCount.toLocaleString() ?? '—'}</strong></div>
        <div><span>Members</span><strong>{status?.memberCount.toLocaleString() ?? '—'}</strong></div>
        <div><span>Generation</span><strong>{status?.authoritativeGeneration ? `#${status.authoritativeGeneration}` : '—'}</strong></div>
        <div><span>Last synchronized</span><strong>{formatDate(status?.lastSuccessAt ?? null)}</strong></div>
      </div>
    {/if}

    {#if status?.state === 'never_synced'}
      <V2Notice tone="info" title="No Immich duplicate snapshot yet">Run a global or incremental asset sync, or refresh manually. The first successful duplicate sync publishes the local index.</V2Notice>
    {/if}
    {#if status?.state === 'failed'}
      <V2Notice tone="error" title="The latest duplicate refresh failed">{status.error ?? 'The previous successful snapshot remains available.'}</V2Notice>
    {/if}
    {#if error}<V2Notice tone="error">{error}</V2Notice>{/if}

    <div class="duplicate-sync-actions">
      <V2Button variant="primary" disabled={starting || busy} onclick={() => void start()}>
        {#if starting}<span class="duplicate-sync-pending"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Starting…</span>{:else if busy}Synchronizing…{:else}Refresh Immich duplicates{/if}
      </V2Button>
      <V2Button disabled={starting || loading} onclick={() => void refresh()}>Refresh status</V2Button>
    </div>
    <span class="v2-small v2-muted">Successful full and incremental asset syncs also queue this refresh automatically. Routine automatic refreshes are coalesced and skip a new snapshot when the last success is less than five minutes old.</span>
  </V2Stack>
</V2Card>

<style>
  .duplicate-sync-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
  .duplicate-sync-summary>div{display:flex;flex-direction:column;gap:3px;padding:10px;border:1px solid var(--v2-border);border-radius:8px}
  .duplicate-sync-summary span{font-size:.78rem;color:var(--v2-muted)}
  .duplicate-sync-actions,.duplicate-sync-pending{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
</style>
