<script lang="ts">
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import { createSearchCondition, createSearchGroup } from '../state/assetViewModel';
  import type { AlbumOption, SearchGroup } from '../types/assets';
  import SearchConditionRow from './SearchConditionRow.svelte';

  interface Props {
    expression: SearchGroup;
    albums: AlbumOption[];
    disabled?: boolean;
  }

  let { expression, albums, disabled = false }: Props = $props();
</script>

{#snippet groupEditor(group: SearchGroup, depth: number)}
  <section class:nested={depth > 0} class="filter-group" aria-label={depth === 0 ? 'Root filter group' : 'Nested filter group'}>
    <header>
      <div class="group-logic">
        <SelectField
          id={`${group.id}-logic`}
          label={depth === 0 ? 'Match assets when' : 'This group matches when'}
          value={group.operator}
          options={[
            { value: 'and', label: 'All conditions are true (AND)' },
            { value: 'or', label: 'Any condition is true (OR)' },
          ]}
          {disabled}
          compact
          onchange={(value) => (group.operator = value as 'and' | 'or')}
        />
        <label class="negate-control">
          <input type="checkbox" bind:checked={group.negate} {disabled} />
          <span>NOT this whole group</span>
        </label>
      </div>
    </header>

    <div class="group-children">
      {#each group.children as child, index (child.id)}
        {#if child.kind === 'condition'}
          <SearchConditionRow
            condition={child}
            {albums}
            {disabled}
            onremove={() => group.children.splice(index, 1)}
          />
        {:else}
          <div class="nested-wrapper">
            {@render groupEditor(child, depth + 1)}
            <button
              class="nested-remove"
              type="button"
              {disabled}
              onclick={() => group.children.splice(index, 1)}
            >Remove nested group</button>
          </div>
        {/if}
      {/each}
    </div>

    {#if group.children.length === 0}
      <p class="empty-group">No conditions: this group currently matches every asset.</p>
    {/if}

    <footer>
      <button type="button" {disabled} onclick={() => group.children.push(createSearchCondition())}>+ Condition</button>
      <button type="button" {disabled} onclick={() => group.children.push(createSearchGroup())}>+ Nested group</button>
    </footer>
  </section>
{/snippet}

{@render groupEditor(expression, 0)}

<style>
  .filter-group {
    display: grid;
    gap: 0.65rem;
    min-width: 0;
    padding: 0.72rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    background: var(--color-surface-soft);
  }

  .filter-group.nested {
    border-left: 0.25rem solid var(--color-accent-strong);
    background: var(--color-canvas);
  }

  header,
  footer,
  .group-logic {
    display: flex;
    align-items: end;
    gap: 0.65rem;
  }

  header {
    justify-content: space-between;
  }

  .group-logic {
    flex-wrap: wrap;
  }

  .negate-control {
    display: flex;
    align-items: center;
    gap: 0.42rem;
    min-height: 2.3rem;
    color: var(--color-ink-muted);
    font-size: 0.74rem;
    font-weight: 720;
  }

  .negate-control input {
    width: 1rem;
    height: 1rem;
    accent-color: var(--color-accent-strong);
  }

  .group-children {
    display: grid;
    gap: 0.55rem;
  }

  .nested-wrapper {
    position: relative;
    display: grid;
    gap: 0.4rem;
  }

  .empty-group {
    margin: 0;
    padding: 0.7rem;
    border: 1px dashed var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-muted);
    font-size: 0.76rem;
  }

  button {
    min-height: 2.25rem;
    padding: 0.42rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-accent-strong);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 750;
  }

  .nested-remove {
    justify-self: end;
    color: var(--color-negative-ink);
  }

  button:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  @media (max-width: 38rem) {
    header,
    footer,
    .group-logic {
      align-items: stretch;
      flex-direction: column;
    }

    footer button {
      width: 100%;
    }
  }
</style>
