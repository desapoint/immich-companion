<script lang="ts">
  interface Props {
    message: string;
    onretry: () => void;
  }

  let { message, onretry }: Props = $props();
</script>

<main class="runtime-error" aria-labelledby="runtime-error-title">
  <section role="alert">
    <p class="eyebrow">Frontend interrupted</p>
    <h1 id="runtime-error-title">Immich Companion could not render this page</h1>
    <p>{message}</p>
    <button type="button" onclick={onretry}>Reload the interface</button>
  </section>
</main>

<style>
  .runtime-error {
    display: grid;
    min-height: 100vh;
    padding: 1rem;
    place-items: center;
  }

  section {
    width: min(42rem, 100%);
    padding: clamp(1.25rem, 4vw, 2rem);
    border: 1px solid var(--color-negative-border, #e7b6b2);
    border-radius: var(--radius-md, 0.9rem);
    color: var(--color-negative-ink, #9a302e);
    background: var(--color-negative-surface, #fff0ee);
  }

  .eyebrow {
    margin: 0 0 0.5rem;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  h1 {
    margin: 0;
    color: var(--color-ink-strong, #171815);
    font-size: clamp(1.5rem, 5vw, 2.35rem);
    line-height: 1.08;
  }

  p:not(.eyebrow) {
    margin: 1rem 0 0;
    line-height: 1.55;
  }

  button {
    min-height: 2.65rem;
    margin-top: 1.25rem;
    padding: 0.65rem 0.9rem;
    border: 1px solid currentColor;
    border-radius: var(--radius-sm, 0.55rem);
    color: inherit;
    background: var(--color-surface-raised, #fffefa);
    cursor: pointer;
    font: inherit;
    font-size: 0.82rem;
    font-weight: 800;
  }
</style>
