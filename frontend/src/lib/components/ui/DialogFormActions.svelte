<script lang="ts">
  interface Props {
    formId: string;
    submitLabel: string;
    busyLabel?: string;
    cancelLabel?: string;
    busy?: boolean;
    disabled?: boolean;
    oncancel: () => void;
  }

  let {
    formId,
    submitLabel,
    busyLabel = 'Saving…',
    cancelLabel = 'Cancel',
    busy = false,
    disabled = false,
    oncancel,
  }: Props = $props();
</script>

<div class="form-actions">
  <button type="button" disabled={busy} onclick={oncancel}>{cancelLabel}</button>
  <button class="primary" type="submit" form={formId} disabled={busy || disabled}>
    {busy ? busyLabel : submitLabel}
  </button>
</div>

<style>
  .form-actions {
    display: flex;
    width: 100%;
    justify-content: flex-end;
    gap: 0.5rem;
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

  button.primary {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  button:hover:not(:disabled) {
    background: var(--color-surface-soft);
  }

  button:disabled {
    cursor: wait;
    opacity: 0.5;
  }
</style>
