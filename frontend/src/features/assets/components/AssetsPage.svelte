<script lang="ts">
  import AssetWorkspace from './AssetWorkspace.svelte';
</script>

<section class="assets-page">
  <header class="page-intro">
    <div>
      <span>Operational workspace</span>
      <h1>Search Immich assets</h1>
    </div>
    <p>
      Sync metadata into the companion index, narrow the library, select images, and inspect every result without exposing your Immich credentials.
    </p>
  </header>

  <AssetWorkspace />
</section>

<style>
  .assets-page {
    display: grid;
    gap: clamp(1.4rem, 3vw, 2.2rem);
  }

  .page-intro {
    display: grid;
    grid-template-columns: minmax(15rem, 0.75fr) minmax(18rem, 1fr);
    gap: 1.5rem;
    align-items: end;
  }

  .page-intro span {
    color: var(--color-accent-strong);
    font-size: 0.68rem;
    font-weight: 820;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h1 {
    margin: 0.28rem 0 0;
    font-size: clamp(2rem, 5vw, 3.6rem);
    letter-spacing: -0.055em;
    line-height: 0.98;
  }

  p {
    max-width: 44rem;
    margin: 0;
    color: var(--color-ink-muted);
    font-size: clamp(0.86rem, 1.4vw, 1rem);
    line-height: 1.65;
  }

  @media (max-width: 46rem) {
    .page-intro {
      grid-template-columns: 1fr;
      gap: 0.8rem;
    }
  }
</style>
