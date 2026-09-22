<script lang="ts">
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
</script>

<V2Section title="Large libraries">
  <V2Stack gap="sm">
    <span class="v2-small">Start with <b>95%</b> similarity, <b>8</b> candidates per image, and <b>5,000</b> retained matches.</span>
    <span class="v2-small v2-muted">Raise candidates when expected matches are missing. Raise retained matches when a completed scan explicitly reports that the retention limit was reached.</span>
  </V2Stack>
</V2Section>
