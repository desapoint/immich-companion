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
  aria-label={label}
  {disabled}
  data-disabled={disabled || undefined}
  onclick={toggle}
>
  <span class="v2-toggle-track" data-checked={checked || undefined} aria-hidden="true">
    <span class="v2-toggle-thumb" data-checked={checked || undefined}></span>
  </span>
  <span class="v2-toggle-label">{label}</span>
</button>
