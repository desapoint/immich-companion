<script lang="ts">
  import V2Button from './Button.svelte';
  import V2Card from './Card.svelte';
  import V2Inline from '../layout/Inline.svelte';
  import V2Stack from '../layout/Stack.svelte';

  let { title='Something went wrong', message, retryLabel='Retry', onretry }: { title?: string; message: string; retryLabel?: string; onretry?: () => void } = $props();
</script>

<V2Card class="v2-error-state">
  <V2Inline justify="between" align="start" wrap={true}>
    <V2Stack gap="xs"><b>{title}</b><span class="v2-small v2-muted">{message}</span></V2Stack>
    {#if onretry}<V2Button onclick={onretry}>{retryLabel}</V2Button>{/if}
  </V2Inline>
</V2Card>

<style>
  :global(.v2-error-state) { border-color: color-mix(in srgb, var(--v2-danger, #e05a5a) 65%, transparent); }
</style>
