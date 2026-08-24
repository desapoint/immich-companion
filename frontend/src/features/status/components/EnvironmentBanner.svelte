<script lang="ts">
  import StatusBadge from '../../../lib/components/ui/StatusBadge.svelte';
  import type { HealthResponse } from '../types/status';

  interface Props {
    health: HealthResponse;
  }

  let { health }: Props = $props();
</script>

<section class="environment-banner" class:unsafe={!health.safe_mode} aria-label="Runtime safety">
  <div>
    <p class="label">{health.environment} environment</p>
    <p class="description">
      {health.safe_mode
        ? 'Destructive operations are disabled for this instance.'
        : 'Destructive operations are enabled. Review actions carefully.'}
    </p>
  </div>
  <StatusBadge
    label={health.safe_mode ? 'Safe mode' : 'Actions enabled'}
    tone={health.safe_mode ? 'positive' : 'negative'}
  />
</section>

<style>
  .environment-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    margin-bottom: 1rem;
    padding: 1rem 1.15rem;
    border: 1px solid var(--color-positive-border);
    border-radius: var(--radius-md);
    background: var(--color-positive-surface);
  }

  .environment-banner.unsafe {
    border-color: var(--color-negative-border);
    background: var(--color-negative-surface);
  }

  p {
    margin: 0;
  }

  .label {
    color: var(--color-ink-strong);
    font-size: 0.78rem;
    font-weight: 850;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  .description {
    margin-top: 0.25rem;
    color: var(--color-ink-muted);
    font-size: 0.82rem;
  }

  @media (max-width: 38rem) {
    .environment-banner {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
