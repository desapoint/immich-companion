<script lang="ts">
  import { AlertTriangle, Eye, ShieldCheck } from '@lucide/svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Inline from '../../../lib/components/layout/Inline.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import type { DuplicateReviewIssue } from '../state/duplicateReviewPreflight';

  let {
    issue,
    issueCount,
    canKeep = true,
    onview,
    onkeep,
  }: {
    issue: DuplicateReviewIssue;
    issueCount: number;
    canKeep?: boolean;
    onview: () => void;
    onkeep: () => void;
  } = $props();
</script>

<V2Card class="duplicate-review-issue">
  <div role="alert" aria-live="assertive">
    <V2Inline gap="sm" align="start" justify="between" wrap={true}>
      <V2Inline gap="sm" align="start">
        <span class="issue-icon" aria-hidden="true"><AlertTriangle size={19} /></span>
        <V2Stack gap="xs">
          <b>Resolve {issueCount === 1 ? 'this stack issue' : `${issueCount} stack issues`} before continuing</b>
          <span class="v2-small v2-muted">{issue.message}</span>
          <span class="v2-small v2-muted">Review actions and page changes are paused so this choice cannot be left behind.</span>
        </V2Stack>
      </V2Inline>
      <V2Inline gap="sm" wrap={true}>
        <V2Button onclick={onview}><Eye size={16} aria-hidden="true" /> View issue</V2Button>
        <V2Button variant="primary" disabled={!canKeep} onclick={onkeep}><ShieldCheck size={16} aria-hidden="true" /> Keep instead</V2Button>
      </V2Inline>
    </V2Inline>
  </div>
</V2Card>

<style>
  :global(.duplicate-review-issue) {
    border-color: color-mix(in srgb, var(--v2-warn, #f0ad4e) 70%, var(--v2-line));
    background: color-mix(in srgb, var(--v2-warn, #f0ad4e) 8%, var(--v2-surface));
  }
  .issue-icon { display: grid; flex: 0 0 auto; place-items: center; color: var(--v2-warn, #f0ad4e); }
</style>
