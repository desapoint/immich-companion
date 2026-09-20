<script lang="ts">
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import { TOAST_POSITIONS, type ToastPosition } from '../../../app/state/toasts.svelte';

  let { toastPosition, ontoastpositionchange, onopenplayground }: {
    toastPosition: ToastPosition;
    ontoastpositionchange?: (position: ToastPosition) => void;
    onopenplayground?: () => void;
  } = $props();
</script>

<div class="v2-setting-grid">
  <V2Card title="Action notifications">
    {#snippet actions()}<V2Badge tone="ok" text="Saved locally" />{/snippet}
    <V2Stack gap="sm">
      <span class="v2-small v2-muted">Choose which corner anchors standard action success, warning and error toasts.</span>
      <SelectField id="settings-toast-position" label="Toast position" value={toastPosition} options={TOAST_POSITIONS} onchange={(value) => ontoastpositionchange?.(value as ToastPosition)} />
      <span class="v2-small v2-muted">Top positions stack downward; bottom positions grow upward.</span>
    </V2Stack>
  </V2Card>
  <V2Card title="Component playground">
    {#snippet actions()}<V2Button variant="primary" onclick={() => onopenplayground?.()}>Open playground</V2Button>{/snippet}
    <V2Stack gap="sm">
      <span class="v2-small v2-muted">Open the static V2 component reference. It behaves the same in demo and live modes and never mutates backend data.</span>
    </V2Stack>
  </V2Card>
</div>
