<script lang="ts">
  import { X } from '@lucide/svelte';
  import { onMount, tick } from 'svelte';
  import V2Button from './V2Button.svelte';

  type ModalRuntime = { nextId: number; stack: number[] };
  type ModalSize = 'sm' | 'md' | 'lg' | 'xl';

  let {
    id,
    title,
    description = '',
    size = 'md',
    draggable = true,
    dismissOnBackdrop = false,
    onclose,
    headerActions,
    children,
    footer,
  }: {
    id: string;
    title: string;
    description?: string;
    size?: ModalSize;
    draggable?: boolean;
    dismissOnBackdrop?: boolean;
    onclose?: () => void;
    headerActions?: import('svelte').Snippet;
    children: import('svelte').Snippet;
    footer?: import('svelte').Snippet;
  } = $props();

  let modalId = $state(0);
  let positioned = $state(false);
  let x = $state(0);
  let y = $state(0);
  let dragging = $state(false);
  let dragStartX = 0;
  let dragStartY = 0;
  let originX = 0;
  let originY = 0;
  let dialog = $state<HTMLDivElement>();

  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;

  function getRuntime(): ModalRuntime {
    const target = window as Window & { __v2ModalRuntime?: ModalRuntime };
    target.__v2ModalRuntime ??= { nextId: 1, stack: [] };
    return target.__v2ModalRuntime;
  }

  function isTopModal(): boolean {
    const stack = getRuntime().stack;
    return stack[stack.length - 1] === modalId;
  }

  function clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), Math.max(min, max));
  }

  function keepVisible(): void {
    if (!dialog) return;
    const margin = 12;
    const rect = dialog.getBoundingClientRect();
    x = clamp(x, margin, window.innerWidth - rect.width - margin);
    y = clamp(y, margin, window.innerHeight - rect.height - margin);
  }

  function center(): void {
    if (!dialog) return;
    const rect = dialog.getBoundingClientRect();
    x = Math.max(12, (window.innerWidth - rect.width) / 2);
    y = Math.max(12, (window.innerHeight - rect.height) / 2);
    positioned = true;
    keepVisible();
  }

  function handlePointerDown(event: PointerEvent): void {
    if (!draggable || event.button !== 0) return;
    if ((event.target as HTMLElement).closest('button,input,select,textarea,a')) return;
    dragging = true;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    originX = x;
    originY = y;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
  }

  function handlePointerMove(event: PointerEvent): void {
    if (!dragging) return;
    x = originX + event.clientX - dragStartX;
    y = originY + event.clientY - dragStartY;
    keepVisible();
  }

  function handlePointerUp(event: PointerEvent): void {
    if (!dragging) return;
    dragging = false;
    (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId);
    keepVisible();
  }

  function handleDialogKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Tab' || !isTopModal() || !dialog) return;
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex]:not([tabindex="-1"])'))
      .filter((element) => element.offsetParent !== null);
    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function handleWindowKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && isTopModal()) {
      event.preventDefault();
      onclose?.();
    }
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (dismissOnBackdrop && event.target === event.currentTarget && isTopModal()) onclose?.();
  }

  onMount(() => {
    const runtime = getRuntime();
    modalId = runtime.nextId++;
    runtime.stack.push(modalId);
    document.body.classList.add('v2-overlay-open');
    const onResize = () => keepVisible();
    window.addEventListener('resize', onResize);
    void tick().then(() => {
      center();
      dialog?.focus();
    });
    return () => {
      window.removeEventListener('resize', onResize);
      const index = runtime.stack.indexOf(modalId);
      if (index >= 0) runtime.stack.splice(index, 1);
      if (!runtime.stack.length) document.body.classList.remove('v2-overlay-open');
    };
  });
</script>

<svelte:window onkeydown={handleWindowKeydown} />

<div
  class="v2-modal-layer"
  style={`z-index:${100 + modalId * 2}`}
  role="presentation"
  onclick={handleBackdropClick}
>
  <div
    bind:this={dialog}
    class="v2-modal"
    data-size={size}
    data-positioned={positioned || undefined}
    data-dragging={dragging || undefined}
    role="dialog"
    aria-modal="true"
    aria-labelledby={titleId}
    aria-describedby={description ? descriptionId : undefined}
    tabindex="-1"
    style={positioned ? `left:${x}px;top:${y}px` : undefined}
    onkeydown={handleDialogKeydown}
  >
    <header
      class="v2-modal-header"
      data-draggable={draggable || undefined}
      onpointerdown={handlePointerDown}
      onpointermove={handlePointerMove}
      onpointerup={handlePointerUp}
      onpointercancel={handlePointerUp}
    >
      <div class="v2-modal-heading">
        <h2 id={titleId}>{title}</h2>
        {#if description}<p id={descriptionId}>{description}</p>{/if}
      </div>
      <div class="v2-modal-header-actions">
        {#if headerActions}{@render headerActions()}{/if}
        <V2Button ariaLabel={`Close ${title}`} title="Close" onclick={onclose}><X size={18} /></V2Button>
      </div>
    </header>

    <div class="v2-modal-content">{@render children()}</div>

    {#if footer}<footer class="v2-modal-footer">{@render footer()}</footer>{/if}
  </div>
</div>
