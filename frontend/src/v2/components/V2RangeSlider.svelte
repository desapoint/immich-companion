<script lang="ts">
  let {
    label,
    min = 0,
    max = 100,
    step = 1,
    value = $bindable<number | string>(0),
    numericValue = $bindable<number>(min),
    normalizedValue = $bindable<number>(0),
    suffix = '',
    track = 'fill',
    width = 160,
    trackHeight = 8,
    thumbSize = 20,
    thumbWidth,
    thumbHeight,
    thumbDraggingWidth,
    thumbDraggingHeight,
    thumbRadius = '50%',
    thumbDraggingRadius,
    thumbBorderWidth = 3,
    hitHeight = 24,
    swatch,
    ariaLabel,
    valueLabel,
    onchange,
    onnumericchange,
    onnormalizedchange,
  }: {
    label?: string;
    min?: number;
    max?: number;
    step?: number;
    value?: number | string;
    numericValue?: number;
    normalizedValue?: number;
    suffix?: string;
    track?: 'fill' | 'spectrum' | 'plain';
    width?: number;
    trackHeight?: number;
    thumbSize?: number;
    thumbWidth?: number;
    thumbHeight?: number;
    thumbDraggingWidth?: number;
    thumbDraggingHeight?: number;
    thumbRadius?: string;
    thumbDraggingRadius?: string;
    thumbBorderWidth?: number;
    hitHeight?: number;
    swatch?: string;
    ariaLabel?: string;
    valueLabel?: string;
    onchange?: (value: number | string) => void;
    onnumericchange?: (value: number) => void;
    onnormalizedchange?: (value: number) => void;
  } = $props();

  const spectrumStops = [
    { at: 0, rgb: [255, 0, 0] },
    { at: 0.15, rgb: [255, 255, 0] },
    { at: 0.30, rgb: [0, 255, 0] },
    { at: 0.45, rgb: [0, 255, 255] },
    { at: 0.60, rgb: [0, 0, 255] },
    { at: 0.75, rgb: [255, 0, 255] },
    { at: 0.90, rgb: [255, 0, 0] },
    { at: 1, rgb: [255, 255, 255] },
  ] as const;

  function clampNumber(next: number): number {
    if (!Number.isFinite(next)) return min;
    return Math.max(min, Math.min(max, next));
  }

  function fractionFor(next: number): number {
    return max === min ? 0 : Math.max(0, Math.min(1, (clampNumber(next) - min) / (max - min)));
  }

  function rgbToHex(rgb: readonly number[]): string {
    return `#${rgb.map((channel) => Math.max(0, Math.min(255, Math.round(channel))).toString(16).padStart(2, '0')).join('').toUpperCase()}`;
  }

  function spectrumColorAt(nextFraction: number): string {
    const clamped = Math.max(0, Math.min(1, nextFraction));
    for (let index = 1; index < spectrumStops.length; index += 1) {
      const right = spectrumStops[index];
      if (clamped <= right.at) {
        const left = spectrumStops[index - 1];
        const span = right.at - left.at;
        const local = span === 0 ? 0 : (clamped - left.at) / span;
        return rgbToHex(left.rgb.map((channel, channelIndex) =>
          channel + (right.rgb[channelIndex] - channel) * local,
        ));
      }
    }
    return '#FFFFFF';
  }

  const sliderNumber = $derived(track === 'spectrum'
    ? clampNumber(numericValue)
    : clampNumber(typeof value === 'number' ? value : Number(value)));
  const fraction = $derived(fractionFor(sliderNumber));
  const spectrumColor = $derived(spectrumColorAt(fraction));
  const displayedValue = $derived(valueLabel ?? (track === 'spectrum' ? spectrumColor : `${sliderNumber}${suffix}`));

  const safeWidth = $derived(Math.max(1, width));
  const safeSliderHeight = $derived(Math.max(2, trackHeight));
  const safeThumbWidth = $derived(Math.max(2, thumbWidth ?? thumbSize));
  const safeThumbHeight = $derived(Math.max(2, thumbHeight ?? thumbSize));
  const safeDraggingWidth = $derived(Math.max(2, thumbDraggingWidth ?? safeThumbWidth * 1.28));
  const safeDraggingHeight = $derived(Math.max(2, thumbDraggingHeight ?? safeThumbHeight * 1.28));
  const safeHitHeight = $derived(Math.max(safeSliderHeight, hitHeight));
  const rootStyle = $derived([
    `--v2-range-slider-width:${safeWidth}px`,
    `--v2-range-slider-height:${safeSliderHeight}px`,
    `--v2-range-thumb-width:${safeThumbWidth}px`,
    `--v2-range-thumb-height:${safeThumbHeight}px`,
    `--v2-range-thumb-dragging-width:${safeDraggingWidth}px`,
    `--v2-range-thumb-dragging-height:${safeDraggingHeight}px`,
    `--v2-range-thumb-radius:${thumbRadius}`,
    `--v2-range-thumb-dragging-radius:${thumbDraggingRadius ?? thumbRadius}`,
    `--v2-range-thumb-border-width:${Math.max(0, thumbBorderWidth)}px`,
    `--v2-range-hit-height:${safeHitHeight}px`,
    `--v2-range-position:${fraction * 100}%`,
    `--v2-range-spectrum-color:${spectrumColor}`,
  ].join(';'));

  function handleInput(event: Event): void {
    const next = clampNumber(Number((event.currentTarget as HTMLInputElement).value));
    const nextNormalized = fractionFor(next);

    numericValue = next;
    normalizedValue = nextNormalized;
    onnumericchange?.(next);
    onnormalizedchange?.(nextNormalized);

    if (track === 'spectrum') {
      const color = spectrumColorAt(nextNormalized);
      value = color;
      onchange?.(color);
      return;
    }

    value = next;
    onchange?.(next);
  }

  $effect(() => {
    const nextNumeric = sliderNumber;
    const nextNormalized = fractionFor(nextNumeric);

    if (numericValue !== nextNumeric) numericValue = nextNumeric;
    if (normalizedValue !== nextNormalized) normalizedValue = nextNormalized;

    if (track === 'spectrum') {
      const color = spectrumColorAt(nextNormalized);
      if (value !== color) value = color;
    }
  });
</script>

<label class="v2-range-slider" style={rootStyle}>
  {#if label}<span>{label}</span>{/if}
  {#if swatch}<i class="v2-range-swatch" style={`background:${swatch}`} aria-hidden="true"></i>{/if}
  <span class="v2-range-control" data-track={track}>
    <span class="v2-range-track" aria-hidden="true">
      <span class="v2-range-fill-rail"><span class="v2-range-fill"></span></span>
    </span>
    <input
      type="range"
      {min}
      {max}
      {step}
      value={sliderNumber}
      oninput={handleInput}
      aria-label={ariaLabel ?? label}
    >
    <span class="v2-range-thumb-rail" aria-hidden="true">
      <span class="v2-range-thumb"></span>
    </span>
  </span>
  <span class="v2-range-value">{displayedValue}</span>
</label>

<style>
  .v2-range-slider{
    --v2-range-slider-radius:calc(var(--v2-range-slider-height) / 2);
    --v2-range-thumb-overhang:max(0px,calc((var(--v2-range-thumb-width) - var(--v2-range-slider-height)) / 2));
    --v2-range-control-width:calc(var(--v2-range-slider-width) + 2 * var(--v2-range-thumb-overhang));
    --v2-range-control-height:max(var(--v2-range-hit-height),var(--v2-range-thumb-height));
    --v2-range-thumb-travel:max(0px,calc(var(--v2-range-slider-width) - var(--v2-range-slider-height)));
    display:flex;align-items:center;gap:7px;font-size:11px;white-space:nowrap;max-width:100%;
  }
  .v2-range-control{position:relative;display:inline-flex;align-items:center;width:var(--v2-range-control-width);height:var(--v2-range-control-height);flex:0 0 var(--v2-range-control-width)}
  .v2-range-track{position:absolute;left:var(--v2-range-thumb-overhang);width:var(--v2-range-slider-width);top:50%;height:var(--v2-range-slider-height);transform:translateY(-50%);border-radius:999px;background:#263342;overflow:hidden;pointer-events:none}

  .v2-range-fill-rail{position:absolute;left:var(--v2-range-slider-radius);top:0;width:var(--v2-range-thumb-travel);height:100%;pointer-events:none}
  .v2-range-fill{display:block;width:var(--v2-range-position);height:100%;background:#7ea6ff}
  .v2-range-control[data-track="fill"] .v2-range-track::after{content:"";position:absolute;left:0;top:0;bottom:0;width:var(--v2-range-slider-radius);background:#7ea6ff}
  .v2-range-control:not([data-track="fill"]) .v2-range-fill-rail{display:none}

  .v2-range-control[data-track="spectrum"] .v2-range-track{background:#ff0000}
  .v2-range-control[data-track="spectrum"] .v2-range-track::before{
    content:"";position:absolute;left:var(--v2-range-slider-radius);right:var(--v2-range-slider-radius);top:0;bottom:0;
    background:linear-gradient(90deg,#ff0000 0%,#ffff00 15%,#00ff00 30%,#00ffff 45%,#0000ff 60%,#ff00ff 75%,#ff0000 90%,#ffffff 100%);
  }
  .v2-range-control[data-track="spectrum"] .v2-range-track::after{content:"";position:absolute;right:0;top:0;bottom:0;width:var(--v2-range-slider-radius);background:#fff}

  .v2-range-control input{position:absolute;left:var(--v2-range-thumb-overhang);top:50%;width:var(--v2-range-slider-width);height:var(--v2-range-hit-height);margin:0;padding:0;transform:translateY(-50%);appearance:none;border:0;outline:none;background:transparent;cursor:pointer;z-index:3}
  .v2-range-control input::-webkit-slider-runnable-track{height:var(--v2-range-slider-height);background:transparent;border:0}
  .v2-range-control input::-moz-range-track{height:var(--v2-range-slider-height);background:transparent;border:0}
  .v2-range-control input::-webkit-slider-thumb{appearance:none;box-sizing:border-box;width:var(--v2-range-slider-height);height:var(--v2-range-slider-height);margin-top:0;border:0;border-radius:50%;background:transparent;box-shadow:none}
  .v2-range-control input::-moz-range-thumb{box-sizing:border-box;width:var(--v2-range-slider-height);height:var(--v2-range-slider-height);border:0;border-radius:50%;background:transparent;box-shadow:none}

  .v2-range-thumb-rail{position:absolute;z-index:2;left:calc(var(--v2-range-thumb-overhang) + var(--v2-range-slider-radius));top:50%;width:var(--v2-range-thumb-travel);height:0;pointer-events:none}
  .v2-range-thumb{position:absolute;left:var(--v2-range-position);top:0;width:var(--v2-range-thumb-width);height:var(--v2-range-thumb-height);box-sizing:border-box;border-radius:var(--v2-range-thumb-radius);background:#fff;border:var(--v2-range-thumb-border-width) solid #7ea6ff;box-shadow:0 2px 8px rgba(0,0,0,.45);transform:translate(-50%,-50%);transform-origin:center;transition:width 110ms ease,height 110ms ease,border-radius 110ms ease,background 110ms ease}
  .v2-range-control[data-track="spectrum"] .v2-range-thumb{background:var(--v2-range-spectrum-color)}
  .v2-range-control input:active ~ .v2-range-thumb-rail .v2-range-thumb{width:var(--v2-range-thumb-dragging-width);height:var(--v2-range-thumb-dragging-height);border-radius:var(--v2-range-thumb-dragging-radius)}
  .v2-range-control input:focus-visible ~ .v2-range-thumb-rail .v2-range-thumb{outline:2px solid #4169a8;outline-offset:2px}

  .v2-range-swatch{width:18px;height:18px;flex:0 0 18px;border-radius:50%;border:2px solid rgba(255,255,255,.8)}
  .v2-range-value{min-width:64px;text-align:center;background:#151f2a;border:1px solid #354557;border-radius:999px;padding:3px 7px;font-size:11px}

  @media (prefers-reduced-motion:reduce){.v2-range-thumb{transition:none}}
</style>
