<script lang="ts">
  import SurfaceCard from '../../../lib/components/layout/SurfaceCard.svelte';
  import StatusBadge from '../../../lib/components/ui/StatusBadge.svelte';
  import { healthLabel, healthTone } from '../state/statusViewModel';
  import type { HealthResponse } from '../types/status';

  interface Props {
    health: HealthResponse;
  }

  let { health }: Props = $props();
  const label = $derived(healthLabel(health));
  const tone = $derived(healthTone(health));
</script>

<SurfaceCard eyebrow="Backend" title="Companion service">
  <div class="status-line">
    <StatusBadge {label} {tone} />
    <span>{health.ready ? 'All required checks passed.' : 'A required dependency needs attention.'}</span>
  </div>
</SurfaceCard>

<style>
  .status-line {
    display: grid;
    justify-items: start;
    gap: 0.85rem;
    line-height: 1.5;
  }
</style>
