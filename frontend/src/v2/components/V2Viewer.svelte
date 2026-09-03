<script lang="ts">
  let { open=false, title='Asset Viewer', mode='assets', onclose }: { open?:boolean; title?:string; mode?:'assets'|'restore'|'duplicates'; onclose:()=>void } = $props();
</script>

<svelte:body class:v2-overlay-open={open}/>

{#if open}
<div class="v2-viewer" role="dialog" aria-modal="true" aria-label={title}>
  <div class="v2-viewer-top"><div class="v2-inline v2-inline-sm v2-inline-align-center"><button class="v2-button" onclick={onclose}>✕</button><b>{title}</b><span class="v2-badge">3 / 48</span></div><div class="v2-inline v2-inline-sm"><button class="v2-button">−</button><button class="v2-button">Fit</button><button class="v2-button">+</button><button class="v2-button">ⓘ</button><button class="v2-button">?</button></div></div>
  <div class="v2-viewer-stage"><div class="v2-image-stage"><div class="v2-fake-image"></div></div><aside class="v2-viewer-info">
    <section class="v2-section"><h3 class="v2-section-heading">Details</h3><div class="v2-card"><b>IMG_20260821_174512.jpg</b><p class="v2-small v2-muted">4032 × 3024 · JPEG · 4.8 MB</p></div></section>
    <section class="v2-section"><h3 class="v2-section-heading">Metadata</h3><div class="v2-card v2-small">Taken Aug 21, 2026<br>Samsung device<br>External library</div></section>
    <section class="v2-section"><h3 class="v2-section-heading">{mode==='restore'?'Restore boundary':mode==='duplicates'?'Comparison':'Asset actions'}</h3><div class="v2-card v2-small">{mode==='restore'?'Only restore, selection and shared viewing controls are exposed.':mode==='duplicates'?'Duplicate decisions persist to the parent group draft.':'Full mutation viewer with guarded plan/review actions.'}</div></section>
  </aside></div>
  <div class="v2-viewer-bottom"><button class="v2-button">← Previous</button><div class="v2-inline v2-inline-sm">{#if mode==='restore'}<button class="v2-button v2-button-primary">Restore visible</button>{:else if mode==='duplicates'}<button class="v2-button v2-button-primary">Keep</button><button class="v2-button">Delete</button><button class="v2-button">Stack</button><button class="v2-button">Primary</button><button class="v2-button">Reference</button>{:else}<button class="v2-button">Favorite</button><button class="v2-button">Archive</button><button class="v2-button">Analyze integrity</button><button class="v2-button v2-button-danger">Trash</button>{/if}</div><button class="v2-button">Next →</button></div>
</div>
{/if}
