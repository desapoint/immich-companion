<script lang="ts">
  interface Props {
    page: number;
    pages: number;
    disabled?: boolean;
    onpage: (page: number) => void;
  }

  let { page, pages, disabled = false, onpage }: Props = $props();
</script>

{#if pages > 1}
  <nav class="pagination" aria-label="Asset result pages">
    <button type="button" onclick={() => onpage(page - 1)} disabled={disabled || page <= 1}>Previous page</button>
    <span>Page {page} of {pages}</span>
    <button type="button" onclick={() => onpage(page + 1)} disabled={disabled || page >= pages}>Next page</button>
  </nav>
{/if}

<style>
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
  }

  button {
    min-height: 2.4rem;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 760;
  }

  button:disabled {
    cursor: default;
    opacity: 0.45;
  }

  span {
    color: var(--color-ink-muted);
    font-size: 0.72rem;
  }
</style>
