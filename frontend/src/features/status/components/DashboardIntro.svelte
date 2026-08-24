<script lang="ts">
  const pageTitle = 'Companion status';
</script>

<div class="intro">
  <p class="eyebrow">System overview</p>
  <h1>{pageTitle}</h1>
  <p class="lede">
    A live read-only view of this companion instance, its Immich connection, and the
    operations currently available.
  </p>
</div>

<style>
  .intro {
    max-width: 48rem;
    margin-bottom: clamp(1.75rem, 4vw, 2.75rem);
  }

  .eyebrow {
    margin: 0 0 0.65rem;
    color: var(--color-accent-strong);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  h1 {
    margin: 0;
    color: var(--color-ink-strong);
    font-size: clamp(2.4rem, 7vw, 5.4rem);
    font-weight: 760;
    letter-spacing: -0.065em;
    line-height: 0.94;
  }

  .lede {
    max-width: 42rem;
    margin: 1.25rem 0 0;
    color: var(--color-ink-muted);
    font-size: clamp(1rem, 2.2vw, 1.18rem);
    line-height: 1.65;
  }
</style>
