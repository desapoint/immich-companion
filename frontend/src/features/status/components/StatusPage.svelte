<script lang="ts">
  import { onMount } from 'svelte';

  import { loadStatus } from '../../../lib/api/status';
  import type { StatusLoadState } from '../../../lib/types/status';
  import V2PageLayout from '../../../lib/components/layout/PageLayout.svelte';
  import StatusContent from './StatusContent.svelte';
  import StatusContext from './StatusContext.svelte';
  import StatusInspector from './StatusInspector.svelte';

  let loadState = $state.raw<StatusLoadState>({ kind: 'loading' });
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

<V2PageLayout
  title="Status"
  description="Read-only health, dependency, capability and version overview for Companion and its Immich connection."
>
  {#snippet context()}
    <StatusContext state={loadState} />
  {/snippet}

  <StatusContent state={loadState} onrefresh={refresh} />

  {#snippet inspector()}
    <StatusInspector state={loadState} />
  {/snippet}
</V2PageLayout>
