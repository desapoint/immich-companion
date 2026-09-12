<script lang="ts">
  import { X } from '@lucide/svelte';
  import V2Button from './V2Button.svelte';
  import V2Notice from './V2Notice.svelte';
  import type { V2Toast } from '../state/toasts.svelte';

  let { toast, ondismiss, onaction }: { toast: V2Toast; ondismiss: () => void; onaction: () => void } = $props();
</script>

<article class="v2-toast" data-tone={toast.tone} role={toast.tone === 'error' ? 'alert' : 'status'} aria-atomic="true">
  <V2Notice tone={toast.tone} title={toast.title} class="v2-toast-notice">
    <span>{toast.message}</span>
    {#if toast.action}<V2Button onclick={onaction}>{toast.action.label}</V2Button>{/if}
  </V2Notice>
  <button type="button" class="v2-toast-close" aria-label={`Dismiss ${toast.title}`} onclick={ondismiss}><X size={17}/></button>
</article>

<style>
  .v2-toast{pointer-events:auto;position:relative;width:min(32rem,calc(100vw - 1.5rem));font-family:var(--font-sans);filter:drop-shadow(0 .75rem 1.35rem rgb(0 0 0/.28))}
  .v2-toast :global(.v2-toast-notice){width:100%;box-sizing:border-box;padding-right:2.7rem;font-family:inherit}
  .v2-toast :global(.v2-toast-notice .v2-notice-title),.v2-toast :global(.v2-toast-notice .v2-notice-content),.v2-toast :global(.v2-toast-notice .v2-button){font-family:inherit}
  .v2-toast :global(.v2-toast-notice .v2-notice-content){display:grid;gap:.55rem}
  .v2-toast :global(.v2-toast-notice .v2-button){width:max-content}
  .v2-toast-close{position:absolute;right:.65rem;top:.65rem;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:.4rem;background:transparent;padding:.18rem;cursor:pointer;opacity:.92;font:inherit}
  .v2-toast[data-tone="info"] .v2-toast-close{color:#cfe0ff}.v2-toast[data-tone="success"] .v2-toast-close{color:#aeeac5}.v2-toast[data-tone="warning"] .v2-toast-close{color:#f5d485}.v2-toast[data-tone="error"] .v2-toast-close{color:#ffb1b1}
  .v2-toast-close:hover{background:rgb(255 255 255/.11);opacity:1}.v2-toast-close:focus-visible{outline:2px solid currentColor;outline-offset:2px}
</style>
