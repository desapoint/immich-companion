<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import type { AssetTaskStatus } from '../types/assets';

  interface Props {
    task: AssetTaskStatus;
    onretry: (ids: string[]) => void;
    onclose: () => void;
  }

  let { task, onretry, onclose }: Props = $props();
  const summary = $derived(task.result?.summary ?? {});
  const failedIds = $derived(summary.failed_ids ?? []);
  const missingIds = $derived(summary.missing_ids ?? []);
  const errors = $derived(summary.errors ?? []);
</script>

<ConfirmDialog
  title="Selected asset sync finished with errors"
  message={`${failedIds.length} assets failed after retrying. ${missingIds.length} no longer exist and cannot be retried.`}
  confirmLabel={`Select ${failedIds.length} failed assets`}
  icon="info"
  confirmDisabled={failedIds.length === 0}
  onconfirm={() => onretry(failedIds)}
  {onclose}
>
  {#snippet detail()}
    {#if errors.length}
      <div class="errors">
        {#each errors as item}
          <p><strong>{item.count.toLocaleString()}</strong> · {item.error}</p>
        {/each}
      </div>
    {/if}
    {#if missingIds.length}<p>{missingIds.length.toLocaleString()} assets were not found in Immich.</p>{/if}
  {/snippet}
</ConfirmDialog>

<style>
  p { margin: 0.25rem 0 0; }
  .errors { display: grid; gap: 0.18rem; }
  .errors p { overflow-wrap: anywhere; }
</style>
