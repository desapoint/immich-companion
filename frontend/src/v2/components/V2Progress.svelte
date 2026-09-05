<script lang="ts">
  let {
    value,
    label = 'Progress',
    indeterminate = false,
  }: {
    value?: number;
    label?: string;
    indeterminate?: boolean;
  } = $props();

  const percent = $derived(Math.min(100, Math.max(0, value ?? 0)));
</script>

<div
  class="v2-progress"
  data-indeterminate={indeterminate || undefined}
  role="progressbar"
  aria-label={label}
  aria-valuemin={indeterminate ? undefined : 0}
  aria-valuemax={indeterminate ? undefined : 100}
  aria-valuenow={indeterminate ? undefined : percent}
>
  <i style:width={indeterminate ? undefined : `${percent}%`}></i>
</div>
