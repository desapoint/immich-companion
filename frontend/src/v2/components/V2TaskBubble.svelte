<script lang="ts">
  import { LoaderCircle } from '@lucide/svelte';

  let {
    value,
    indeterminate = false,
    label,
    detail,
    onclick,
  }: {
    value?: number;
    indeterminate?: boolean;
    label: string;
    detail?: string;
    onclick?: () => void;
  } = $props();

  const percent = $derived(Math.min(100, Math.max(0, value ?? 0)));
</script>

<button
  type="button"
  class="v2-task-bubble"
  data-indeterminate={indeterminate || undefined}
  style:--v2-task-fill={indeterminate ? undefined : `${percent}%`}
  aria-label={`${label}: ${indeterminate ? 'progress unknown' : `${Math.round(percent)}% complete`}. Expand background tasks`}
  {onclick}
>
  <span class="v2-task-bubble-shell" aria-hidden="true">
    <span class="v2-task-liquid">
      <span class="v2-task-wave v2-task-wave-back">
        <svg viewBox="0 0 300 24" preserveAspectRatio="none">
          <path d="M0 13 C18 5 32 5 50 13 S82 21 100 13 S132 5 150 13 S182 21 200 13 S232 5 250 13 S282 21 300 13 V24 H0 Z" />
        </svg>
      </span>
      <span class="v2-task-wave v2-task-wave-front">
        <svg viewBox="0 0 300 100" preserveAspectRatio="none">
          <path d="M0 16 C15 4 35 4 50 16 S85 28 100 16 S135 4 150 16 S185 28 200 16 S235 4 250 16 S285 28 300 16 V100 H0 Z" />
        </svg>
      </span>
    </span>
    <span class="v2-task-bubble-value">
      {#if indeterminate}
        <LoaderCircle size={17} strokeWidth={2.2} />
      {:else}
        {Math.round(percent)}
      {/if}
    </span>
  </span>
  <span class="v2-task-bubble-tooltip" role="tooltip">
    <b>{label}</b>
    {#if detail}<span>{detail}</span>{/if}
    <span>{indeterminate ? 'Progress amount is unknown' : `${Math.round(percent)}% complete`} · click to expand</span>
  </span>
</button>
