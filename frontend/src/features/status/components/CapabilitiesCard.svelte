<script lang="ts">
  import SurfaceCard from '../../../lib/components/layout/SurfaceCard.svelte';
  import StatusBadge from '../../../lib/components/ui/StatusBadge.svelte';
  import { humanizeIdentifier } from '../state/statusViewModel';
  import type { CapabilitiesResponse } from '../types/status';

  interface Props {
    capabilities: CapabilitiesResponse;
  }

  let { capabilities }: Props = $props();
</script>

<SurfaceCard eyebrow="Scope" title="Available capabilities">
  <div class="capability-content">
    <StatusBadge
      label={capabilities.destructive_actions ? 'Destructive enabled' : 'Read-only baseline'}
      tone={capabilities.destructive_actions ? 'negative' : 'positive'}
    />
    <div>
      <h3>Implemented</h3>
      <ul>
        {#each capabilities.implemented as capability (capability)}
          <li>{humanizeIdentifier(capability)}</li>
        {/each}
      </ul>
    </div>
    <details>
      <summary>{capabilities.planned.length} planned capabilities</summary>
      <ul>
        {#each capabilities.planned as capability (capability)}
          <li>{humanizeIdentifier(capability)}</li>
        {/each}
      </ul>
    </details>
  </div>
</SurfaceCard>

<style>
  .capability-content {
    display: grid;
    justify-items: start;
    gap: 1rem;
  }

  h3 {
    margin: 0 0 0.5rem;
    color: var(--color-ink-strong);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }

  ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    padding: 0.25rem 0.5rem;
    border-radius: 0.35rem;
    color: var(--color-ink-strong);
    background: var(--color-surface-soft);
    font-size: 0.75rem;
  }

  details {
    width: 100%;
  }

  summary {
    color: var(--color-ink-muted);
    font-size: 0.78rem;
    font-weight: 750;
    cursor: pointer;
  }

  details ul {
    margin-top: 0.75rem;
  }
</style>
