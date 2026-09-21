<script lang="ts">
  import V2RangeSlider from '../../../lib/components/ui/RangeSlider.svelte';

  let {
    value,
    onchange,
  }: {
    value: number | string;
    onchange: (value: number) => void;
  } = $props();
</script>

<div class="v2-perceptual-distance-setting">
  <V2RangeSlider
    label="Maximum dHash distance"
    min={0}
    max={64}
    step={1}
    {value}
    grow={true}
    valueLabel={`${value} / 64`}
    onchange={(next) => onchange(Number(next))}
  />
  <p class="v2-small v2-muted">
    This is the candidate-search gate. Lower values require more alike coarse image structure; higher values find broader candidates and can increase scan work. Final similarity validation still decides whether a candidate joins a group.
  </p>
  <table>
    <caption>Approximate dHash distance guide</caption>
    <thead><tr><th scope="col">Distance</th><th scope="col">Typical meaning</th></tr></thead>
    <tbody>
      <tr><th scope="row">0</th><td>Identical coarse brightness pattern, but not proof of identical files.</td></tr>
      <tr><th scope="row">1–4</th><td>Extremely similar structure.</td></tr>
      <tr><th scope="row">5–12</th><td>Strong near-duplicate candidate; 12 is the default.</td></tr>
      <tr><th scope="row">13–16</th><td>Noticeable differences, but potentially the same scene.</td></tr>
      <tr><th scope="row">17–24</th><td>Weaker resemblance and more false candidates.</td></tr>
      <tr><th scope="row">Around 32</th><td>Unrelated image hashes commonly cluster here.</td></tr>
      <tr><th scope="row">64</th><td>Every compared brightness relationship is reversed.</td></tr>
    </tbody>
  </table>
</div>

<style>
  .v2-perceptual-distance-setting{display:grid;gap:8px}
  p{margin:0;max-width:78ch}
  table{width:min(100%,720px);border-collapse:collapse;font-size:12px;color:var(--v2-text-muted,#aebac8)}
  caption{text-align:left;padding:3px 0 6px;font-weight:700;color:var(--v2-text,#f4f7fb)}
  th,td{padding:5px 8px;border:1px solid var(--v2-border,#354557);text-align:left;vertical-align:top}
  th{color:var(--v2-text,#f4f7fb);white-space:nowrap}
</style>
