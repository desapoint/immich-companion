<script lang="ts">
  import SurfaceCard from '../../../lib/components/layout/SurfaceCard.svelte';
  import type { VersionResponse } from '../types/status';

  interface Props {
    version: VersionResponse;
  }

  let { version }: Props = $props();
</script>

<SurfaceCard eyebrow="Build" title="Runtime identity">
  <dl>
    <div>
      <dt>Service</dt>
      <dd>{version.name}</dd>
    </div>
    <div>
      <dt>Version</dt>
      <dd><code>{version.version}</code></dd>
    </div>
    <div>
      <dt>Environment</dt>
      <dd>{version.environment}</dd>
    </div>
  </dl>
</SurfaceCard>

<style>
  dl {
    display: grid;
    gap: 0.55rem;
    margin: 0;
  }

  dl div {
    display: grid;
    grid-template-columns: minmax(6rem, 0.65fr) minmax(0, 1fr);
    gap: 1rem;
  }

  dt {
    color: var(--color-ink-muted);
  }

  dd {
    min-width: 0;
    margin: 0;
    overflow-wrap: anywhere;
    color: var(--color-ink-strong);
    font-weight: 700;
  }

  code {
    font: 0.82rem/1.4 var(--font-mono);
  }
</style>
