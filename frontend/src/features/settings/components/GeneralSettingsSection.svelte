<script lang="ts">
  import SelectField from '../../../v2/components/SelectField.svelte';
  import V2Badge from '../../../v2/components/V2Badge.svelte';
  import V2Button from '../../../v2/components/V2Button.svelte';
  import V2Card from '../../../v2/components/V2Card.svelte';
  import V2Segmented from '../../../v2/components/V2Segmented.svelte';
  import V2Stack from '../../../v2/components/V2Stack.svelte';
  import { V2_TOAST_POSITIONS, type V2ToastPosition } from '../../../v2/state/toasts.svelte';
  import type { V2Density } from '../../../v2/state/density';

  let { density, toastPosition, ondensitychange, ontoastpositionchange, onopenplayground }: {
    density: V2Density;
    toastPosition: V2ToastPosition;
    ondensitychange: (density: V2Density) => void;
    ontoastpositionchange?: (position: V2ToastPosition) => void;
    onopenplayground?: () => void;
  } = $props();
</script>

<div class="v2-setting-grid">
  <V2Card title="Interface density">
    {#snippet actions()}<V2Badge tone="ok" text="Saved locally" />{/snippet}
    <V2Stack gap="sm">
      <span class="v2-small v2-muted">Controls spacing, table row height, card padding and grid thumbnail density throughout V2.</span>
      <V2Segmented items={['Standard', 'Condensed']} active={density === 'standard' ? 'Standard' : 'Condensed'} onselect={(value) => ondensitychange(value === 'Standard' ? 'standard' : 'condensed')} ariaLabel="Interface density" />
      <span class="v2-small v2-muted">The preference is applied immediately and retained across pages and browser reloads.</span>
    </V2Stack>
  </V2Card>
  <V2Card title="Action notifications">
    {#snippet actions()}<V2Badge tone="ok" text="Saved locally" />{/snippet}
    <V2Stack gap="sm">
      <span class="v2-small v2-muted">Choose which corner anchors standard action success, warning and error toasts.</span>
      <SelectField id="settings-toast-position" label="Toast position" value={toastPosition} options={V2_TOAST_POSITIONS} onchange={(value) => ontoastpositionchange?.(value as V2ToastPosition)} />
      <span class="v2-small v2-muted">Top positions place each latest notification below the previous one; bottom positions grow upward.</span>
    </V2Stack>
  </V2Card>
  <V2Card title="Component playground">
    <V2Stack gap="sm">
      <span class="v2-small v2-muted">Open the static V2 component reference. It behaves the same in demo and live modes and never mutates backend data.</span>
      <div><V2Button variant="primary" onclick={() => onopenplayground?.()}>Open playground</V2Button></div>
    </V2Stack>
  </V2Card>
</div>
