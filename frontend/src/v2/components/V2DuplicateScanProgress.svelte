<script lang="ts">
  import type { DuplicateDiscoveryProgress } from '../data/contracts';
  import V2Badge from './V2Badge.svelte';
  import V2Card from './V2Card.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Progress from './V2Progress.svelte';
  import V2Stack from './V2Stack.svelte';

  let { progress }: { progress: DuplicateDiscoveryProgress } = $props();

  const progressKnown = $derived(progress.percent !== null);
  const processedLabel = $derived(
    progress.total === null
      ? `${progress.completed.toLocaleString()} processed`
      : `${progress.completed.toLocaleString()} / ${progress.total.toLocaleString()}`,
  );
</script>

<V2Card class="v2-duplicate-scan-progress">
  <V2Stack gap="sm">
    <V2Inline justify="between" align="center" wrap={true}>
      <b>{progress.phase}</b>
      <V2Inline gap="sm" wrap={true}>
        <V2Badge text={processedLabel} />
        {#if progress.candidatePairs !== null}<V2Badge text={`${progress.candidatePairs.toLocaleString()} candidate pairs`} />{/if}
        {#if progress.matchesFound !== null}<V2Badge tone="ok" text={`${progress.matchesFound.toLocaleString()} matches retained`} />{/if}
      </V2Inline>
    </V2Inline>
    <V2Progress
      value={progressKnown ? progress.percent ?? undefined : undefined}
      indeterminate={!progressKnown}
      label={`${progress.phase} progress`}
    />
    <span class="v2-small v2-muted">{progress.detail}</span>
    <span class="v2-small v2-muted">The previous completed results remain visible until this scan finishes.</span>
  </V2Stack>
</V2Card>
