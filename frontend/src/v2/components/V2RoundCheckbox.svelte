<script lang="ts">
  let {
    checked = false,
    indeterminate = false,
    disabled = false,
    size = 'md',
    ariaLabel,
    title = ariaLabel,
    onclick,
    onpointerdown,
  }: {
    checked?: boolean;
    indeterminate?: boolean;
    disabled?: boolean;
    size?: 'sm' | 'md';
    ariaLabel: string;
    title?: string;
    onclick?: (event: MouseEvent) => void;
    onpointerdown?: (event: PointerEvent) => void;
  } = $props();
</script>

<button
  class="v2-round-checkbox"
  class:small={size === 'sm'}
  class:checked={checked && !indeterminate}
  class:indeterminate
  type="button"
  role="checkbox"
  aria-checked={indeterminate ? 'mixed' : checked}
  aria-label={ariaLabel}
  {title}
  {disabled}
  onclick={(event) => {
    event.stopPropagation();
    onclick?.(event);
  }}
  onpointerdown={(event) => {
    event.stopPropagation();
    onpointerdown?.(event);
  }}
>
  <span class="v2-round-checkbox-mark" aria-hidden="true"></span>
</button>

<style>
  .v2-round-checkbox {
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    cursor: pointer;
  }

  .v2-round-checkbox-mark {
    width: 22px;
    height: 22px;
    position: relative;
    display: grid;
    place-items: center;
    border: 2px solid rgba(255, 255, 255, 0.92);
    border-radius: 50%;
    background: rgba(10, 15, 21, 0.72);
    box-shadow: 0 2px 7px rgba(0, 0, 0, 0.34);
    transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
  }

  .v2-round-checkbox.small {
    width: 28px;
    height: 28px;
  }

  .v2-round-checkbox.small .v2-round-checkbox-mark {
    width: 17px;
    height: 17px;
    border-width: 1.5px;
  }

  .v2-round-checkbox.small .v2-round-checkbox-mark::after {
    width: 6px;
    height: 3px;
    border-left-width: 1.5px;
    border-bottom-width: 1.5px;
  }

  .v2-round-checkbox.small.indeterminate .v2-round-checkbox-mark::after {
    width: 7px;
    height: 0;
    border-left: 0;
    border-bottom-width: 1.5px;
  }

  .v2-round-checkbox-mark::after {
    content: '';
    width: 8px;
    height: 4px;
    border-left: 2px solid white;
    border-bottom: 2px solid white;
    opacity: 0;
    transform: translateY(-1px) rotate(-45deg) scale(0.45);
    transition: opacity 120ms ease, transform 120ms ease;
  }

  .v2-round-checkbox.checked .v2-round-checkbox-mark {
    border-color: var(--v2-accent, #6ea8fe);
    background: var(--v2-accent, #6ea8fe);
    box-shadow: 0 2px 7px rgba(0, 0, 0, 0.34), 0 0 0 3px color-mix(in srgb, var(--v2-accent, #6ea8fe) 24%, transparent);
  }

  .v2-round-checkbox.indeterminate .v2-round-checkbox-mark {
    border-color: var(--v2-accent, #6ea8fe);
    background: var(--v2-accent-2, #243b69);
  }

  .v2-round-checkbox.checked .v2-round-checkbox-mark::after {
    opacity: 1;
    transform: translateY(-1px) rotate(-45deg) scale(1);
  }

  .v2-round-checkbox.indeterminate .v2-round-checkbox-mark::after {
    width: 9px;
    height: 0;
    border-left: 0;
    border-bottom: 2px solid white;
    opacity: 1;
    transform: none;
  }

  .v2-round-checkbox:hover:not(:disabled) .v2-round-checkbox-mark {
    border-color: white;
    transform: scale(1.06);
  }

  .v2-round-checkbox:focus-visible {
    outline: 2px solid white;
    outline-offset: 1px;
  }
  .v2-round-checkbox:disabled {
    cursor: default;
    opacity: 0.5;
  }

  .v2-round-checkbox:disabled .v2-round-checkbox-mark {
    transform: none;
  }
</style>
