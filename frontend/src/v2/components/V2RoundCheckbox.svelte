<script lang="ts">
  let {
    checked = false,
    ariaLabel,
    title = ariaLabel,
    onclick,
    onpointerdown,
  }: {
    checked?: boolean;
    ariaLabel: string;
    title?: string;
    onclick?: (event: MouseEvent) => void;
    onpointerdown?: (event: PointerEvent) => void;
  } = $props();
</script>

<button
  class="v2-round-checkbox"
  class:checked
  type="button"
  role="checkbox"
  aria-checked={checked}
  aria-label={ariaLabel}
  {title}
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

  .v2-round-checkbox.checked .v2-round-checkbox-mark::after {
    opacity: 1;
    transform: translateY(-1px) rotate(-45deg) scale(1);
  }

  .v2-round-checkbox:hover .v2-round-checkbox-mark {
    border-color: white;
    transform: scale(1.06);
  }

  .v2-round-checkbox:focus-visible {
    outline: 2px solid white;
    outline-offset: 1px;
  }
</style>
