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
  const thumbRadius = thumbSize / 2;
  const fraction = $derived(max === min ? 0 : Math.max(0, Math.min(1, (value - min) / (max - min))));
  const percent = $derived(fraction * 100);
  const positionPx = $derived(trackRadius + fraction * Math.max(0, width - trackHeight));
  const spectrumColor = $derived(`hsl(${fraction * 360}deg 100% 50%)`);
</script>

<label class="v2-range-slider">
  {#if label}<span>{label}</span>{/if}
  {#if swatch}<i class="v2-range-swatch" style={`background:${swatch}`} aria-hidden="true"></i>{/if}
  <span
    class="v2-range-control"
    data-track={track}
    style={`--v2-range-width:${width}px;--v2-range-track-height:${trackHeight}px;--v2-range-track-radius:${trackRadius}px;--v2-range-thumb-size:${thumbSize}px;--v2-range-thumb-offset:${thumbRadius - trackRadius}px;--v2-range-position:${positionPx}px;--v2-range-pct:${percent}%;--v2-range-spectrum-color:${spectrumColor}`}
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
  </span>
  <span class="v2-range-value">{valueLabel ?? `${value}${suffix}`}</span>
</label>

<style>
  .v2-range-slider{display:flex;align-items:center;gap:7px;font-size:11px;white-space:nowrap}
  .v2-range-control{position:relative;display:inline-flex;align-items:center;width:var(--v2-range-width);height:var(--v2-range-thumb-size);flex:0 0 var(--v2-range-width)}
  .v2-range-track{position:absolute;left:0;right:0;top:50%;height:var(--v2-range-track-height);transform:translateY(-50%);border-radius:999px;background:#263342;overflow:hidden;pointer-events:none}
  .v2-range-control[data-track="fill"] .v2-range-track{background:linear-gradient(90deg,#7ea6ff 0 var(--v2-range-position),#263342 var(--v2-range-position) 100%)}
  .v2-range-control[data-track="spectrum"] .v2-range-track{background:linear-gradient(90deg,
    hsl(0deg 100% 50%) 0 var(--v2-range-track-radius),
    hsl(0deg 100% 50%) var(--v2-range-track-radius),
    hsl(60deg 100% 50%) calc(var(--v2-range-track-radius) + (100% - 2 * var(--v2-range-track-radius)) * .166667),
    hsl(120deg 100% 50%) calc(var(--v2-range-track-radius) + (100% - 2 * var(--v2-range-track-radius)) * .333333),
    hsl(180deg 100% 50%) calc(var(--v2-range-track-radius) + (100% - 2 * var(--v2-range-track-radius)) * .5),
    hsl(240deg 100% 50%) calc(var(--v2-range-track-radius) + (100% - 2 * var(--v2-range-track-radius)) * .666667),
    hsl(300deg 100% 50%) calc(var(--v2-range-track-radius) + (100% - 2 * var(--v2-range-track-radius)) * .833333),
    hsl(360deg 100% 50%) calc(100% - var(--v2-range-track-radius)),
    hsl(360deg 100% 50%) calc(100% - var(--v2-range-track-radius)) 100%)}
  .v2-range-control input{position:absolute;top:50%;left:calc(-1 * var(--v2-range-thumb-offset));width:calc(100% + 2 * var(--v2-range-thumb-offset));height:var(--v2-range-thumb-size);margin:0;padding:0;transform:translateY(-50%);appearance:none;border:0;outline:none;background:transparent;cursor:pointer}
  .v2-range-control input::-webkit-slider-runnable-track{height:var(--v2-range-track-height);background:transparent;border:0}
  .v2-range-control input::-moz-range-track{height:var(--v2-range-track-height);background:transparent;border:0}
  .v2-range-control input::-webkit-slider-thumb{appearance:none;width:var(--v2-range-thumb-size);height:var(--v2-range-thumb-size);margin-top:calc((var(--v2-range-track-height) - var(--v2-range-thumb-size)) / 2);border-radius:50%;background:#fff;border:3px solid #7ea6ff;box-shadow:0 2px 8px rgba(0,0,0,.45);cursor:pointer;transform:scale(1);transform-origin:center;transition:transform 110ms ease,background 110ms ease}
  .v2-range-control input::-moz-range-thumb{width:var(--v2-range-thumb-size);height:var(--v2-range-thumb-size);box-sizing:border-box;border-radius:50%;background:#fff;border:3px solid #7ea6ff;box-shadow:0 2px 8px rgba(0,0,0,.45);cursor:pointer;transform:scale(1);transform-origin:center;transition:transform 110ms ease,background 110ms ease}
  .v2-range-control[data-track="spectrum"] input::-webkit-slider-thumb{background:var(--v2-range-spectrum-color)}
  .v2-range-control[data-track="spectrum"] input::-moz-range-thumb{background:var(--v2-range-spectrum-color)}
  .v2-range-control input:active::-webkit-slider-thumb{transform:scale(1.28)}
  .v2-range-control input:active::-moz-range-thumb{transform:scale(1.28)}
  .v2-range-control input:focus-visible::-webkit-slider-thumb{outline:2px solid #4169a8;outline-offset:2px}
  .v2-range-control input:focus-visible::-moz-range-thumb{outline:2px solid #4169a8;outline-offset:2px}
  .v2-range-swatch{width:18px;height:18px;flex:0 0 18px;border-radius:50%;border:2px solid rgba(255,255,255,.8)}
  .v2-range-value{min-width:44px;text-align:center;background:#151f2a;border:1px solid #354557;border-radius:999px;padding:3px 7px;font-size:11px}

  @media (prefers-reduced-motion:reduce){
    .v2-range-control input::-webkit-slider-thumb,.v2-range-control input::-moz-range-thumb{transition:none}
  }
</style>
