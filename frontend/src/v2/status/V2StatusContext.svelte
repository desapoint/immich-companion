<script lang="ts">
  import type { StatusLoadState } from '../../features/status/types/status';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import { companionState, dependencyState } from './statusPresentation';

  let { state }: { state: StatusLoadState } = $props();
</script>

<span class="v2-zone">Context rail</span>

{#if state.kind === 'loaded'}
  {@const snapshot = state.snapshot}
  {@const companion = companionState(snapshot)}
  {@const immich = dependencyState(snapshot.health.dependencies.immich, 'Connected')}
  {@const database = dependencyState(snapshot.health.dependencies.companion_database, 'Ready')}

  <V2Section title="Environment">
    <V2Card>
      <V2Stack gap="sm">
        <V2Inline justify="between"><span>Companion</span><V2Badge tone={companion.tone} text={companion.label} /></V2Inline>
        <V2Inline justify="between"><span>Immich API</span><V2Badge tone={immich.tone} text={immich.label} /></V2Inline>
        <V2Inline justify="between"><span>Database</span><V2Badge tone={database.tone} text={database.label} /></V2Inline>
      </V2Stack>
    </V2Card>
  </V2Section>

  <V2Card>
    <div class="v2-small v2-muted">Environment: {snapshot.version.environment}<br>Safe mode: {snapshot.health.safe_mode ? 'On' : 'Off'}</div>
  </V2Card>
{:else}
  <V2Card>
    <div class="v2-small v2-muted">{state.kind === 'loading' ? 'Loading environment status…' : 'Live status unavailable.'}</div>
  </V2Card>
{/if}
