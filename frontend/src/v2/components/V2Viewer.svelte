<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';

  let { open=false, title='Asset Viewer', mode='assets', onclose }: { open?:boolean; title?:string; mode?:'assets'|'restore'|'duplicates'; onclose:()=>void } = $props();
</script>

<svelte:body class:v2-overlay-open={open}/>

{#if open}
  <div class="v2-viewer" role="dialog" aria-modal="true" aria-label={title}>
    <div class="v2-viewer-top">
      <V2Inline gap="sm"><V2Button onclick={onclose}>✕</V2Button><b>{title}</b><V2Badge text="3 / 48"/></V2Inline>
      <V2Inline gap="sm"><V2Button>−</V2Button><V2Button>Fit</V2Button><V2Button>+</V2Button><V2Button>ⓘ</V2Button><V2Button>?</V2Button></V2Inline>
    </div>
    <div class="v2-viewer-stage">
      <div class="v2-image-stage"><div class="v2-fake-image"></div></div>
      <aside class="v2-viewer-info">
        <V2Section title="Details"><V2Card><b>IMG_20260821_174512.jpg</b><p class="v2-small v2-muted">4032 × 3024 · JPEG · 4.8 MB</p></V2Card></V2Section>
        <V2Section title="Metadata"><V2Card><span class="v2-small">Taken Aug 21, 2026<br>Samsung device<br>External library</span></V2Card></V2Section>
        <V2Section title={mode==='restore'?'Restore boundary':mode==='duplicates'?'Comparison':'Asset actions'}><V2Card><span class="v2-small">{mode==='restore'?'Only restore, selection and shared viewing controls are exposed.':mode==='duplicates'?'Duplicate decisions persist to the parent group draft.':'Full mutation viewer with guarded plan/review actions.'}</span></V2Card></V2Section>
      </aside>
    </div>
    <div class="v2-viewer-bottom">
      <V2Button>← Previous</V2Button>
      <V2Inline gap="sm">
        {#if mode==='restore'}
          <V2Button variant="primary">Restore visible</V2Button>
        {:else if mode==='duplicates'}
          <V2Button variant="primary">Keep</V2Button><V2Button>Delete</V2Button><V2Button>Stack</V2Button><V2Button>Primary</V2Button><V2Button>Reference</V2Button>
        {:else}
          <V2Button>Favorite</V2Button><V2Button>Archive</V2Button><V2Button>Analyze integrity</V2Button><V2Button variant="danger">Trash</V2Button>
        {/if}
      </V2Inline>
      <V2Button>Next →</V2Button>
    </div>
  </div>
{/if}
