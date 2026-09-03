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
</script>

<label class="v2-toggle">
  <input type="checkbox" {checked} {disabled} onchange={(event) => onchange?.(event.currentTarget.checked)}>
  <span class="v2-toggle-track" aria-hidden="true"><span class="v2-toggle-thumb"></span></span>
  <span class="v2-toggle-label">{label}</span>
</label>
