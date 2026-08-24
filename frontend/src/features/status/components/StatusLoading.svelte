<script lang="ts">
  import SurfaceCard from '../../../lib/components/layout/SurfaceCard.svelte';
</script>

<div role="status" aria-live="polite">
  <SurfaceCard eyebrow="Connecting" title="Reading companion status">
    <div class="loading-row">
      <span class="pulse" aria-hidden="true"></span>
      <p>Checking the backend and Immich dependency…</p>
    </div>
  </SurfaceCard>
</div>

<style>
  .loading-row {
    display: flex;
    align-items: center;
    gap: 0.8rem;
  }

  .pulse {
    width: 0.75rem;
    height: 0.75rem;
    flex: none;
    border-radius: 50%;
    background: var(--color-accent-strong);
    animation: pulse 1.2s ease-in-out infinite;
  }

  p {
    margin: 0;
  }

  @keyframes pulse {
    50% {
      opacity: 0.35;
      transform: scale(0.78);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .pulse {
      animation: none;
    }
  }
</style>
