<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2Modal from './V2Modal.svelte';
  import { validPageNumber } from '../state/pagination';

  let {
    id,
    currentPage,
    maxPage,
    onpage,
    onclose,
  }: {
    id: string;
    currentPage: number;
    maxPage: number;
    onpage: (page: number) => void;
    onclose: () => void;
  } = $props();

  let draft = $state('');
  const normalized = $derived(validPageNumber(draft, maxPage));
  const valid = $derived(normalized !== null);
  const invalid = $derived(draft.trim().length > 0 && normalized === null);

  function submit(): void {
    if (normalized === null) return;
    onpage(normalized);
    onclose();
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter' || event.isComposing) return;
    event.preventDefault();
    submit();
  }

  function focusPageInput(input: HTMLInputElement): () => void {
    draft = String(currentPage);
    const timer = setTimeout(() => {
      input.focus();
      input.select();
    });
    return () => clearTimeout(timer);
  }
</script>

<V2Modal {id} title="Go to page" description={`Enter a page from 1 to ${maxPage.toLocaleString()}.`} size="sm" {onclose}>
  <label class="v2-field" for={`${id}-input`}>
    <span class="v2-field-label">Page number</span>
    <input
      {@attach focusPageInput}
      id={`${id}-input`}
      type="number"
      inputmode="numeric"
      min="1"
      max={maxPage}
      step="1"
      value={draft}
      aria-invalid={invalid || undefined}
      aria-describedby={`${id}-hint`}
      oninput={(event) => draft = event.currentTarget.value}
      onkeydown={handleKeydown}
    />
    <span id={`${id}-hint`} class={invalid ? 'v2-page-jump-error' : 'v2-small v2-muted'}>
      {invalid ? `Choose a whole number from 1 to ${maxPage.toLocaleString()}.` : `Current page: ${currentPage.toLocaleString()}`}
    </span>
  </label>

  {#snippet footer()}
    <V2Button onclick={onclose}>Cancel</V2Button>
    <V2Button variant="primary" disabled={!valid} onclick={submit}>Go to page</V2Button>
  {/snippet}
</V2Modal>

<style>
  .v2-page-jump-error { color: var(--v2-red); font-size: 12px; }
</style>
