<script lang="ts">
  import { onMount } from 'svelte';

  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import {
    decodeSavedExpertSearches,
    removeSavedExpertSearch,
    SAVED_EXPERT_SEARCHES_STORAGE_KEY,
    upsertSavedExpertSearch,
  } from '../state/savedExpertSearches';
  import { copySearchGroup } from '../state/assetViewModel';
  import type { SavedExpertSearch, SearchGroup } from '../types/assets';

  interface Props {
    expression: SearchGroup;
    disabled?: boolean;
    onload: (expression: SearchGroup) => void;
  }

  let { expression, disabled = false, onload }: Props = $props();
  let searches = $state.raw<SavedExpertSearch[]>([]);
  let selectedId = $state('');
  let name = $state('');
  let error = $state<string | null>(null);
  const options = $derived(searches.map((search) => ({ value: search.id, label: search.name })));
  const hasSelection = $derived(searches.some((search) => search.id === selectedId));

  onMount(() => {
    searches = decodeSavedExpertSearches(localStorage.getItem(SAVED_EXPERT_SEARCHES_STORAGE_KEY));
  });

  function persist(next: SavedExpertSearch[]): boolean {
    try {
      localStorage.setItem(SAVED_EXPERT_SEARCHES_STORAGE_KEY, JSON.stringify(next));
      searches = next;
      error = null;
      return true;
    } catch {
      error = 'Saved searches could not be written to this browser.';
      return false;
    }
  }

  function saveCurrent(): void {
    try {
      const next = upsertSavedExpertSearch(searches, name, expression);
      if (!persist(next)) return;
      selectedId = next[0].id;
      name = next[0].name;
    } catch (saveError) {
      error = saveError instanceof Error ? saveError.message : 'This search could not be saved.';
    }
  }

  function loadSelected(): void {
    const selected = searches.find((search) => search.id === selectedId);
    if (!selected) return;
    name = selected.name;
    error = null;
    onload(copySearchGroup(selected.expression));
  }

  function deleteSelected(): void {
    if (!hasSelection || !persist(removeSavedExpertSearch(searches, selectedId))) return;
    selectedId = '';
    name = '';
  }
</script>

<section class="saved-searches" aria-label="Saved Expert searches">
  <div class="saved-copy">
    <strong>Saved searches</strong>
    <span>Keep reusable Expert expressions in this browser.</span>
  </div>

  <div class="saved-controls">
    <label class="name-field">
      <span>Search name</span>
      <input
        type="text"
        maxlength="80"
        placeholder="e.g. Unsorted favorites"
        bind:value={name}
        {disabled}
      />
    </label>
    <div class="action-field">
      <span aria-hidden="true">Save</span>
      <button class="save" type="button" onclick={saveCurrent} {disabled}>Save current</button>
    </div>
    <SelectField
      id="saved-expert-search"
      label="Saved search"
      value={selectedId}
      {options}
      {disabled}
      compact
      onchange={(value) => (selectedId = value)}
    />
    <div class="action-field paired-actions">
      <span aria-hidden="true">Actions</span>
      <div>
        <button type="button" onclick={loadSelected} disabled={disabled || !hasSelection}>Load</button>
        <button class="delete" type="button" onclick={deleteSelected} disabled={disabled || !hasSelection}>Delete</button>
      </div>
    </div>
  </div>

  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .saved-searches {
    display: grid;
    gap: 0.65rem;
    padding: 0.72rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    background: var(--color-surface-soft);
  }

  .saved-copy {
    display: flex;
    align-items: baseline;
    gap: 0.55rem;
  }

  .saved-copy strong {
    color: var(--color-ink-strong);
    font-size: 0.8rem;
  }

  .saved-copy span {
    color: var(--color-ink-muted);
    font-size: 0.72rem;
  }

  .saved-controls {
    display: grid;
    grid-template-columns: minmax(12rem, 1fr) auto minmax(12rem, 1fr) auto;
    align-items: start;
    gap: 0.55rem;
  }

  .name-field,
  .action-field {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  .name-field > span,
  .action-field > span {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  .action-field > span {
    visibility: hidden;
  }

  input,
  button {
    min-height: 2.3rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    font: inherit;
    font-size: 0.76rem;
  }

  input {
    width: 100%;
    min-width: 0;
    padding: 0.42rem 0.68rem;
    color: var(--color-ink-strong);
    background: var(--color-canvas);
  }

  button {
    padding: 0.42rem 0.68rem;
    color: var(--color-accent-strong);
    background: var(--color-surface-raised);
    cursor: pointer;
    font-weight: 750;
  }

  button:hover:not(:disabled),
  input:focus-visible {
    border-color: var(--color-accent-strong);
  }

  button:focus-visible,
  input:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  .save {
    color: var(--color-canvas);
    background: var(--color-accent-strong);
  }

  .paired-actions > div {
    display: flex;
    gap: 0.4rem;
  }

  .delete {
    color: var(--color-negative-ink);
  }

  button:disabled,
  input:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

  .error {
    margin: 0;
    color: var(--color-negative-ink);
    font-size: 0.72rem;
  }

  @media (max-width: 62rem) {
    .saved-controls {
      grid-template-columns: minmax(12rem, 1fr) auto;
    }
  }

  @media (max-width: 36rem) {
    .saved-copy {
      align-items: flex-start;
      flex-direction: column;
      gap: 0.2rem;
    }

    .saved-controls {
      grid-template-columns: 1fr;
    }

    .action-field > span {
      display: none;
    }

    .action-field,
    .paired-actions > div,
    button {
      width: 100%;
    }

    .paired-actions button {
      flex: 1;
    }
  }
</style>
