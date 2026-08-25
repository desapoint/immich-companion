<script lang="ts">
  import { tick, type Snippet } from 'svelte';

  import IconButton from './IconButton.svelte';

  interface Props {
    title: string;
    children: Snippet;
    footer?: Snippet;
    description?: string;
    size?: 'small' | 'medium' | 'large';
    closeOnBackdrop?: boolean;
    closeOnEscape?: boolean;
    onclose: () => void;
  }

  let {
    title,
    children,
    footer,
    description,
    size = 'medium',
    closeOnBackdrop = true,
    closeOnEscape = true,
    onclose,
  }: Props = $props();
  let panel = $state<HTMLElement>();
  const componentId = $props.id();
  const titleId = `${componentId}-title`;
  const descriptionId = `${componentId}-description`;

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && closeOnEscape) {
      event.preventDefault();
      onclose();
    } else if (event.key === 'Tab' && panel) {
      const focusable = [...panel.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex="-1"])',
      )];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  }

  $effect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    document.body.style.overflow = 'hidden';
    void tick().then(() => {
      panel?.querySelector<HTMLElement>('button:not(:disabled), input:not(:disabled)')?.focus();
    });
    return () => {
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="dialog-backdrop"
  role="presentation"
  onpointerdown={(event) => {
    if (closeOnBackdrop && event.target === event.currentTarget) onclose();
  }}
>
  <div
    bind:this={panel}
    class="dialog-panel"
    data-size={size}
    role="dialog"
    aria-modal="true"
    aria-labelledby={titleId}
    aria-describedby={description ? descriptionId : undefined}
    tabindex="-1"
  >
    <header>
      <div>
        <h2 id={titleId}>{title}</h2>
        {#if description}<p id={descriptionId}>{description}</p>{/if}
      </div>
      <IconButton icon="close" label="Close dialog" size="compact" onclick={onclose} />
    </header>
    <div class="dialog-content">{@render children()}</div>
    {#if footer}<footer>{@render footer()}</footer>{/if}
  </div>
</div>

<style>
  .dialog-backdrop {
    position: fixed;
    z-index: 900;
    inset: 0;
    display: grid;
    padding: 1rem;
    place-items: center;
    background: rgb(6 12 9 / 64%);
    backdrop-filter: blur(0.3rem);
  }

  .dialog-panel {
    display: grid;
    width: min(100%, 38rem);
    max-height: min(90vh, 52rem);
    grid-template-rows: auto minmax(0, 1fr) auto;
    overflow: hidden;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: 0 1.5rem 4.5rem rgb(5 12 8 / 35%);
  }

  .dialog-panel[data-size='small'] { width: min(100%, 30rem); }
  .dialog-panel[data-size='large'] { width: min(100%, 58rem); }

  header,
  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1rem;
  }

  header { border-bottom: 1px solid var(--color-border-subtle); }
  footer { border-top: 1px solid var(--color-border-subtle); }

  h2,
  p { margin: 0; }
  h2 { font-size: 1rem; }
  p { margin-top: 0.2rem; color: var(--color-ink-muted); font-size: 0.72rem; }

  .dialog-content {
    min-height: 0;
    padding: 1rem;
    overflow: auto;
    overscroll-behavior: contain;
  }
</style>
