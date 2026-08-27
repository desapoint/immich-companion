<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import type { IconName } from '../../../lib/types/ui';
  import type { AlbumOption, AssetActionPlan, StackResolution, TagOption } from '../types/assets';

  interface Props {
    plan: AssetActionPlan;
    albums: AlbumOption[];
    tags: TagOption[];
    busy?: boolean;
    onconfirm: () => void;
    onclose: () => void;
    onstackconfirm?: (mode: StackResolution) => void;
  }

  let {
    plan,
    albums,
    tags,
    busy = false,
    onconfirm,
    onclose,
    onstackconfirm = () => undefined,
  }: Props = $props();

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
    stack: 'Stack assets',
    set_stack_primary: 'Set as primary',
    remove_from_stack: 'Remove from stack',
    remove_stack: 'Remove complete stack',
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
    stack: 'stack',
    set_stack_primary: 'favorite',
    remove_from_stack: 'stack',
    remove_stack: 'stack',
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
  const stackConflicts = $derived(plan.stack_conflicts ?? []);
  let stackMode = $state<StackResolution | null>(null);

  function confirm(): void {
    if (stackConflicts.length) {
      if (stackMode) onstackconfirm(stackMode);
      return;
    }
    onconfirm();
  }
</script>

<ConfirmDialog
  title={`Confirm ${actionLabel.toLocaleLowerCase()}`}
  message={plan.operation === 'stack' && stackConflicts.length
    ? 'Some selected assets are already in stacks. Choose how to continue.'
    : `${plan.applicable_count} of ${requestedCount} ${noun} will change.`}
  confirmLabel={`Confirm ${actionLabel.toLocaleLowerCase()}`}
  icon={icons[plan.operation]}
  destructive={plan.destructive}
  confirmDisabled={plan.operation === 'stack' && stackConflicts.length > 0 && !stackMode}
  {busy}
  onconfirm={confirm}
  {onclose}
>
  {#snippet detail()}
    {#if relationNames.length}<p><strong>Relations:</strong> {relationNames.join(', ')}</p>{/if}
    {#if plan.skipped_count}
      <p>{plan.skipped_count} already satisfy the requested state and will be skipped.</p>
    {/if}
    {#if plan.missing_ids.length}<p>{plan.missing_ids.length} missing assets are excluded.</p>{/if}
    {#if plan.destructive}<p>Applicable assets will be moved out of the timeline and into trash.</p>{/if}
    {#if plan.operation === 'stack' && stackConflicts.length}
      <fieldset class="stack-conflict">
        <legend>Existing stacks</legend>
        <label>
          <input
            type="radio"
            name="stack-resolution"
            value="move_selected"
            disabled={busy}
            checked={stackMode === 'move_selected'}
            onchange={() => (stackMode = 'move_selected')}
          />
          <span><strong>Move selected assets</strong><small>Unselected members remain in their current stacks.</small></span>
        </label>
        <label>
          <input
            type="radio"
            name="stack-resolution"
            value="keep_existing"
            disabled={busy}
            checked={stackMode === 'keep_existing'}
            onchange={() => (stackMode = 'keep_existing')}
          />
          <span><strong>Keep existing stacks</strong><small>Only selected assets that are not stacked will be added.</small></span>
        </label>
        <label>
          <input
            type="radio"
            name="stack-resolution"
            value="include_existing"
            disabled={busy}
            checked={stackMode === 'include_existing'}
            onchange={() => (stackMode = 'include_existing')}
          />
          <span><strong>Include every member</strong><small>Bring all members of affected stacks into the new stack.</small></span>
        </label>
      </fieldset>
    {/if}
  {/snippet}
</ConfirmDialog>

<style>
  p { margin: 0.25rem 0 0; }
  .stack-conflict {
    display: grid;
    gap: 0.45rem;
    margin: 0.75rem 0 0;
    padding: 0.65rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
  }
  .stack-conflict legend { padding: 0 0.3rem; font-weight: 650; }
  .stack-conflict label { display: flex; gap: 0.55rem; align-items: flex-start; cursor: pointer; color: var(--color-ink); }
  .stack-conflict input { margin-top: 0.18rem; accent-color: var(--color-accent-strong); }
  .stack-conflict span { display: grid; gap: 0.08rem; }
  .stack-conflict small { color: var(--color-ink-muted); }
</style>
