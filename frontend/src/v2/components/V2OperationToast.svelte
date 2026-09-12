<script lang="ts">
  import { untrack } from 'svelte';
  import type { OperationFeedback } from '../data/mutationFeedback';
  import { useOptionalV2Toasts } from '../state/toasts.svelte';

  let {
    feedback,
    error = '',
    failureTitle = 'Operation failed',
    retryLabel = '',
    onretry,
  }: {
    feedback: OperationFeedback | null;
    error?: string;
    failureTitle?: string;
    retryLabel?: string;
    onretry?: () => void | Promise<void>;
  } = $props();

  const toasts = useOptionalV2Toasts();
  let lastOutcome = '';

  $effect(() => {
    const outcome = feedback;
    const failure = error.trim();
    if (outcome?.tone === 'pending' || (!outcome && !failure)) {
      lastOutcome = '';
      return;
    }
    const key = JSON.stringify([outcome?.tone, outcome?.title, outcome?.detail, outcome?.failures, failure]);
    if (!toasts || key === lastOutcome) return;
    lastOutcome = key;
    untrack(() => {
      const retry = retryLabel && onretry ? { label: retryLabel, run: onretry } : undefined;
      const firstFailure = outcome?.failures[0]?.reason;
      toasts.push({
        tone: failure ? (outcome ? 'warning' : 'error') : outcome?.tone === 'ok' ? 'success' : outcome?.tone === 'warn' ? 'warning' : 'error',
        title: failure ? (outcome ? `${outcome.title} needs attention` : failureTitle) : outcome?.title ?? failureTitle,
        message: [outcome?.detail, failure, firstFailure].filter(Boolean).join(' '),
        action: retry,
      });
    });
  });
</script>
