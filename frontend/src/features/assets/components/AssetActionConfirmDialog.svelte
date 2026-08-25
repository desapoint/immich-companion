<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import type { IconName } from '../../../lib/types/ui';
  import type { AlbumOption, AssetActionPlan, TagOption } from '../types/assets';

  interface Props {
    plan: AssetActionPlan;
    albums: AlbumOption[];
    tags: TagOption[];
    busy?: boolean;
    onconfirm: () => void;
    onclose: () => void;
  }

  let { plan, albums, tags, busy = false, onconfirm, onclose }: Props = $props();

  const labels: Record<AssetActionPlan['operation'], string> = {
    archive: 'Archive',
    unarchive: 'Unarchive',
    favorite: 'Favorite',
    unfavorite: 'Unfavorite',
    trash: 'Trash',
    restore: 'Restore',
    add_album: 'Add to albums',
    add_tag: 'Add tags',
    remove_album: 'Remove from albums',
    remove_tag: 'Remove tags',
  };
  const icons: Record<AssetActionPlan['operation'], IconName> = {
    archive: 'archive',
    unarchive: 'unarchive',
    favorite: 'favorite',
    unfavorite: 'unfavorite',
    trash: 'trash',
    restore: 'restore',
    add_album: 'album-add',
    add_tag: 'tag-add',
    remove_album: 'album-remove',
    remove_tag: 'tag-remove',
  };
  const actionLabel = $derived(labels[plan.operation]);
  const relationNames = $derived.by(() => {
    const options = plan.operation.endsWith('album') ? albums : tags;
    return plan.relation_ids.map((relationId) =>
      options.find((option) => option.id === relationId)?.name ?? relationId,
    );
  });
  const requestedCount = $derived(
    plan.relation_ids.length ? plan.target_count * plan.relation_ids.length : plan.target_count,
  );
  const noun = $derived(plan.relation_ids.length ? 'asset-relation changes' : 'assets');
</script>

<ConfirmDialog
  title={`Confirm ${actionLabel.toLocaleLowerCase()}`}
  message={`${plan.applicable_count} of ${requestedCount} ${noun} will change.`}
  confirmLabel={`Confirm ${actionLabel.toLocaleLowerCase()}`}
  icon={icons[plan.operation]}
  destructive={plan.destructive}
  {busy}
  {onconfirm}
  {onclose}
>
  {#snippet detail()}
    {#if relationNames.length}<p><strong>Relations:</strong> {relationNames.join(', ')}</p>{/if}
    {#if plan.skipped_count}
      <p>{plan.skipped_count} already satisfy the requested state and will be skipped.</p>
    {/if}
    {#if plan.missing_ids.length}<p>{plan.missing_ids.length} missing assets are excluded.</p>{/if}
    {#if plan.destructive}<p>Applicable assets will be moved out of the timeline and into trash.</p>{/if}
  {/snippet}
</ConfirmDialog>

<style>
  p { margin: 0.25rem 0 0; }
</style>
