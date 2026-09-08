<script lang="ts">
  import { CheckCircle2, CircleAlert, Info, TriangleAlert, X } from '@lucide/svelte';
  import V2Button from './V2Button.svelte';
  import type { V2Toast } from '../state/toasts.svelte';

  let { toast, ondismiss, onaction }: { toast: V2Toast; ondismiss: () => void; onaction: () => void } = $props();
</script>

<article class="v2-toast" data-tone={toast.tone} role={toast.tone === 'error' ? 'alert' : 'status'} aria-atomic="true">
  <span class="v2-toast-icon" aria-hidden="true">
    {#if toast.tone === 'success'}<CheckCircle2 size={19}/>{:else if toast.tone === 'warning'}<TriangleAlert size={19}/>{:else if toast.tone === 'error'}<CircleAlert size={19}/>{:else}<Info size={19}/>{/if}
  </span>
  <div class="v2-toast-copy"><strong>{toast.title}</strong><span>{toast.message}</span>{#if toast.action}<V2Button onclick={onaction}>{toast.action.label}</V2Button>{/if}</div>
  <button type="button" class="v2-toast-close" aria-label={`Dismiss ${toast.title}`} onclick={ondismiss}><X size={17}/></button>
</article>

<style>
  .v2-toast{pointer-events:auto;width:min(24rem,calc(100vw - 1.5rem));display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:.65rem;align-items:start;padding:.8rem;border:1px solid var(--v2-line);border-radius:.75rem;background:color-mix(in srgb,var(--v2-surface,#111821) 96%,transparent);box-shadow:0 .75rem 2rem rgb(0 0 0/.28);color:var(--v2-text);backdrop-filter:blur(12px)}
  .v2-toast[data-tone="success"]{border-color:color-mix(in srgb,var(--v2-ok,#4caf50) 62%,var(--v2-line))}.v2-toast[data-tone="warning"]{border-color:color-mix(in srgb,var(--v2-warn,#f0ad4e) 68%,var(--v2-line))}.v2-toast[data-tone="error"]{border-color:color-mix(in srgb,var(--v2-danger,#e05a5a) 68%,var(--v2-line))}.v2-toast[data-tone="info"]{border-color:color-mix(in srgb,var(--v2-accent,#8b5cf6) 58%,var(--v2-line))}
  .v2-toast-icon{display:inline-flex;margin-top:.05rem}.v2-toast[data-tone="success"] .v2-toast-icon{color:var(--v2-ok,#74d296)}.v2-toast[data-tone="warning"] .v2-toast-icon{color:var(--v2-warn,#f0c56a)}.v2-toast[data-tone="error"] .v2-toast-icon{color:var(--v2-danger,#ff8585)}
  .v2-toast-copy{display:grid;gap:.2rem;min-width:0}.v2-toast-copy strong{font-size:.82rem}.v2-toast-copy span{font-size:.75rem;line-height:1.4;color:var(--v2-muted);overflow-wrap:anywhere}.v2-toast-copy :global(.v2-button){margin-top:.3rem;width:max-content}
  .v2-toast-close{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:.4rem;background:transparent;color:var(--v2-muted);padding:.15rem;cursor:pointer}.v2-toast-close:hover{background:color-mix(in srgb,currentColor 10%,transparent);color:var(--v2-text)}.v2-toast-close:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px}
</style>
