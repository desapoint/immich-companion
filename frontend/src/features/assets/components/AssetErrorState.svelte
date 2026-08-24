<script lang="ts">
  interface Props {
    message: string;
    onretry: () => void;
  }

  let { message, onretry }: Props = $props();
</script>

<div class="error-state" role="alert">
  <div>
    <strong>Asset workspace unavailable</strong>
    <p>{message}</p>
  </div>
  <button type="button" onclick={onretry}>Retry asset search</button>
</div>

<style>
  .error-state {
    display: flex;
    min-height: 10rem;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 1.5rem;
    border: 1px solid var(--color-negative-border);
    border-radius: var(--radius-md);
    color: var(--color-negative-ink);
    background: var(--color-negative-surface);
  }

  strong,
  p {
    display: block;
    margin: 0;
  }

  p {
    max-width: 40rem;
    margin-top: 0.25rem;
    font-size: 0.75rem;
  }

  button {
    flex: 0 0 auto;
    min-height: 2.45rem;
    padding: 0.55rem 0.8rem;
    border: 1px solid var(--color-negative-border);
    border-radius: var(--radius-sm);
    color: inherit;
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 760;
  }

  @media (max-width: 36rem) {
    .error-state {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
