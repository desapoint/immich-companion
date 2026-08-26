<script lang="ts">
  import { onMount, tick, type Snippet } from 'svelte';

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
  let dialog = $state<HTMLDialogElement>();
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
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  }

  function handleCancel(event: Event): void {
    event.preventDefault();
    if (closeOnEscape) onclose();
  }

  onMount(() => {
    const currentDialog = dialog;
    if (!currentDialog) return;
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    document.body.style.overflow = 'hidden';
    currentDialog.showModal();
    void tick().then(() => panel?.focus({ preventScroll: true }));
    return () => {
      if (currentDialog.open) currentDialog.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<dialog
  bind:this={dialog}
  class="dialog-modal"
  aria-labelledby={titleId}
  aria-describedby={description ? descriptionId : undefined}
  oncancel={handleCancel}
  onpointerdown={(event) => {
    if (closeOnBackdrop && event.target === event.currentTarget) onclose();
  }}
>
  <div
    bind:this={panel}
    class="dialog-panel"
    data-size={size}
    role="document"
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
</dialog>

<style>
  .dialog-modal {
    position: fixed;
    z-index: 900;
    inset: 0;
    width: 100vw;
    max-width: none;
    height: 100vh;
    height: 100dvh;
    max-height: none;
    margin: 0;
    padding: clamp(0.6rem, 2vw, 1.25rem);
    overflow: hidden;
    border: 0;
    background: transparent;
  }

  .dialog-modal[open] {
    display: grid;
    place-items: center;
  }

  .dialog-modal::backdrop {
    background: rgb(0 0 0 / 68%);
    backdrop-filter: blur(0.3rem);
  }

  .dialog-panel {
    display: grid;
    width: min(100%, 38rem);
    max-height: min(calc(100dvh - 2 * clamp(0.6rem, 2vw, 1.25rem)), 52rem);
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

  @media (max-width: 32rem) {
    .dialog-modal {
      padding: 0.5rem;
    }

    .dialog-panel {
      max-height: calc(100dvh - 1rem);
    }
  }
</style>
