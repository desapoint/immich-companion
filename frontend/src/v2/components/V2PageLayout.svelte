<script lang="ts">
  let {
    title,
    description,
    context,
    content,
    inspector,
  }: {
    title: string;
    description: string;
    context: import('svelte').Snippet;
    content: import('svelte').Snippet;
    inspector: import('svelte').Snippet;
  } = $props();
</script>

<div class="v2-page-host">
  <section class="v2-page-head">
    <div class="v2-head-row">
      <div class="v2-title">
        <span class="v2-zone">Page identity</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </div>
  </section>

  <section class="v2-workspace">
    <aside class="v2-context">{@render context()}</aside>
    <main class="v2-content">{@render content()}</main>
    <aside class="v2-inspector">{@render inspector()}</aside>
  </section>
</div>
