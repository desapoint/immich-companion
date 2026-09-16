<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Card from './V2Card.svelte';
  import V2Notice from './V2Notice.svelte';
  import V2PageLayout from './V2PageLayout.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2Zone from './V2Zone.svelte';

  let {
    title,
    description = 'This V2 surface is visible for layout and navigation work, but its live implementation is intentionally disabled for now.',
  }: {
    title: string;
    description?: string;
  } = $props();
</script>

<V2PageLayout
  {title}
  description="V2 implementation boundary"
>
  <V2Zone>
    <V2Card title="Implementation not done yet">
      {#snippet actions()}<V2Badge tone="warn" text="Live actions disabled" />{/snippet}
      <V2Stack gap="sm">
        <V2Notice tone="warning" title="This feature is not live yet">
          {description}
        </V2Notice>
        <span class="v2-small v2-muted">
          Synchronization and synchronization configuration are the only V2 workflows currently allowed to call the live backend.
        </span>
      </V2Stack>
    </V2Card>
  </V2Zone>
</V2PageLayout>
