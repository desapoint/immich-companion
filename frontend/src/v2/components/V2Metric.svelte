<script lang="ts">
  let { value, label, class: className = '' }: { value: string; label: string; class?: string } = $props();
</script>

<div class={`v2-card ${className}`.trim()}>
  <span class="v2-metric-value">{value}</span>
  <span class="v2-metric-label">{label}</span>
</div>
