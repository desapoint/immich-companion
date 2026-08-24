<script lang="ts">
  import SurfaceCard from '../../../lib/components/layout/SurfaceCard.svelte';
  import StatusBadge from '../../../lib/components/ui/StatusBadge.svelte';

  interface Props {
    message: string;
    onretry: () => void;
  }

  let { message, onretry }: Props = $props();
</script>

<div role="alert">
  <SurfaceCard eyebrow="Connection failed" title="The companion backend is unavailable">
    <div class="error-content">
      <StatusBadge label="Unavailable" tone="negative" />
      <p>{message}</p>
      <p>Confirm the companion service is running, then try the request again.</p>
      <button type="button" onclick={onretry}>Retry status check</button>
    </div>
  </SurfaceCard>
</div>

<style>
  .error-content {
    display: grid;
    justify-items: start;
    gap: 0.85rem;
  }

  p {
    margin: 0;
    line-height: 1.55;
  }

  button {
    margin-top: 0.25rem;
    padding: 0.7rem 1rem;
    border: 1px solid var(--color-accent-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 800;
    cursor: pointer;
  }

  button:hover {
    background: var(--color-accent-hover);
  }
</style>
