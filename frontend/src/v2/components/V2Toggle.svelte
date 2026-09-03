<script lang="ts">
  let {
    label,
    checked = false,
    disabled = false,
    onchange,
  }: {
    label: string;
    checked?: boolean;
    disabled?: boolean;
    onchange?: (checked: boolean) => void;
  } = $props();

  function toggle(): void {
    if (disabled) return;
    onchange?.(!checked);
  }
</script>

<button
  class="v2-toggle"
  type="button"
  role="switch"
  aria-checked={checked}
  {disabled}
  data-checked={checked || undefined}
  onclick={toggle}
>
  <span class="v2-toggle-track" data-checked={checked || undefined} aria-hidden="true">
    <span class="v2-toggle-thumb" data-checked={checked || undefined}></span>
  </span>
  <span class="v2-toggle-label">{label}</span>
</button>

<style>
  .v2-toggle[data-checked="true"] .v2-toggle-track {
    background: var(--v2-accent-2);
    border-color: #4e6e9b;
  }

  .v2-toggle[data-checked="true"] .v2-toggle-thumb {
    transform: translateX(14px);
    background: #cfe0ff;
  }

  .v2-toggle:focus-visible .v2-toggle-track {
    outline: 2px solid #4169a8;
    outline-offset: 2px;
  }

  .v2-toggle:disabled {
    cursor: default;
    opacity: .5;
  }
</style>
