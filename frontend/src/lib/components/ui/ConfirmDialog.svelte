<script lang="ts">
  import type { Snippet } from 'svelte';

  import type { IconName } from '../../types/ui';
  import Dialog from './Dialog.svelte';
  import Icon from './Icon.svelte';

  interface Props {
    title: string;
    message: string;
    confirmLabel: string;
    icon?: IconName;
    detail?: Snippet;
    busy?: boolean;
    destructive?: boolean;
    onconfirm: () => void;
    onclose: () => void;
  }

  let {
    title,
    message,
    confirmLabel,
    icon = 'check',
    detail,
    busy = false,
    destructive = false,
    onconfirm,
    onclose,
  }: Props = $props();
</script>

<Dialog {title} size="small" closeOnBackdrop={!busy} closeOnEscape={!busy} {onclose}>
  <div class:destructive class="confirmation">
    <span class="confirmation-icon"><Icon name={icon} size="1.35rem" /></span>
    <div>
      <p>{message}</p>
      {#if detail}<div class="detail">{@render detail()}</div>{/if}
    </div>
  </div>
  {#snippet footer()}
    <div class="confirmation-actions">
      <button type="button" onclick={onclose} disabled={busy}>Cancel</button>
      <button
        class:destructive
        class="confirm"
        type="button"
        onclick={onconfirm}
        disabled={busy}
      >{busy ? 'Applying…' : confirmLabel}</button>
    </div>
  {/snippet}
</Dialog>

<style>
  .confirmation {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.8rem;
    align-items: start;
  }

  .confirmation-icon {
    display: grid;
    width: 2.6rem;
    height: 2.6rem;
    place-items: center;
    border-radius: 999px;
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  .confirmation.destructive .confirmation-icon { color: #b45309; }
  p { margin: 0; line-height: 1.5; }
  .detail { margin-top: 0.65rem; color: var(--color-ink-muted); font-size: 0.74rem; }

  .confirmation-actions {
    display: flex;
    width: 100%;
    justify-content: flex-end;
    gap: 0.55rem;
  }

  button {
    min-height: 2.4rem;
    padding: 0.5rem 0.8rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 780;
  }

  .confirm { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  .confirm.destructive { border-color: #b45309; color: #b45309; }
  button:disabled { cursor: wait; opacity: 0.5; }
</style>
