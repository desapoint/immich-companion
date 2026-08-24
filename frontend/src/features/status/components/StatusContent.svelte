<script lang="ts">
  import CapabilitiesCard from './CapabilitiesCard.svelte';
  import DependencyStatusCard from './DependencyStatusCard.svelte';
  import EnvironmentBanner from './EnvironmentBanner.svelte';
  import HealthOverview from './HealthOverview.svelte';
  import VersionCard from './VersionCard.svelte';
  import type { StatusSnapshot } from '../types/status';

  interface Props {
    snapshot: StatusSnapshot;
  }

  let { snapshot }: Props = $props();
</script>

<div aria-live="polite">
  <EnvironmentBanner health={snapshot.health} />
  <section class="status-grid" aria-label="Companion service details">
    <HealthOverview health={snapshot.health} />
    <DependencyStatusCard dependency={snapshot.health.dependencies.immich} />
    <VersionCard version={snapshot.version} />
    <CapabilitiesCard capabilities={snapshot.capabilities} />
  </section>
</div>

<style>
  .status-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  @media (max-width: 44rem) {
    .status-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
