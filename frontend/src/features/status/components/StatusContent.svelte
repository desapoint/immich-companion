<script lang="ts">
  import type { StatusLoadState } from '../../../lib/types/status';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Metric from '../../../lib/components/ui/Metric.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import V2Table from '../../../lib/components/ui/Table.svelte';
  import V2Toolbar from '../../../lib/components/layout/Toolbar.svelte';
  import V2Zone from '../../../lib/components/layout/Zone.svelte';
  import { companionState, dependencyState, immichVersion } from '../utils/statusPresentation';

  let {
    state,
    onrefresh,
  }: {
    state: StatusLoadState;
    onrefresh: () => void | Promise<void>;
  } = $props();
</script>

<V2Zone>
  {#if state.kind === 'loading'}
    <V2Notice>Loading live Companion status…</V2Notice>
    <div class="v2-metric-grid">
      <V2Metric value="…" label="Companion backend" />
      <V2Metric value="…" label="Immich dependency" />
      <V2Metric value="…" label="Capabilities" />
      <V2Metric value="…" label="Immich version" />
    </div>
  {:else if state.kind === 'error'}
    <V2Notice>
      <V2Stack gap="sm">
        <div><b>Status unavailable.</b><br>{state.message}</div>
        <div><V2Button variant="primary" onclick={onrefresh}>Retry</V2Button></div>
      </V2Stack>
    </V2Notice>
  {:else}
    {@const snapshot = state.snapshot}
    {@const companion = companionState(snapshot)}
    {@const immichDep = snapshot.health.dependencies.immich}
    {@const databaseDep = snapshot.health.dependencies.companion_database}
    {@const immich = dependencyState(immichDep, 'Connected')}
    {@const database = dependencyState(databaseDep, 'Ready')}

    <V2Toolbar>
      <b>System overview</b>
      {#snippet actions()}<V2Button onclick={onrefresh}>Refresh view</V2Button>{/snippet}
    </V2Toolbar>

    <div class="v2-metric-grid">
      <V2Metric value={companion.label} label="Companion backend" />
      <V2Metric value={immich.label} label="Immich dependency" />
      <V2Metric value={String(snapshot.capabilities.implemented.length)} label="Capabilities" />
      <V2Metric value={immichVersion(snapshot)} label="Immich version" />
    </div>

    <V2Section title="Dependencies">
      <V2Card>
        <div class="status-dependency-table">
          <V2Table>
            <thead><tr><th>Service</th><th>Status</th><th>Version</th><th>Details</th></tr></thead>
            <tbody>
              <tr><td>Immich API</td><td><V2Badge tone={immich.tone} text={immich.label} /></td><td>{immichVersion(snapshot)}</td><td>{immichDep.detail ?? (immichDep.configured ? 'Configured' : 'Not configured')}</td></tr>
              <tr><td>Companion API</td><td><V2Badge tone={companion.tone} text={companion.label} /></td><td>{snapshot.version.version}</td><td>{snapshot.health.status}</td></tr>
              <tr><td>Database</td><td><V2Badge tone={database.tone} text={database.label} /></td><td>—</td><td>{databaseDep.detail ?? (databaseDep.configured ? 'Configured' : 'Not configured')}</td></tr>
            </tbody>
          </V2Table>
        </div>

        <div class="status-dependency-cards" aria-label="Dependency details">
          <article class="status-dependency-card">
            <h3>Immich API</h3>
            <dl>
              <div><dt>Status</dt><dd><V2Badge tone={immich.tone} text={immich.label} /></dd></div>
              <div><dt>Version</dt><dd>{immichVersion(snapshot)}</dd></div>
              <div><dt>Details</dt><dd>{immichDep.detail ?? (immichDep.configured ? 'Configured' : 'Not configured')}</dd></div>
            </dl>
          </article>
          <article class="status-dependency-card">
            <h3>Companion API</h3>
            <dl>
              <div><dt>Status</dt><dd><V2Badge tone={companion.tone} text={companion.label} /></dd></div>
              <div><dt>Version</dt><dd>{snapshot.version.version}</dd></div>
              <div><dt>Details</dt><dd>{snapshot.health.status}</dd></div>
            </dl>
          </article>
          <article class="status-dependency-card">
            <h3>Database</h3>
            <dl>
              <div><dt>Status</dt><dd><V2Badge tone={database.tone} text={database.label} /></dd></div>
              <div><dt>Version</dt><dd>—</dd></div>
              <div><dt>Details</dt><dd>{databaseDep.detail ?? (databaseDep.configured ? 'Configured' : 'Not configured')}</dd></div>
            </dl>
          </article>
        </div>
      </V2Card>
    </V2Section>
  {/if}
</V2Zone>

<style>
  .status-dependency-cards {
    display: none;
  }

  @media (max-width: 620px) {
    .status-dependency-table {
      display: none;
    }

    .status-dependency-cards {
      display: grid;
      gap: 10px;
    }

    .status-dependency-card {
      min-width: 0;
      padding: 11px;
      border: 1px solid var(--v2-line);
      border-radius: 9px;
      background: color-mix(in srgb, var(--v2-surface-2) 55%, transparent);
    }

    .status-dependency-card h3 {
      margin: 0 0 9px;
      font-size: 14px;
    }

    .status-dependency-card dl {
      display: grid;
      gap: 7px;
      margin: 0;
    }

    .status-dependency-card dl > div {
      display: grid;
      grid-template-columns: minmax(62px, 0.35fr) minmax(0, 1fr);
      gap: 10px;
      align-items: start;
      min-width: 0;
    }

    .status-dependency-card dt {
      color: var(--v2-muted);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
    }

    .status-dependency-card dd {
      min-width: 0;
      margin: 0;
      overflow-wrap: anywhere;
    }
  }
</style>
