<script lang="ts">
  import { onMount } from 'svelte';

  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import V2Field from '../../../lib/components/ui/TextField.svelte';
  import { comparisonAlignmentSettingsRepository } from '../../duplicates/api/comparisonAlignmentSettingsRepository';
  import type { ComparisonAlignmentSettings } from '../../duplicates/api/comparisonAlignmentSettingsRepository';

  let settings = $state<ComparisonAlignmentSettings | null>(null);
  let savedDisplacement = $state<number | null>(null);
  let savedRotation = $state<number | null>(null);
  let savedZoom = $state<number | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state('');
  let success = $state('');

  const dirty = $derived(
    settings !== null && savedDisplacement !== null && savedRotation !== null && savedZoom !== null &&
    (settings.maxDisplacementPercent !== savedDisplacement ||
      settings.maxRotationDegrees !== savedRotation || settings.maxZoomPercent !== savedZoom),
  );
  const valid = $derived(
    settings !== null && Number.isInteger(settings.maxDisplacementPercent) &&
    settings.maxDisplacementPercent >= 0 && settings.maxDisplacementPercent <= 50 &&
    Number.isInteger(settings.maxRotationDegrees) &&
    settings.maxRotationDegrees >= 0 && settings.maxRotationDegrees <= 30 &&
    Number.isInteger(settings.maxZoomPercent) && settings.maxZoomPercent >= 0 && settings.maxZoomPercent <= 50,
  );

  async function load(): Promise<void> {
    loading = true;
    error = '';
    try {
      settings = await comparisonAlignmentSettingsRepository.load();
      savedDisplacement = settings.maxDisplacementPercent;
      savedRotation = settings.maxRotationDegrees;
      savedZoom = settings.maxZoomPercent;
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Comparison alignment settings could not be loaded.';
    } finally {
      loading = false;
    }
  }

  async function save(): Promise<void> {
    if (!settings || !dirty || !valid || saving) return;
    saving = true;
    error = '';
    success = '';
    try {
      settings = await comparisonAlignmentSettingsRepository.save(settings);
      savedDisplacement = settings.maxDisplacementPercent;
      savedRotation = settings.maxRotationDegrees;
      savedZoom = settings.maxZoomPercent;
      success = 'Comparison alignment settings saved.';
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Comparison alignment settings could not be saved.';
    } finally {
      saving = false;
    }
  }

  function update(field: 'maxDisplacementPercent' | 'maxRotationDegrees' | 'maxZoomPercent', raw: string): void {
    const value = Number(raw);
    if (!settings || !Number.isFinite(value)) return;
    settings[field] = Math.trunc(value);
    success = '';
  }

  onMount(() => {
    void load();
  });
</script>

<V2Card title="Localized comparison alignment">
  {#snippet actions()}
    {#if settings}
      <V2Badge tone={dirty ? 'warn' : 'ok'} text={dirty ? 'Unsaved changes' : 'Saved'} />
    {/if}
  {/snippet}

  <V2Stack gap="sm">
    <span class="v2-small v2-muted">
      Limits how much the Local changes comparison can align frames before measuring differences.
      These settings apply to the comparison diagnostics and are shared through Companion.
    </span>
    {#if loading}
      <V2Notice>Loading comparison alignment settings…</V2Notice>
    {:else if settings}
      <V2Field
        label="Maximum frame displacement (%)"
        type="number"
        min="0"
        max="50"
        step="1"
        value={settings.maxDisplacementPercent}
        onchange={(value) => update('maxDisplacementPercent', value)}
      />
      <span class="v2-small v2-muted">
        Defaults to 10%. The comparison searches up to this fraction of the frame in each direction; 0 disables displacement compensation.
      </span>
      <V2Field
        label="Maximum frame rotation (degrees)"
        type="number"
        min="0"
        max="30"
        step="1"
        value={settings.maxRotationDegrees}
        onchange={(value) => update('maxRotationDegrees', value)}
      />
      <span class="v2-small v2-muted">
        Defaults to 0° (off). When enabled, the comparison checks whole-degree rotations up to 30° in either direction. Higher limits add comparison work and can align away camera roll.
      </span>
      <V2Field
        label="Maximum zoom compensation (%)"
        type="number"
        min="0"
        max="50"
        step="1"
        value={settings.maxZoomPercent}
        onchange={(value) => update('maxZoomPercent', value)}
      />
      <span class="v2-small v2-muted">
        Defaults to 0% (off). Allows the diagnostic to compensate for up to this much absolute scale difference, zooming the comparison frame in either direction.
      </span>
      {#if !valid}<V2Notice tone="warning">Use whole numbers: displacement 0–50%, rotation 0–30°, and zoom compensation 0–50%.</V2Notice>{/if}
      {#if error}<V2Notice tone="error">{error}</V2Notice>{/if}
      {#if success}<V2Notice tone="success">{success}</V2Notice>{/if}
      <div>
        <V2Button variant="primary" disabled={!dirty || !valid || saving} onclick={() => void save()}>
          {saving ? 'Saving…' : 'Save comparison settings'}
        </V2Button>
      </div>
    {:else}
      <V2Notice tone="error">{error || 'Comparison alignment settings are unavailable.'}</V2Notice>
      <div><V2Button onclick={() => void load()}>Retry</V2Button></div>
    {/if}
  </V2Stack>
</V2Card>
