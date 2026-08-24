<script lang="ts">
  import SurfaceCard from '../../../lib/components/layout/SurfaceCard.svelte';
  import StatusBadge from '../../../lib/components/ui/StatusBadge.svelte';
  import {
    dependencyLabel,
    dependencyTone,
    formatLatency,
  } from '../state/statusViewModel';
  import type { DependencyStatus } from '../types/status';

  interface Props {
    dependency: DependencyStatus;
  }

  let { dependency }: Props = $props();
  const label = $derived(dependencyLabel(dependency));
  const tone = $derived(dependencyTone(dependency));
</script>

<SurfaceCard eyebrow="Dependency" title="Immich API">
  <div class="dependency-content">
    <StatusBadge {label} {tone} />
    <dl>
      <div>
        <dt>Configured</dt>
        <dd>{dependency.configured ? 'Yes' : 'No'}</dd>
      </div>
      <div>
        <dt>Latency</dt>
        <dd>{formatLatency(dependency.latency_ms)}</dd>
      </div>
    </dl>
    {#if dependency.detail}
      <p>{dependency.detail}</p>
    {/if}
  </div>
</SurfaceCard>

<style>
  .dependency-content {
    display: grid;
    justify-items: start;
    gap: 1rem;
  }

  dl {
    width: 100%;
    margin: 0;
  }

  dl div {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.45rem 0;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  dt {
    color: var(--color-ink-muted);
  }

  dd {
    margin: 0;
    color: var(--color-ink-strong);
    font-weight: 700;
  }

  p {
    margin: 0;
    font-size: 0.82rem;
    line-height: 1.5;
  }
</style>
