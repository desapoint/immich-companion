<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Stack from './V2Stack.svelte';
  import type { OperationFeedback } from '../data/mutationFeedback';

  let { feedback, retryLabel = '', onretry }: { feedback: OperationFeedback | null; retryLabel?: string; onretry?: () => void } = $props();
</script>

{#if feedback}
  <V2Card class="v2-operation-feedback" data-tone={feedback.tone}>
    <V2Stack gap="sm">
      <V2Inline justify="between" align="start" wrap={true}>
        <div><b>{feedback.title}</b><div class="v2-small v2-muted">{feedback.detail}</div></div>
        {#if retryLabel && onretry}<V2Button onclick={onretry}>{retryLabel}</V2Button>{/if}
      </V2Inline>
      {#if feedback.failures.length}
        <details>
          <summary>{feedback.failures.length} failure{feedback.failures.length === 1 ? '' : 's'}</summary>
          <ul>
            {#each feedback.failures.slice(0, 20) as failure}
              <li><code>{failure.id}</code> — {failure.reason}</li>
            {/each}
          </ul>
          {#if feedback.failures.length > 20}<div class="v2-small v2-muted">Showing first 20 failures.</div>{/if}
        </details>
      {/if}
    </V2Stack>
  </V2Card>
{/if}

<style>
  :global(.v2-operation-feedback[data-tone='ok']) { border-color: color-mix(in srgb, var(--v2-ok, #4caf50) 55%, transparent); }
  :global(.v2-operation-feedback[data-tone='warn']) { border-color: color-mix(in srgb, var(--v2-warn, #f0ad4e) 65%, transparent); }
  :global(.v2-operation-feedback[data-tone='bad']) { border-color: color-mix(in srgb, var(--v2-danger, #e05a5a) 65%, transparent); }
  details summary { cursor: pointer; }
  ul { margin: 0; padding-left: 1.2rem; max-height: 12rem; overflow: auto; }
  code { overflow-wrap: anywhere; }
</style>
