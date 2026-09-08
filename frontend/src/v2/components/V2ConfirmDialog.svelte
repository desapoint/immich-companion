<script lang="ts">
  import type { Snippet } from 'svelte';

  import Icon from '../../lib/components/ui/Icon.svelte';
  import type { IconName } from '../../lib/types/ui';
  import V2Button from './V2Button.svelte';
  import V2Modal from './V2Modal.svelte';

  let {
    title,
    message,
    confirmLabel,
    icon = 'check',
    children,
    detail,
    busy = false,
    loading = false,
    confirmDisabled = false,
    destructive = false,
    onconfirm,
    onclose,
  }: {
    title: string;
    message?: string;
    confirmLabel: string;
    icon?: IconName;
    children?: Snippet;
    detail?: Snippet;
    busy?: boolean;
    loading?: boolean;
    confirmDisabled?: boolean;
    destructive?: boolean;
    onconfirm: () => void;
    onclose: () => void;
  } = $props();
  const dialogId = $props.id();

  function requestClose(): void {
    if (!busy) onclose();
  }
</script>

<V2Modal
  id={dialogId}
  {title}
  size="sm"
  dismissOnBackdrop={!busy}
  onclose={requestClose}
>
  <div class="v2-confirmation" data-destructive={destructive || undefined}>
    <span class="v2-confirmation-icon"><Icon name={icon} size="1.35rem" /></span>
    <div class="v2-confirmation-copy">
      {#if message}<p>{message}</p>{/if}
      {#if detail}<div class="v2-confirmation-detail">{@render detail()}</div>{/if}
      {#if children}<div class="v2-confirmation-form">{@render children()}</div>{/if}
    </div>
  </div>

  {#snippet footer()}
    <V2Button disabled={busy} onclick={requestClose}>Cancel</V2Button>
    <V2Button
      variant={destructive ? 'danger' : 'primary'}
      disabled={busy || confirmDisabled}
      onclick={onconfirm}
    >
      {#if busy && loading}
        <span class="v2-confirmation-loading" aria-live="polite">
          <span class="v2-confirmation-spinner" aria-hidden="true"></span>
          <span>Applying…</span>
        </span>
      {:else}
        {confirmLabel}
      {/if}
    </V2Button>
  {/snippet}
</V2Modal>

<style>
  .v2-confirmation {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 12px;
    align-items: start;
  }

  .v2-confirmation-icon {
    display: grid;
    width: 42px;
    height: 42px;
    place-items: center;
    border-radius: 999px;
    color: var(--v2-accent);
    background: var(--v2-accent-2);
  }

  .v2-confirmation[data-destructive='true'] .v2-confirmation-icon {
    color: var(--v2-red);
    background: color-mix(in srgb, var(--v2-red) 14%, var(--v2-surface-2));
  }

  .v2-confirmation-copy { min-width: 0; }
  p { margin: 2px 0 0; line-height: 1.5; }
  .v2-confirmation-detail { margin-top: 10px; color: var(--v2-muted); font-size: 12px; }
  .v2-confirmation-form { min-width: 0; margin-top: 12px; }
  .v2-confirmation-loading { display: inline-flex; align-items: center; gap: 8px; }
  .v2-confirmation-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 999px;
    animation: v2-confirmation-spin .7s linear infinite;
  }

  @keyframes v2-confirmation-spin { to { transform: rotate(360deg); } }
</style>
