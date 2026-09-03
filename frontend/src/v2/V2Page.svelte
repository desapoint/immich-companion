<script lang="ts">
  import demoHtml from './demo.html?raw';
</script>

<svelte:head>
  <title>Immich Companion V2</title>
</svelte:head>

<iframe class="v2-demo" title="Immich Companion V2 demo shell" srcdoc={demoHtml}></iframe>

<style>
  .v2-demo {
    display: block;
    width: 100vw;
    height: 100vh;
    border: 0;
    background: #0b1016;
  }
</style>
