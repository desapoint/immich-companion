<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2Modal from './V2Modal.svelte';

  let {
    id,
    title,
    message,
    onclose,
  }: {
    id: string;
    title: string;
    message: string;
    onclose: () => void;
  } = $props();
</script>

<V2Modal {id} {title} size="sm" {onclose}>
  <p>{message}</p>

  {#snippet footer()}
    <V2Button variant="primary" onclick={onclose}>Close</V2Button>
  {/snippet}
</V2Modal>

<style>
  p {
    margin: 0;
    line-height: 1.5;
  }
</style>
