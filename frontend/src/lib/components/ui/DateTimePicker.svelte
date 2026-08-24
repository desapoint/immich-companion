<script lang="ts">
  interface Props {
    id: string;
    label: string;
    value: string;
    disabled?: boolean;
    required?: boolean;
    onchange: (value: string) => void;
  }

  let { id, label, value, disabled = false, required = false, onchange }: Props = $props();
</script>

<label>
  <span>{label}</span>
  <input
    {id}
    type="datetime-local"
    {value}
    {disabled}
    {required}
    onchange={(event) => onchange(event.currentTarget.value)}
  />
</label>

<style>
  label {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  span {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  input {
    width: 100%;
    min-width: 0;
    min-height: 2.55rem;
    padding: 0.56rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    font: inherit;
  }

  input:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  input:disabled {
    cursor: wait;
    opacity: 0.58;
  }
</style>
