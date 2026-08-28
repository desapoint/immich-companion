<script lang="ts">
  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import type { SearchMode } from '../types/assets';

  interface Props {
    mode: SearchMode;
    onchange: (mode: SearchMode) => void;
  }

  let { mode, onchange }: Props = $props();
</script>

<div class="mode-control">
  <div class="mode-copy">
    <span>Search mode</span>
    <strong>{mode === 'expert' ? 'Expert rules' : 'Simple filters'}</strong>
  </div>
  <div class="mode-switch">
    <span>Simple</span>
    <Checkbox
      checked={mode === 'expert'}
      label="Use expert search mode"
      hiddenLabel
      variant="switch"
      onchange={(checked) => onchange(checked ? 'expert' : 'simple')}
    />
    <span>Expert</span>
  </div>
</div>

<style>
  .mode-control,
  .mode-switch {
    display: flex;
    align-items: center;
  }

  .mode-control {
    justify-content: space-between;
    gap: 1rem;
    padding-bottom: 0.85rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  .mode-copy {
    display: grid;
    gap: 0.14rem;
  }

  .mode-copy span {
    color: var(--color-ink-muted);
    font-size: 0.63rem;
    font-weight: 800;
    letter-spacing: 0.075em;
    text-transform: uppercase;
  }

  .mode-copy strong {
    font-size: 0.82rem;
  }

  .mode-switch {
    gap: 0.5rem;
    color: var(--color-ink-muted);
    cursor: pointer;
    font-size: 0.72rem;
    font-weight: 760;
  }

  @media (max-width: 34rem) {
    .mode-control {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
