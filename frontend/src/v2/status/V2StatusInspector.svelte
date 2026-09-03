<script lang="ts">
  import type { StatusLoadState } from '../../features/status/types/status';
  import V2Card from '../components/V2Card.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { capabilityLabel } from './statusPresentation';

  let { state }: { state: StatusLoadState } = $props();
</script>

<V2Zone label="Inspector">
  <V2Section title="Capabilities">
    <V2Card>
      <V2Stack gap="sm">
        {#if state.kind === 'loaded'}
          {#each state.snapshot.capabilities.implemented as capability}
            <span class="v2-small">{capabilityLabel(capability)}</span>
          {:else}
            <span class="v2-small v2-muted">No implemented capabilities reported.</span>
          {/each}
        {:else}
          <span class="v2-small v2-muted">{state.kind === 'loading' ? 'Loading capabilities…' : 'No live capability data available.'}</span>
        {/if}
      </V2Stack>
    </V2Card>
  </V2Section>
</V2Zone>
