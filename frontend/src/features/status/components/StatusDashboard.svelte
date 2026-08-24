<script lang="ts">
  import { onMount } from 'svelte';

  import { loadStatus } from '../api/statusApi';
  import type { StatusLoadState } from '../types/status';
  import DashboardIntro from './DashboardIntro.svelte';
  import StatusContent from './StatusContent.svelte';
  import StatusError from './StatusError.svelte';
  import StatusLoading from './StatusLoading.svelte';

  let loadState = $state<StatusLoadState>({ kind: 'loading' });
  let active = true;

  async function refresh(): Promise<void> {
    loadState = { kind: 'loading' };

    try {
      const snapshot = await loadStatus();
      if (active) loadState = { kind: 'loaded', snapshot };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'An unknown status error occurred.';
      if (active) loadState = { kind: 'error', message };
    }
  }

  onMount(() => {
    active = true;
    void refresh();

    return () => {
      active = false;
    };
  });
</script>

<DashboardIntro />

{#if loadState.kind === 'loading'}
  <StatusLoading />
{:else if loadState.kind === 'error'}
  <StatusError message={loadState.message} onretry={refresh} />
{:else}
  <StatusContent snapshot={loadState.snapshot} />
{/if}
