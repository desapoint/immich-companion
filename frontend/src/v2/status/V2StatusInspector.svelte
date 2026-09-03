<script lang="ts">
  import type { StatusLoadState } from '../../features/status/types/status';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { capabilityLabel } from './statusPresentation';

  let { state }: { state: StatusLoadState } = $props();
</script>

<V2Zone label="Inspector">
  {#if state.kind === 'loaded'}
    <V2Section title="Capabilities">
      <V2Card>
        <V2Stack gap="sm">
          {#each state.snapshot.capabilities.implemented as capability}
            <span class="v2-small">{capabilityLabel(capability)}</span>
          {:else}
            <span class="v2-small v2-muted">No implemented capabilities reported.</span>
          {/each}
        </V2Stack>
      </V2Card>
    </V2Section>

    <V2Card>
      <V2Inline justify="between">
        <span class="v2-small">Destructive actions</span>
        <V2Badge
          tone={state.snapshot.capabilities.destructive_actions ? 'warn' : 'ok'}
          text={state.snapshot.capabilities.destructive_actions ? 'Enabled' : 'Disabled'}
        />
      </V2Inline>
    </V2Card>
  {:else}
    <V2Card>
      <div class="v2-small v2-muted">{state.kind === 'loading' ? 'Loading capabilities…' : 'No live capability data available.'}</div>
    </V2Card>
  {/if}
</V2Zone>
