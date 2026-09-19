<script lang="ts">
  import type { StatusLoadState } from '../../../lib/types/status';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import V2Zone from '../../../lib/components/layout/Zone.svelte';
  import { capabilityLabel } from '../utils/statusPresentation';

  let { state }: { state: StatusLoadState } = $props();
</script>

<V2Zone>
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
