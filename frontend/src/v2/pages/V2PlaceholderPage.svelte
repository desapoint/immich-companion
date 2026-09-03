<script lang="ts">
  import V2Card from '../components/V2Card.svelte';
  import V2Notice from '../components/V2Notice.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Zone from '../components/V2Zone.svelte';

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
    <V2Zone label="Context rail">
      <V2Section title="Demo context">
        <V2Card><div class="v2-small v2-muted">{contextText}</div></V2Card>
      </V2Section>
    </V2Zone>
  {/snippet}

  {#snippet content()}
    <V2Zone label="Primary content">
      <V2Notice>{contentText}</V2Notice>
      <V2Card>
        <V2Stack gap="sm">
          <b>{title} V2</b>
          <p class="v2-muted v2-small v2-text-block">This page remains intentionally static until its integration phase.</p>
        </V2Stack>
      </V2Card>
    </V2Zone>
  {/snippet}

  {#snippet inspector()}
    <V2Zone label="Inspector">
      <V2Section title="Demo inspector">
        <V2Card><div class="v2-small v2-muted">{inspectorText}</div></V2Card>
      </V2Section>
    </V2Zone>
  {/snippet}
</V2PageLayout>
