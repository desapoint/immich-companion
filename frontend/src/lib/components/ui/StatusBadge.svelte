<script lang="ts">
  import type { StatusTone } from '../../types/ui';

  interface Props {
    label: string;
    tone?: StatusTone;
  }

  let { label, tone = 'neutral' }: Props = $props();
</script>

<span class="badge" class:positive={tone === 'positive'} class:warning={tone === 'warning'} class:negative={tone === 'negative'}>
  <span class="indicator" aria-hidden="true"></span>
  {label}
</span>

<style>
  .badge {
    display: inline-flex;
    min-height: 1.85rem;
    align-items: center;
    gap: 0.45rem;
    padding: 0.25rem 0.65rem;
    border: 1px solid var(--color-border-strong);
    border-radius: 999px;
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    line-height: 1;
    text-transform: uppercase;
  }

  .indicator {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 0 0.2rem color-mix(in srgb, currentColor 13%, transparent);
  }

  .positive {
    border-color: var(--color-positive-border);
    color: var(--color-positive-ink);
    background: var(--color-positive-surface);
  }

  .warning {
    border-color: var(--color-warning-border);
    color: var(--color-warning-ink);
    background: var(--color-warning-surface);
  }

  .negative {
    border-color: var(--color-negative-border);
    color: var(--color-negative-ink);
    background: var(--color-negative-surface);
  }
</style>
