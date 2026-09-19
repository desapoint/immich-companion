<script lang="ts">
  import { CircleAlert, CircleCheck, Info, TriangleAlert } from '@lucide/svelte';

  export type NoticeTone = 'info' | 'success' | 'warning' | 'error';

  let {
    tone = 'info',
    title = '',
    children,
    class: className = '',
  }: {
    tone?: NoticeTone;
    title?: string;
    children?: import('svelte').Snippet;
    class?: string;
  } = $props();

  const semanticRole = $derived(tone === 'error' ? 'alert' : 'status');
  const liveMode = $derived(tone === 'error' ? 'assertive' : 'polite');
</script>

<div
  class={`v2-notice ${className}`.trim()}
  data-tone={tone}
  role={semanticRole}
  aria-live={liveMode}
  aria-atomic="true"
>
  <span class="v2-notice-icon" aria-hidden="true">
    {#if tone === 'success'}
      <CircleCheck size={18}/>
    {:else if tone === 'warning'}
      <TriangleAlert size={18}/>
    {:else if tone === 'error'}
      <CircleAlert size={18}/>
    {:else}
      <Info size={18}/>
    {/if}
  </span>
  <div class="v2-notice-copy">
    {#if title}<strong class="v2-notice-title">{title}</strong>{/if}
    {#if children}<div class="v2-notice-content">{@render children()}</div>{/if}
  </div>
</div>
