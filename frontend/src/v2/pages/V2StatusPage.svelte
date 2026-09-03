<script lang="ts">
  import { onMount } from 'svelte';

  import { loadStatus } from '../../features/status/api/statusApi';
  import type { StatusLoadState } from '../../features/status/types/status';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2StatusContent from '../status/V2StatusContent.svelte';
  import V2StatusContext from '../status/V2StatusContext.svelte';
  import V2StatusInspector from '../status/V2StatusInspector.svelte';

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

<V2PageLayout
  title="Status"
  description="Read-only health, dependency, capability and version overview for Companion and its Immich connection."
>
  {#snippet context()}
    <V2StatusContext state={loadState} />
  {/snippet}

  <V2StatusContent state={loadState} onrefresh={refresh} />

  {#snippet inspector()}
    <V2StatusInspector state={loadState} />
  {/snippet}
</V2PageLayout>
