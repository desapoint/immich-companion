<script lang="ts">
  let {
    label,
    value = $bindable(0),
    min = 0,
    max = 100,
    step = 1,
    suffix = '',
    track = 'fill',
    width = 160,
    swatch,
    ariaLabel,
  }: {
    label?: string;
    value?: number;
    min?: number;
    max?: number;
    step?: number;
    suffix?: string;
    track?: 'fill' | 'spectrum' | 'plain';
    width?: number;
    swatch?: string;
    ariaLabel?: string;
  } = $props();

  const percent = $derived(max === min ? 0 : Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100)));
</script>

<label class="v2-range-slider">
  {#if label}<span>{label}</span>{/if}
  {#if swatch}<i class="v2-range-swatch" style={`background:${swatch}`} aria-hidden="true"></i>{/if}
  <input
    type="range"
    {min}
    {max}
    {step}
    bind:value
    aria-label={ariaLabel ?? label}
    data-track={track}
    style={`--v2-range-pct:${percent}%;--v2-range-width:${width}px`}
  >
  <span class="v2-range-value">{value}{suffix}</span>
</label>

<style>
  .v2-range-slider{display:flex;align-items:center;gap:7px;font-size:11px;white-space:nowrap}
  .v2-range-slider input{appearance:none;width:var(--v2-range-width);height:8px;padding:0;border:0;border-radius:999px;outline:none;background:#263342}
  .v2-range-slider input[data-track="fill"]{background:linear-gradient(90deg,#7ea6ff 0 var(--v2-range-pct),#263342 var(--v2-range-pct) 100%)}
  .v2-range-slider input[data-track="spectrum"]{background:linear-gradient(90deg,#ff334f,#ffd633,#42e36f,#27d9ff,#5f72ff,#d94cff,#ff334f)}
  .v2-range-slider input::-webkit-slider-thumb{appearance:none;width:20px;height:20px;border-radius:50%;background:#fff;border:3px solid #7ea6ff;box-shadow:0 2px 8px rgba(0,0,0,.45);cursor:pointer}
  .v2-range-slider input::-moz-range-thumb{width:20px;height:20px;border-radius:50%;background:#fff;border:3px solid #7ea6ff;box-shadow:0 2px 8px rgba(0,0,0,.45);cursor:pointer}
  .v2-range-swatch{width:18px;height:18px;flex:0 0 18px;border-radius:50%;border:2px solid rgba(255,255,255,.8)}
  .v2-range-value{min-width:44px;text-align:center;background:#151f2a;border:1px solid #354557;border-radius:999px;padding:3px 7px;font-size:11px}
</style>
