<script lang="ts">
  let {
    text,
    class: className = '',
  }: {
    text: string;
    class?: string;
  } = $props();
</script>

<span class={`v2-zone ${className}`.trim()}>{text}</span>
