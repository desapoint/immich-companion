<script lang="ts">
  import StatusNotice from './StatusNotice.svelte';

  interface Props {
    hasLoaded: boolean;
    initialLoading: boolean;
    refreshing: boolean;
    error: string | null;
    empty: boolean;
    loadingLabel: string;
    refreshingLabel: string;
    emptyLabel: string;
    retryLabel?: string;
    onretry: () => void;
    emptyActionLabel?: string;
    onemptyaction?: () => void;
  }

  let {
    hasLoaded,
    initialLoading,
    refreshing,
    error,
    empty,
    loadingLabel,
    refreshingLabel,
    emptyLabel,
    retryLabel = 'Retry',
    onretry,
    emptyActionLabel,
    onemptyaction,
  }: Props = $props();
</script>

{#if initialLoading && !hasLoaded}
  <StatusNotice message={loadingLabel} />
{:else if error && !hasLoaded}
  <StatusNotice tone="error" message={error} actionLabel={retryLabel} onaction={onretry} />
{:else}
  {#if refreshing}
    <StatusNotice compact message={refreshingLabel} />
  {/if}
  {#if error}
    <StatusNotice compact tone="error" message={error} actionLabel={retryLabel} onaction={onretry} />
  {:else if empty}
    <StatusNotice
      compact
      message={emptyLabel}
      actionLabel={emptyActionLabel}
      onaction={onemptyaction}
    />
  {/if}
{/if}
