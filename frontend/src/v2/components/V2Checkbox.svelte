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

<label class="v2-checkbox">
  <input type="checkbox" {checked} {disabled} onchange={(event) => onchange?.(event.currentTarget.checked)}>
  <span>{label}</span>
</label>
