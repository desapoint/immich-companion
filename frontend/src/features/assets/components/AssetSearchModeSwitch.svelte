<script lang="ts">
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
  <label class="mode-switch">
    <span>Simple</span>
    <input
      type="checkbox"
      role="switch"
      aria-label="Use expert search mode"
      checked={mode === 'expert'}
      onchange={(event) => onchange(event.currentTarget.checked ? 'expert' : 'simple')}
    />
    <span class="switch-track" aria-hidden="true"><span></span></span>
    <span>Expert</span>
  </label>
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

  input {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .switch-track {
    display: flex;
    width: 2.8rem;
    height: 1.55rem;
    align-items: center;
    padding: 0.16rem;
    border: 1px solid var(--color-border-strong);
    border-radius: 999px;
    background: var(--color-surface-soft);
    transition: border-color 140ms ease, background 140ms ease;
  }

  .switch-track span {
    width: 1.08rem;
    height: 1.08rem;
    border-radius: 50%;
    background: var(--color-ink-muted);
    box-shadow: 0 0.1rem 0.3rem rgb(0 0 0 / 18%);
    transition: transform 140ms ease, background 140ms ease;
  }

  input:checked + .switch-track {
    border-color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 18%, var(--color-surface-soft));
  }

  input:checked + .switch-track span {
    background: var(--color-accent-strong);
    transform: translateX(1.2rem);
  }

  input:focus-visible + .switch-track {
    outline: 0.18rem solid var(--color-accent-strong);
    outline-offset: 0.18rem;
  }

  @media (max-width: 34rem) {
    .mode-control {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
