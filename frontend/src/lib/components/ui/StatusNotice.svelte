<script lang="ts">
  type NoticeTone = 'info' | 'success' | 'warning' | 'error';

  interface Props {
    message: string;
    tone?: NoticeTone;
    compact?: boolean;
    actionLabel?: string;
    onaction?: () => void;
    actionDisabled?: boolean;
    dismissLabel?: string;
    ondismiss?: () => void;
  }

  let {
    message,
    tone = 'info',
    compact = false,
    actionLabel,
    onaction,
    actionDisabled = false,
    dismissLabel = 'Dismiss',
    ondismiss,
  }: Props = $props();

  const role = $derived(tone === 'error' ? 'alert' : 'status');
  const live = $derived(tone === 'error' ? 'assertive' : 'polite');
</script>

<div class="status-notice" class:compact data-tone={tone} {role} aria-live={live}>
  <p>{message}</p>
  {#if actionLabel && onaction}
    <button type="button" disabled={actionDisabled} onclick={onaction}>{actionLabel}</button>
  {/if}
  {#if ondismiss}
    <button class="dismiss" type="button" aria-label={dismissLabel} onclick={ondismiss}>×</button>
  {/if}
</div>

<style>
  .status-notice {
    --notice-color: var(--color-accent-strong);
    display: flex;
    min-width: 0;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.65rem;
    padding: 0.7rem 0.8rem;
    border: 1px solid color-mix(in srgb, var(--notice-color) 34%, var(--color-border-subtle));
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--notice-color) 7%, var(--color-surface-raised));
  }

  .status-notice[data-tone='success'] { --notice-color: var(--color-accent-strong); }
  .status-notice[data-tone='warning'] { --notice-color: var(--color-warning, #8a5b00); }
  .status-notice[data-tone='error'] { --notice-color: var(--color-danger, #a33d45); }

  .status-notice.compact {
    padding-block: 0.52rem;
  }

  p {
    min-width: 0;
    flex: 1 1 14rem;
    margin: 0;
    color: var(--color-ink-strong);
    font-size: 0.78rem;
    line-height: 1.45;
  }

  button {
    min-height: 2.15rem;
    padding: 0.4rem 0.68rem;
    border: 1px solid var(--notice-color);
    border-radius: var(--radius-sm);
    color: var(--notice-color);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 760;
  }

  button:hover:not(:disabled) {
    background: color-mix(in srgb, var(--notice-color) 9%, var(--color-surface-raised));
  }

  button:disabled {
    cursor: default;
    opacity: 0.5;
  }

  button.dismiss {
    min-width: 2.15rem;
    padding-inline: 0.45rem;
    border-color: transparent;
    color: var(--color-ink-muted);
    background: transparent;
    font-size: 1rem;
  }
</style>
