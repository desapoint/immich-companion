<script lang="ts">
  import V2PageHeader from './V2PageHeader.svelte';
  import V2Workspace from './V2Workspace.svelte';

  let {
    title,
    description = '',
    eyebrow = '',
    headerActions,
    tabs,
    context,
    children,
    inspector,
  }: {
    title: string;
    description?: string;
    eyebrow?: string;
    headerActions?: import('svelte').Snippet;
    tabs?: import('svelte').Snippet;
    context?: import('svelte').Snippet;
    children: import('svelte').Snippet;
    inspector?: import('svelte').Snippet;
  } = $props();
</script>

<div class="v2-page-host">
  <V2PageHeader {title} {description} {eyebrow} actions={headerActions} {tabs} />
  <V2Workspace {context} {inspector}>{@render children()}</V2Workspace>
</div>
