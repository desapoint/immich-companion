<script lang="ts">
  import type { StatusLoadState } from '../../features/status/types/status';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Metric from '../components/V2Metric.svelte';
  import V2Notice from '../components/V2Notice.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Table from '../components/V2Table.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { companionState, dependencyState, immichVersion } from './statusPresentation';

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

    <V2Toolbar label="Primary content">
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
        <V2Table>
          <thead><tr><th>Service</th><th>Status</th><th>Version</th><th>Details</th></tr></thead>
          <tbody>
            <tr><td>Immich API</td><td><V2Badge tone={immich.tone} text={immich.label} /></td><td>{immichVersion(snapshot)}</td><td>{immichDep.detail ?? (immichDep.configured ? 'Configured' : 'Not configured')}</td></tr>
            <tr><td>Companion API</td><td><V2Badge tone={companion.tone} text={companion.label} /></td><td>{snapshot.version.version}</td><td>{snapshot.health.status}</td></tr>
            <tr><td>Database</td><td><V2Badge tone={database.tone} text={database.label} /></td><td>—</td><td>{databaseDep.detail ?? (databaseDep.configured ? 'Configured' : 'Not configured')}</td></tr>
          </tbody>
        </V2Table>
      </V2Card>
    </V2Section>
  {/if}
</V2Zone>
