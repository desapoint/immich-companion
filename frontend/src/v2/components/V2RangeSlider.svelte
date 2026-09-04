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
    valueLabel,
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
    valueLabel?: string;
  } = $props();

  const trackHeight = 8;
  const thumbSize = 20;
  const trackRadius = trackHeight / 2;
  const fraction = $derived(max === min ? 0 : Math.max(0, Math.min(1, (value - min) / (max - min))));
  const positionPx = $derived(trackRadius + fraction * Math.max(0, width - trackHeight));
  const spectrumColor = $derived(`hsl(${fraction * 360}deg 100% 50%)`);
</script>

<label class="v2-range-slider">
  {#if label}<span>{label}</span>{/if}
  {#if swatch}<i class="v2-range-swatch" style={`background:${swatch}`} aria-hidden="true"></i>{/if}
  <span
    class="v2-range-control"
    data-track={track}
    style={`--v2-range-width:${width}px;--v2-range-track-height:${trackHeight}px;--v2-range-track-radius:${trackRadius}px;--v2-range-thumb-size:${thumbSize}px;--v2-range-position:${positionPx}px;--v2-range-spectrum-color:${spectrumColor}`}
  >
    <span class="v2-range-track" aria-hidden="true"></span>
    <input
      type="range"
      {min}
      {max}
      {step}
      bind:value
      aria-label={ariaLabel ?? label}
    >
    <span class="v2-range-thumb" aria-hidden="true"></span>
  </span>
  <span class="v2-range-value">{valueLabel ?? `${value}${suffix}`}</span>
</label>

<style>
  .v2-range-slider{display:flex;align-items:center;gap:7px;font-size:11px;white-space:nowrap}
  .v2-range-control{position:relative;display:inline-flex;align-items:center;width:var(--v2-range-width);height:var(--v2-range-thumb-size);flex:0 0 var(--v2-range-width)}
  .v2-range-track{position:absolute;left:0;right:0;top:50%;height:var(--v2-range-track-height);transform:translateY(-50%);border-radius:999px;background:#263342;overflow:hidden;pointer-events:none}
  .v2-range-control[data-track="fill"] .v2-range-track{background:linear-gradient(90deg,#7ea6ff 0 var(--v2-range-position),#263342 var(--v2-range-position) 100%)}
  .v2-range-control[data-track="spectrum"] .v2-range-track{background:#ff0000}
  .v2-range-control[data-track="spectrum"] .v2-range-track::before{content:"";position:absolute;left:var(--v2-range-track-radius);right:var(--v2-range-track-radius);top:0;bottom:0;background:linear-gradient(90deg,#ff0000 0%,#ffff00 16.6667%,#00ff00 33.3333%,#00ffff 50%,#0000ff 66.6667%,#ff00ff 83.3333%,#ff0000 100%)}

  .v2-range-control input{position:absolute;inset:0;width:100%;height:100%;margin:0;padding:0;appearance:none;border:0;outline:none;background:transparent;cursor:pointer;z-index:2}
  .v2-range-control input::-webkit-slider-runnable-track{height:var(--v2-range-track-height);background:transparent;border:0}
  .v2-range-control input::-moz-range-track{height:var(--v2-range-track-height);background:transparent;border:0}
  .v2-range-control input::-webkit-slider-thumb{appearance:none;box-sizing:border-box;width:var(--v2-range-track-height);height:var(--v2-range-track-height);margin-top:0;border:0;border-radius:50%;background:transparent;box-shadow:none}
  .v2-range-control input::-moz-range-thumb{box-sizing:border-box;width:var(--v2-range-track-height);height:var(--v2-range-track-height);border:0;border-radius:50%;background:transparent;box-shadow:none}

  .v2-range-thumb{position:absolute;z-index:1;left:var(--v2-range-position);top:50%;width:var(--v2-range-thumb-size);height:var(--v2-range-thumb-size);box-sizing:border-box;border-radius:50%;background:#fff;border:3px solid #7ea6ff;box-shadow:0 2px 8px rgba(0,0,0,.45);pointer-events:none;transform:translate(-50%,-50%) scale(1);transform-origin:center;transition:transform 110ms ease,background 110ms ease}
  .v2-range-control[data-track="spectrum"] .v2-range-thumb{background:var(--v2-range-spectrum-color)}
  .v2-range-control input:active ~ .v2-range-thumb{transform:translate(-50%,-50%) scale(1.28)}
  .v2-range-control input:focus-visible ~ .v2-range-thumb{outline:2px solid #4169a8;outline-offset:2px}

  .v2-range-swatch{width:18px;height:18px;flex:0 0 18px;border-radius:50%;border:2px solid rgba(255,255,255,.8)}
  .v2-range-value{min-width:44px;text-align:center;background:#151f2a;border:1px solid #354557;border-radius:999px;padding:3px 7px;font-size:11px}

  @media (prefers-reduced-motion:reduce){.v2-range-thumb{transition:none}}
</style>
