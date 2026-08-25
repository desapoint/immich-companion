<script lang="ts">
  import type { AssetActionPlan } from '../types/assets';

  interface Props {
    plan: AssetActionPlan;
    relationLabel?: string | null;
    busy?: boolean;
    onconfirm: () => void;
    oncancel: () => void;
  }

  let {
    plan,
    relationLabel = null,
    busy = false,
    onconfirm,
    oncancel,
  }: Props = $props();

  const labels: Record<AssetActionPlan['operation'], string> = {
    archive: 'Archive',
    unarchive: 'Unarchive',
    favorite: 'Favorite',
    unfavorite: 'Unfavorite',
    trash: 'Trash',
    restore: 'Restore',
    remove_album: 'Remove from album',
    remove_tag: 'Remove tag',
  };
  const actionLabel = $derived(labels[plan.operation]);
</script>

<section class:destructive={plan.destructive} class="action-review" aria-label="Review asset action">
  <div>
    <span>Review action</span>
    <strong>{actionLabel}{relationLabel ? ` · ${relationLabel}` : ''}</strong>
    <p>
      {plan.applicable_count} of {plan.target_count} assets will change.
      {#if plan.skipped_count}
        {plan.skipped_count} already satisfy the requested state and will be skipped.
      {/if}
      {#if plan.missing_ids.length}
        {plan.missing_ids.length} missing assets are excluded.
      {/if}
    </p>
    {#if plan.destructive}
      <small>Trash is destructive and will move applicable assets out of the timeline.</small>
    {/if}
  </div>
  <div class="review-actions">
    <button type="button" class="secondary" onclick={oncancel} disabled={busy}>Cancel</button>
    <button type="button" class="confirm" onclick={onconfirm} disabled={busy}>
      {busy ? 'Applying…' : `Confirm ${actionLabel}`}
    </button>
  </div>
</section>

<style>
  .action-review {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.8rem;
    border: 1px solid var(--color-accent-strong);
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--color-accent-strong) 7%, var(--color-canvas));
  }

  .action-review.destructive {
    border-color: #b45309;
    background: color-mix(in srgb, #b45309 8%, var(--color-canvas));
  }

  .action-review > div:first-child {
    display: grid;
    gap: 0.2rem;
  }

  span,
  small {
    color: var(--color-ink-muted);
    font-size: 0.66rem;
  }

  span {
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  p {
    margin: 0;
    color: var(--color-ink-muted);
    font-size: 0.72rem;
  }

  .review-actions {
    display: flex;
    flex: 0 0 auto;
    gap: 0.5rem;
  }

  button {
    min-height: 2.35rem;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 780;
  }

  .confirm {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  button:disabled {
    cursor: wait;
    opacity: 0.55;
  }

  @media (max-width: 48rem) {
    .action-review {
      align-items: stretch;
      flex-direction: column;
    }

    .review-actions button {
      flex: 1;
    }
  }
</style>
