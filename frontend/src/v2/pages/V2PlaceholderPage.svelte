<script lang="ts">
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Ui from '../components/V2Ui.svelte';

  let {
    title,
    description,
    contextText,
    contentText,
    inspectorText,
  }: {
    title: string;
    description: string;
    contextText: string;
    contentText: string;
    inspectorText: string;
  } = $props();
</script>

<V2PageLayout {title} {description}>
  {#snippet context()}
    <span class="v2-zone">Context rail</span>
    <V2Ui kind="section" title="Demo context"><V2Ui kind="card"><div class="v2-small v2-muted">{contextText}</div></V2Ui></V2Ui>
  {/snippet}

  {#snippet content()}
    <V2Ui kind="notice">{contentText}</V2Ui>
    <div class="v2-demo-page">
      <V2Ui kind="card"><b>{title} V2</b><p class="v2-muted v2-small">This page remains intentionally static until its integration phase.</p></V2Ui>
    </div>
  {/snippet}

  {#snippet inspector()}
    <span class="v2-zone">Inspector</span>
    <V2Ui kind="section" title="Demo inspector"><V2Ui kind="card"><div class="v2-small v2-muted">{inspectorText}</div></V2Ui></V2Ui>
  {/snippet}
</V2PageLayout>
