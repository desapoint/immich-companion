<script lang="ts">
  import { Star } from '@lucide/svelte';

  let {
    selected = false,
    disabled = false,
    onclick,
  }: {
    selected?: boolean;
    disabled?: boolean;
    onclick?: () => void;
  } = $props();
</script>

<button
  class="v2-stack-primary-control"
  class:selected
  type="button"
  {disabled}
  aria-label={selected ? 'Selected as stack primary' : 'Set as stack primary'}
  aria-pressed={selected}
  title={selected ? 'Stack primary' : 'Set as stack primary'}
  onclick={(event) => { event.stopPropagation(); onclick?.(); }}
  onpointerdown={(event) => event.stopPropagation()}
>
  <Star size={17} fill={selected ? 'currentColor' : 'none'} aria-hidden="true" />
</button>

<style>
  .v2-stack-primary-control {
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
    border: 1px solid color-mix(in srgb, white 62%, transparent);
    border-radius: 8px;
    background: rgba(10, 15, 21, .68);
    color: white;
    cursor: pointer;
  }
  .v2-stack-primary-control:hover:not(:disabled) { background: rgba(22, 31, 43, .92); border-color: white; }
  .v2-stack-primary-control.selected { color: #ffd166; border-color: color-mix(in srgb, #ffd166 75%, white); }
  .v2-stack-primary-control:focus-visible { outline: 2px solid white; outline-offset: 1px; }
  .v2-stack-primary-control:disabled { opacity: .5; cursor: not-allowed; }
</style>
