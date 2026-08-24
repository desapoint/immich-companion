<script lang="ts">
  interface Props {
    eyebrow: string;
    title: string;
    description: string;
    disabled?: boolean;
    onreset: () => void;
  }

  let { eyebrow, title, description, disabled = false, onreset }: Props = $props();
</script>

<header class="search-heading">
  <div>
    <span>{eyebrow}</span>
    <h2>{title}</h2>
    <p>{description}</p>
  </div>
  <div class="search-actions">
    <button class="reset-action" type="button" onclick={onreset} {disabled}>Clear filters</button>
    <button class="primary-action" type="submit" {disabled}>Search assets</button>
  </div>
</header>

<style>
  .search-heading,
  .search-actions {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 0.65rem;
  }

  span {
    color: var(--color-accent-strong);
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0.12rem 0 0;
    font-size: clamp(1rem, 2vw, 1.22rem);
  }

  p {
    margin: 0.22rem 0 0;
    color: var(--color-ink-muted);
    font-size: 0.78rem;
  }

  button {
    min-height: 2.65rem;
    padding: 0.6rem 0.86rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font: inherit;
    font-size: 0.78rem;
    font-weight: 780;
    white-space: nowrap;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  .primary-action {
    border-color: var(--color-accent-strong);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
  }

  .reset-action {
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
  }

  @media (max-width: 46rem) {
    .search-heading {
      align-items: stretch;
      flex-direction: column;
    }

    .search-actions button {
      flex: 1;
    }
  }
</style>
