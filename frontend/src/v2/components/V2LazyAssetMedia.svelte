<script lang="ts">
  import { Image as ImageIcon, ImageOff } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import { cachedThumbnail, type ThumbnailSource } from '../data/mediaThumbnailCache';

  let {
    cacheKey,
    resolve,
    alt = '',
    rootMargin = '320px 0px',
    onerror,
    onload,
  }: {
    cacheKey: string;
    resolve: () => ThumbnailSource;
    alt?: string;
    rootMargin?: string;
    onerror?: () => void;
    onload?: () => void;
  } = $props();

  let host = $state<HTMLSpanElement | null>(null);
  let source = $state<ThumbnailSource | null>(null);
  let failed = $state(false);
  let scheduled = false;
  let idleHandle: number | null = null;
  let timerHandle: ReturnType<typeof setTimeout> | null = null;

  const url = $derived(typeof source === 'string' ? source : source?.url ?? '');
  const videoSource = $derived(Boolean(url && /\.(mp4|webm)(?:$|\?)/i.test(url)));

  function resolveSource(): void {
    if (source || failed) return;
    try {
      source = cachedThumbnail(cacheKey, resolve);
    } catch {
      failed = true;
      onerror?.();
    }
  }

  function scheduleResolve(): void {
    if (scheduled || source || failed) return;
    scheduled = true;
    const requestIdle = (window as typeof window & { requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number }).requestIdleCallback;
    if (requestIdle) {
      idleHandle = requestIdle(() => resolveSource(), { timeout: 350 });
    } else {
      timerHandle = setTimeout(resolveSource, 0);
    }
  }

  function mediaError(): void {
    failed = true;
    onerror?.();
  }

  function mediaLoad(): void {
    onload?.();
  }

  onMount(() => {
    if (!host || typeof IntersectionObserver === 'undefined') {
      scheduleResolve();
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      scheduleResolve();
    }, { rootMargin });
    observer.observe(host);
    return () => {
      observer.disconnect();
      if (idleHandle !== null) {
        const cancelIdle = (window as typeof window & { cancelIdleCallback?: (handle: number) => void }).cancelIdleCallback;
        cancelIdle?.(idleHandle);
      }
      if (timerHandle !== null) clearTimeout(timerHandle);
    };
  });
</script>

<span bind:this={host} class="v2-lazy-asset-media" data-loaded={Boolean(url) && !failed} data-failed={failed || undefined} aria-busy={!url && !failed}>
  {#if failed}
    <span class="v2-lazy-asset-placeholder v2-lazy-asset-failed" role="img" aria-label="Preview unavailable">
      <ImageOff size={27} strokeWidth={1.8} aria-hidden="true"/>
      <small>Preview unavailable</small>
    </span>
  {:else if !url}
    <span class="v2-lazy-asset-placeholder" aria-hidden="true"><ImageIcon size={23}/></span>
  {:else if videoSource}
    <video src={url} muted playsinline preload="none" aria-hidden="true" onerror={mediaError} onloadeddata={mediaLoad}></video>
  {:else}
    <img src={url} {alt} loading="lazy" decoding="async" fetchpriority="low" draggable="false" onerror={mediaError} onload={mediaLoad}>
  {/if}
</span>

<style>
  .v2-lazy-asset-media{position:absolute;inset:0;display:block;width:100%;height:100%;min-width:0;min-height:0;background:#0d141d;overflow:hidden}
  .v2-lazy-asset-media img,.v2-lazy-asset-media video{display:block;width:100%;height:100%;object-fit:cover}
  .v2-lazy-asset-placeholder{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.4rem;color:var(--v2-muted);background:linear-gradient(135deg,#101923,#0c1219);opacity:.72;text-align:center;pointer-events:none}
  .v2-lazy-asset-placeholder small{font-size:.72rem;line-height:1.2}
  .v2-lazy-asset-failed{background:#0f1a27;color:#7f91a7;opacity:1}
</style>
