<script lang="ts">
  import { Check, Copy } from '@lucide/svelte';
  import { onDestroy, onMount, tick, untrack } from 'svelte';
  import { clickOutside } from '../../lib/actions/clickOutside';
  import {
    addRecentColor,
    clamp,
    foregroundForBackground,
    hexToRgb,
    hsvToRgb,
    normalizeHex,
    parseRecentColors,
    RECENT_COLORS_STORAGE_KEY,
    rgbToHex,
    rgbToHsv,
    V2_COLOR_PALETTE,
    wrapHue,
    type HsvColor,
  } from '../state/color';
  import { floatingFieldLayout, type FloatingAlignment, type FloatingPlacement } from '../state/floatingField';
  import V2ColorSwatch from './V2ColorSwatch.svelte';

  type UsedColor = { color: string; count?: number };

  let {
    id,
    label = '',
    value,
    disabled = false,
    allowEmpty = true,
    palette = V2_COLOR_PALETTE.map((entry) => entry.color),
    recent = true,
    usedColors = [],
    usedColorsLabel = 'Used colors',
    onchange,
  }: {
    id: string;
    label?: string;
    value: string | null;
    disabled?: boolean;
    allowEmpty?: boolean;
    palette?: string[];
    recent?: boolean;
    usedColors?: UsedColor[];
    usedColorsLabel?: string;
    onchange?: (value: string | null) => void;
  } = $props();

  const FALLBACK_HSV: HsvColor = { h: 258, s: 52, v: 100 };
  const CHROMATIC_THRESHOLD = 0.5;
  let open = $state(false);
  let trigger = $state<HTMLButtonElement>();
  let popup = $state<HTMLDivElement>();
  let plane = $state<HTMLButtonElement>();
  let hsv = $state<HsvColor>({ ...FALLBACK_HSV });
  let currentHex = $derived<string | null>(value === null ? null : normalizeHex(value));
  let hexDraft = $state('');
  let copied = $state(false);
  let recentColors = $state<string[]>([]);
  let popupTop = $state(0);
  let popupLeft = $state(0);
  let popupWidth = $state(360);
  let popupMaxHeight = $state(480);
  let popupPlacement = $state<FloatingPlacement>('down');
  let popupAlignment = $state<FloatingAlignment>('left');
  let lastChromaticHue = FALLBACK_HSV.h;
  let synchronizedExternal: string | null | undefined;
  let openedWithColor: string | null = null;
  let planePointer: number | null = null;
  let huePointer: number | null = null;
  let copyTimer: ReturnType<typeof setTimeout> | undefined;

  const pureHue = $derived(rgbToHex(hsvToRgb({ h: hsv.h, s: 100, v: 100 })));
  const normalizedPalette = $derived.by(() => {
    const colors = palette.map(normalizeHex).filter((color): color is string => color !== null);
    return [...new Set(colors)];
  });
  const normalizedUsedColors = $derived.by(() => {
    const counts = new Map<string, number | undefined>();
    for (const entry of usedColors) {
      const color = normalizeHex(entry.color);
      if (!color) continue;
      const previous = counts.get(color);
      counts.set(color, previous === undefined ? entry.count : Math.max(previous, entry.count ?? 0));
    }
    return [...counts].map(([color, count]) => ({ color, count })).sort((a, b) => (b.count ?? 0) - (a.count ?? 0));
  });

  function syncFromExternal(externalValue: string | null): void {
    const normalized = externalValue === null ? null : normalizeHex(externalValue);
    if (externalValue !== null && !normalized) return;
    if (normalized === synchronizedExternal) return;
    synchronizedExternal = normalized;
    if (normalized !== currentHex) currentHex = normalized;
    hexDraft = normalized ?? '';
    if (!normalized) return;
    const converted = rgbToHsv(hexToRgb(normalized));
    if (converted.s > CHROMATIC_THRESHOLD && converted.v > CHROMATIC_THRESHOLD) lastChromaticHue = converted.h;
    hsv = { ...converted, h: converted.s <= CHROMATIC_THRESHOLD || converted.v <= CHROMATIC_THRESHOLD ? lastChromaticHue : converted.h };
  }

  $effect(() => {
    const externalValue = value;
    untrack(() => syncFromExternal(externalValue));
  });

  function publishHsv(next: HsvColor): void {
    const normalized = { h: wrapHue(next.h), s: clamp(next.s, 0, 100), v: clamp(next.v, 0, 100) };
    if (normalized.s > CHROMATIC_THRESHOLD && normalized.v > CHROMATIC_THRESHOLD) lastChromaticHue = normalized.h;
    hsv = normalized;
    const hex = rgbToHex(hsvToRgb(normalized));
    currentHex = hex;
    hexDraft = hex;
    onchange?.(hex);
  }

  function chooseHex(input: string): boolean {
    const normalized = normalizeHex(input);
    if (!normalized) return false;
    const converted = rgbToHsv(hexToRgb(normalized));
    if (converted.s > CHROMATIC_THRESHOLD && converted.v > CHROMATIC_THRESHOLD) lastChromaticHue = converted.h;
    hsv = { ...converted, h: converted.s <= CHROMATIC_THRESHOLD || converted.v <= CHROMATIC_THRESHOLD ? lastChromaticHue : converted.h };
    currentHex = normalized;
    hexDraft = normalized;
    onchange?.(normalized);
    return true;
  }

  function rememberSelection(): void {
    if (!recent || !currentHex || currentHex === openedWithColor || typeof localStorage === 'undefined') return;
    recentColors = addRecentColor(recentColors, currentHex);
    try {
      localStorage.setItem(RECENT_COLORS_STORAGE_KEY, JSON.stringify(recentColors));
    } catch {
      // Color selection must remain usable when browser storage is unavailable.
    }
  }

  function positionPopup(): void {
    if (!open || !trigger) return;
    const layout = floatingFieldLayout({
      anchor: trigger.getBoundingClientRect(),
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      preferredWidth: 360,
      preferredHeight: Math.min(480, popup?.scrollHeight || 480),
      minimumUsefulHeight: 240,
      minimumHeight: 220,
      margin: window.innerWidth <= 520 ? 8 : 10,
    });
    popupTop = layout.top;
    popupLeft = layout.left;
    popupWidth = layout.width;
    popupMaxHeight = layout.maxHeight;
    popupPlacement = layout.placement;
    popupAlignment = layout.alignment;
  }

  function show(focusInside = false): void {
    if (disabled || open) return;
    openedWithColor = currentHex;
    open = true;
    void tick().then(() => {
      positionPopup();
      requestAnimationFrame(positionPopup);
      if (focusInside) plane?.focus();
    });
  }

  function close(returnFocus = true): void {
    if (!open) return;
    rememberSelection();
    open = false;
    if (returnFocus) void tick().then(() => trigger?.focus());
  }

  function toggle(): void {
    if (open) close();
    else show(false);
  }

  function handleTriggerKeydown(event: KeyboardEvent): void {
    if (!['Enter', ' ', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    show(true);
  }

  function handlePopupKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    event.stopPropagation();
    close();
  }

  function updatePlane(event: PointerEvent): void {
    const target = event.currentTarget as HTMLElement;
    const rect = target.getBoundingClientRect();
    publishHsv({ ...hsv, s: clamp((event.clientX - rect.left) / rect.width, 0, 1) * 100, v: (1 - clamp((event.clientY - rect.top) / rect.height, 0, 1)) * 100 });
  }

  function handlePlanePointerDown(event: PointerEvent): void {
    if (disabled || event.button !== 0) return;
    planePointer = event.pointerId;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    updatePlane(event);
  }

  function handlePlanePointerMove(event: PointerEvent): void {
    if (planePointer !== event.pointerId) return;
    updatePlane(event);
  }

  function releasePlanePointer(event: PointerEvent): void {
    if (planePointer !== event.pointerId) return;
    planePointer = null;
    (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId);
  }

  function handlePlaneKeydown(event: KeyboardEvent): void {
    const step = event.shiftKey ? 5 : 1;
    let next: HsvColor | null = null;
    if (event.key === 'ArrowLeft') next = { ...hsv, s: hsv.s - step };
    else if (event.key === 'ArrowRight') next = { ...hsv, s: hsv.s + step };
    else if (event.key === 'ArrowUp') next = { ...hsv, v: hsv.v + step };
    else if (event.key === 'ArrowDown') next = { ...hsv, v: hsv.v - step };
    if (!next) return;
    event.preventDefault();
    publishHsv(next);
  }

  function updateHue(event: PointerEvent): void {
    const target = event.currentTarget as HTMLElement;
    const rect = target.getBoundingClientRect();
    publishHsv({ ...hsv, h: clamp((event.clientX - rect.left) / rect.width, 0, 1) * 359.999 });
  }

  function handleHuePointerDown(event: PointerEvent): void {
    if (disabled || event.button !== 0) return;
    huePointer = event.pointerId;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    updateHue(event);
  }

  function handleHuePointerMove(event: PointerEvent): void {
    if (huePointer !== event.pointerId) return;
    updateHue(event);
  }

  function releaseHuePointer(event: PointerEvent): void {
    if (huePointer !== event.pointerId) return;
    huePointer = null;
    (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId);
  }

  function handleHueKeydown(event: KeyboardEvent): void {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const step = event.shiftKey ? 10 : 1;
    publishHsv({ ...hsv, h: hsv.h + (event.key === 'ArrowRight' ? step : -step) });
  }

  function commitHex(): void {
    if (!chooseHex(hexDraft)) hexDraft = currentHex ?? '';
  }

  function handleHexInput(event: Event & { currentTarget: HTMLInputElement }): void {
    hexDraft = event.currentTarget.value;
    const inputType = event instanceof InputEvent ? event.inputType : '';
    if (inputType === 'insertFromPaste' || /^#?[\da-f]{6}$/i.test(hexDraft.trim())) chooseHex(hexDraft);
  }

  function handleHexKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    commitHex();
  }

  async function copyColor(): Promise<void> {
    if (!currentHex) return;
    try {
      await navigator.clipboard.writeText(currentHex);
      copied = true;
      if (copyTimer) clearTimeout(copyTimer);
      copyTimer = setTimeout(() => copied = false, 1000);
    } catch {
      copied = false;
    }
  }

  function clearColor(): void {
    if (!allowEmpty) return;
    currentHex = null;
    hexDraft = '';
    onchange?.(null);
  }

  function paletteLabel(color: string): string {
    return V2_COLOR_PALETTE.find((entry) => entry.color === color)?.label ?? color;
  }

  onMount(() => {
    if (!recent || typeof localStorage === 'undefined') return;
    try {
      recentColors = parseRecentColors(localStorage.getItem(RECENT_COLORS_STORAGE_KEY));
    } catch {
      recentColors = [];
    }
  });

  $effect(() => {
    if (!open) return;
    const reposition = () => positionPopup();
    const observer = typeof ResizeObserver === 'undefined' || !trigger ? null : new ResizeObserver(reposition);
    if (trigger) observer?.observe(trigger);
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
  });

  onDestroy(() => {
    if (open) rememberSelection();
    if (copyTimer) clearTimeout(copyTimer);
  });
</script>

<div class="v2-color-field" data-open={open || undefined} data-empty={currentHex === null || undefined} data-disabled={disabled || undefined} use:clickOutside={{ enabled: open, onoutside: () => close() }}>
  {#if label}<label class="v2-color-label" for={id}>{label}</label>{/if}
  <button bind:this={trigger} {id} class="v2-color-trigger" type="button" {disabled} aria-haspopup="dialog" aria-expanded={open} aria-controls={`${id}-popup`} onclick={toggle} onkeydown={handleTriggerKeydown}>
    <span class="v2-color-trigger-content"><V2ColorSwatch color={currentHex}/><span class="v2-color-trigger-value">{currentHex ?? 'No color'}</span></span>
    <span class="v2-color-trigger-chevron" aria-hidden="true"></span>
  </button>

  {#if open}
    <div bind:this={popup} id={`${id}-popup`} class="v2-color-popup" role="dialog" tabindex="-1" aria-label="Choose color" data-placement={popupPlacement} data-alignment={popupAlignment} style={`top:${popupTop}px;left:${popupLeft}px;width:${popupWidth}px;max-height:${popupMaxHeight}px`} onkeydown={handlePopupKeydown}>
      <span id={`${id}-plane-help`} class="v2-visually-hidden">Use arrow keys to change saturation and brightness. Hold Shift for larger adjustments.</span>
      <button bind:this={plane} type="button" role="slider" class="v2-color-plane" style:--v2-picker-hue={pureHue} aria-label="Saturation and brightness" aria-describedby={`${id}-plane-help`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(hsv.s)} aria-valuetext={`Saturation ${Math.round(hsv.s)} percent, brightness ${Math.round(hsv.v)} percent`} onpointerdown={handlePlanePointerDown} onpointermove={handlePlanePointerMove} onpointerup={releasePlanePointer} onpointercancel={releasePlanePointer} onkeydown={handlePlaneKeydown}>
        <span class="v2-color-plane-handle" style:left={`${hsv.s}%`} style:top={`${100-hsv.v}%`}></span>
      </button>

      <button type="button" class="v2-color-hue" role="slider" aria-label="Hue" aria-valuemin="0" aria-valuemax="359" aria-valuenow={Math.round(wrapHue(hsv.h))} aria-valuetext={`${Math.round(wrapHue(hsv.h))} degrees`} onpointerdown={handleHuePointerDown} onpointermove={handleHuePointerMove} onpointerup={releaseHuePointer} onpointercancel={releaseHuePointer} onkeydown={handleHueKeydown}>
        <span class="v2-color-hue-track"></span><span class="v2-color-hue-handle" style:left={`${wrapHue(hsv.h)/360*100}%`}></span>
      </button>

      <div class="v2-color-value-row" data-invalid={Boolean(hexDraft && !normalizeHex(hexDraft)) || undefined}>
        <V2ColorSwatch color={currentHex}/>
        <input class="v2-color-hex-input" value={hexDraft} placeholder="#9A78FF" aria-label="HEX color" spellcheck="false" autocomplete="off" oninput={handleHexInput} onkeydown={handleHexKeydown} onblur={commitHex}>
        <button type="button" class="v2-color-copy" disabled={!currentHex} aria-label={currentHex ? `Copy ${currentHex}` : 'No color to copy'} title={copied ? 'Copied' : 'Copy HEX color'} onclick={() => void copyColor()}>{#if copied}<Check size={16} aria-hidden="true"/>{:else}<Copy size={16} aria-hidden="true"/>{/if}<span class="v2-visually-hidden">{copied ? 'Copied' : 'Copy'}</span></button>
      </div>

      <section class="v2-color-section" aria-label="Quick colors"><span class="v2-color-section-title">Quick colors</span><div class="v2-color-palette">{#each normalizedPalette as color (color)}<button type="button" class="v2-color-choice" data-selected={currentHex === color || undefined} aria-label={`${paletteLabel(color)} · ${color}`} aria-pressed={currentHex === color} title={`${paletteLabel(color)} · ${color}`} onclick={() => chooseHex(color)}><V2ColorSwatch {color} selected={currentHex === color}/></button>{/each}</div></section>

      {#if recent && recentColors.length}<section class="v2-color-section" aria-label="Recent colors"><span class="v2-color-section-title">Recent</span><div class="v2-color-palette">{#each recentColors as color (color)}<button type="button" class="v2-color-choice" data-selected={currentHex === color || undefined} aria-label={`Recent color ${color}`} aria-pressed={currentHex === color} title={color} onclick={() => chooseHex(color)}><V2ColorSwatch {color} selected={currentHex === color}/></button>{/each}</div></section>{/if}

      {#if normalizedUsedColors.length}<section class="v2-color-section" aria-label={usedColorsLabel}><span class="v2-color-section-title">{usedColorsLabel}</span><div class="v2-color-palette">{#each normalizedUsedColors as entry (entry.color)}<button type="button" class="v2-color-choice" data-selected={currentHex === entry.color || undefined} aria-label={`${entry.color}${entry.count === undefined ? '' : `, used by ${entry.count} tags`}`} aria-pressed={currentHex === entry.color} title={`${entry.color}${entry.count === undefined ? '' : ` · Used by ${entry.count} tags`}`} onclick={() => chooseHex(entry.color)}><V2ColorSwatch color={entry.color} selected={currentHex === entry.color}/></button>{/each}</div></section>{/if}

      {#if allowEmpty}<div class="v2-color-actions"><button type="button" onclick={clearColor}><V2ColorSwatch color={null} size="sm"/><span>No color</span></button></div>{/if}
    </div>
  {/if}
</div>

<style>
  .v2-color-field{position:relative;display:flex;flex-direction:column;gap:5px;width:100%;min-width:0}
  .v2-color-label{font-size:12px;color:#a9b6c4}
  .v2-color-trigger{width:100%;min-width:0;min-height:42px;display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;border:1px solid var(--v2-line);border-radius:8px;background:#0f151d;color:var(--v2-text);padding:8px 10px;cursor:pointer;text-align:left}
  .v2-color-trigger:hover:not(:disabled),.v2-color-trigger[aria-expanded="true"]{border-color:#4d607a}
  .v2-color-trigger:focus-visible,.v2-color-popup button:focus-visible,.v2-color-popup input:focus-visible{outline:2px solid #4169a8;outline-offset:2px}
  .v2-color-trigger:disabled{cursor:default;opacity:.5}
  .v2-color-trigger-content{min-width:0;display:flex;align-items:center;gap:9px}.v2-color-trigger-value{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.v2-color-field[data-empty="true"] .v2-color-trigger-value{color:var(--v2-muted)}
  .v2-color-trigger-chevron{width:7px;height:7px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:translateY(-2px) rotate(45deg);transition:transform 120ms ease}.v2-color-trigger[aria-expanded="true"] .v2-color-trigger-chevron{transform:translateY(2px) rotate(225deg)}
  .v2-color-popup{position:fixed;z-index:180;display:flex;flex-direction:column;gap:12px;overflow-y:auto;overscroll-behavior:contain;padding:14px;border:1px solid var(--v2-line);border-radius:10px;background:var(--v2-surface-2);box-shadow:0 14px 32px rgba(0,0,0,.42);scrollbar-gutter:stable both-edges;scrollbar-width:thin;scrollbar-color:#475970 transparent}
  .v2-color-popup::-webkit-scrollbar{width:6px;height:6px}.v2-color-popup::-webkit-scrollbar-track{background:transparent}.v2-color-popup::-webkit-scrollbar-thumb{border:1px solid var(--v2-surface-2);border-radius:999px;background:#475970}
  .v2-color-plane{position:relative;display:block;width:100%;aspect-ratio:1.68/1;min-height:150px;flex:0 0 auto;overflow:hidden;border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:0;cursor:crosshair;touch-action:none;background:linear-gradient(to top,#000,transparent),linear-gradient(to right,#fff,var(--v2-picker-hue));box-shadow:inset 0 0 0 1px rgba(0,0,0,.18)}
  .v2-color-plane-handle{position:absolute;width:15px;height:15px;border:2px solid #fff;border-radius:50%;box-shadow:0 0 0 1px rgba(0,0,0,.7),0 1px 3px rgba(0,0,0,.4);transform:translate(-50%,-50%);pointer-events:none}
  .v2-color-hue{position:relative;width:100%;height:28px;display:block;border:0;background:transparent;padding:6px 0;cursor:pointer;touch-action:none}
  .v2-color-hue-track{display:block;width:100%;height:16px;border-radius:999px;background:linear-gradient(to right,#f00 0%,#ff0 16.67%,#0f0 33.33%,#0ff 50%,#00f 66.67%,#f0f 83.33%,#f00 100%);box-shadow:inset 0 0 0 1px rgba(0,0,0,.32)}
  .v2-color-hue-handle{position:absolute;top:3px;width:10px;height:22px;border:2px solid #fff;border-radius:999px;box-shadow:0 0 0 1px rgba(0,0,0,.6),0 1px 3px rgba(0,0,0,.35);transform:translateX(-50%);pointer-events:none}
  .v2-color-value-row{display:grid;grid-template-columns:auto minmax(0,1fr) 36px;align-items:center;gap:8px}.v2-color-hex-input{width:100%;min-width:0;height:38px;border:1px solid var(--v2-line);border-radius:8px;background:#0f151d;color:var(--v2-text);padding:7px 9px;text-transform:uppercase}.v2-color-value-row[data-invalid="true"] .v2-color-hex-input{border-color:var(--v2-red)}
  .v2-color-copy{width:36px;height:36px;display:grid;place-items:center;border:1px solid var(--v2-line);border-radius:8px;background:#111923;color:var(--v2-text);padding:0;cursor:pointer}.v2-color-copy:hover:not(:disabled){border-color:#4d607a;background:#172231}.v2-color-copy:disabled{cursor:default;opacity:.45}
  .v2-color-section{display:flex;flex-direction:column;gap:7px}.v2-color-section-title{font-size:10px;font-weight:800;line-height:1.2;letter-spacing:.08em;text-transform:uppercase;color:#9aaabd}.v2-color-palette{display:grid;grid-template-columns:repeat(8,minmax(28px,1fr));gap:6px}
  .v2-color-choice{min-width:0;min-height:30px;display:grid;place-items:center;border:0;border-radius:999px;background:transparent;padding:3px;cursor:pointer}.v2-color-choice:hover{background:rgba(255,255,255,.07)}.v2-color-choice:focus-visible{outline-offset:0!important}
  .v2-color-actions{display:flex;justify-content:flex-end;padding-top:1px}.v2-color-actions button{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--v2-line);border-radius:8px;background:#111923;color:var(--v2-text);padding:7px 9px;cursor:pointer}.v2-color-actions button:hover{border-color:#4d607a;background:#172231}
  @media(max-width:520px){.v2-color-popup{padding:12px}.v2-color-plane{min-height:140px}}
</style>
