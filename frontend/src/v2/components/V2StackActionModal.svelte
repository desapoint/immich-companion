<script lang="ts">
  import V2ConfirmDialog from './V2ConfirmDialog.svelte';
  import type { StackActionPlan, StackResolution } from '../data/contracts';

  let {
    plan,
    primaryLabel,
    resolution = null,
    busy = false,
    onresolutionchange,
    onconfirm,
    onclose,
  }: {
    plan: StackActionPlan;
    primaryLabel: string;
    resolution?: StackResolution | null;
    busy?: boolean;
    onresolutionchange: (resolution: StackResolution) => void;
    onconfirm: () => void;
    onclose: () => void;
  } = $props();

  const hasConflicts = $derived(plan.conflicts.length > 0);
  const options: Array<{ value: StackResolution; label: string; description: string }> = [
    { value: 'move_selected', label: 'Move selected assets', description: 'Detach selected assets. Unselected members remain together when at least two remain.' },
    { value: 'keep_existing', label: 'Keep existing stacks', description: 'Only selected assets that are not already stacked are added.' },
    { value: 'include_existing', label: 'Include every member', description: 'Merge every member of each affected stack into the new stack.' },
  ];
</script>

<V2ConfirmDialog
  title="Confirm stack assets"
  message={hasConflicts ? 'Some selected assets already belong to stacks. Choose how those stacks should be reconciled.' : `${plan.targetCount.toLocaleString()} selected assets will be placed in one stack.`}
  confirmLabel="Stack assets"
  icon="stack"
  pending={busy}
  confirmDisabled={hasConflicts && resolution === null}
  {onconfirm}
  {onclose}
>
  <div class="v2-stack-review">
    <p><strong>Stack primary:</strong> {primaryLabel}</p>
    {#if hasConflicts}
      <fieldset>
        <legend>Existing stacks</legend>
        {#each options as option (option.value)}
          <label>
            <input
              type="radio"
              name="v2-stack-resolution"
              value={option.value}
              checked={resolution === option.value}
              disabled={busy}
              onchange={() => onresolutionchange(option.value)}
            />
            <span><strong>{option.label}</strong><small>{option.description}</small></span>
          </label>
        {/each}
      </fieldset>
    {/if}
  </div>
</V2ConfirmDialog>

<style>
  .v2-stack-review, fieldset, label, label span { display: grid; }
  .v2-stack-review { gap: 10px; }
  .v2-stack-review p { margin: 0; }
  fieldset { gap: 7px; margin: 0; padding: 10px; border: 1px solid var(--v2-line); border-radius: 8px; }
  legend { padding: 0 5px; font-weight: 700; }
  label { grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 9px; cursor: pointer; }
  label input { margin-top: 3px; }
  label span { gap: 2px; }
  label small { color: var(--v2-muted); line-height: 1.4; }
</style>
