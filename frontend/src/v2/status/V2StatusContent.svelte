<script lang="ts">
  import type { StatusLoadState } from '../../features/status/types/status';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Metric from '../components/V2Metric.svelte';
  import V2Notice from '../components/V2Notice.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2ZoneLabel from '../components/V2ZoneLabel.svelte';
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
        <div><button class="v2-button v2-button-primary" onclick={onrefresh}>Retry</button></div>
      </V2Stack>
    </V2Notice>
  {:else}
    {@const snapshot = state.snapshot}
    {@const companion = companionState(snapshot)}
    {@const immichDep = snapshot.health.dependencies.immich}
    {@const databaseDep = snapshot.health.dependencies.companion_database}
    {@const immich = dependencyState(immichDep, 'Connected')}
    {@const database = dependencyState(databaseDep, 'Ready')}

    <V2Inline justify="between" align="start" wrap={true} gap="md">
      <V2Inline gap="sm" wrap={true}>
        <V2ZoneLabel text="Primary content" />
        <b>System overview</b>
      </V2Inline>
      <button class="v2-button" onclick={onrefresh}>Refresh view</button>
    </V2Inline>

    <div class="v2-metric-grid">
      <V2Metric value={companion.label} label="Companion backend" />
      <V2Metric value={immich.label} label="Immich dependency" />
      <V2Metric value={String(snapshot.capabilities.implemented.length)} label="Capabilities" />
      <V2Metric value={immichVersion(snapshot)} label="Immich version" />
    </div>

    <V2Section title="Dependencies">
      <V2Card>
        <div class="v2-table-wrap">
          <table class="v2-table">
            <thead>
              <tr>
                <th class="v2-table-heading">Service</th>
                <th class="v2-table-heading">Status</th>
                <th class="v2-table-heading">Version</th>
                <th class="v2-table-heading">Details</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="v2-table-cell">Immich API</td>
                <td class="v2-table-cell"><V2Badge tone={immich.tone} text={immich.label} /></td>
                <td class="v2-table-cell">{immichVersion(snapshot)}</td>
                <td class="v2-table-cell">{immichDep.detail ?? (immichDep.configured ? 'Configured' : 'Not configured')}</td>
              </tr>
              <tr>
                <td class="v2-table-cell">Companion API</td>
                <td class="v2-table-cell"><V2Badge tone={companion.tone} text={companion.label} /></td>
                <td class="v2-table-cell">{snapshot.version.version}</td>
                <td class="v2-table-cell">{snapshot.health.status}</td>
              </tr>
              <tr>
                <td class="v2-table-cell">Database</td>
                <td class="v2-table-cell"><V2Badge tone={database.tone} text={database.label} /></td>
                <td class="v2-table-cell">—</td>
                <td class="v2-table-cell">{databaseDep.detail ?? (databaseDep.configured ? 'Configured' : 'Not configured')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </V2Card>
    </V2Section>
  {/if}
</V2Zone>
