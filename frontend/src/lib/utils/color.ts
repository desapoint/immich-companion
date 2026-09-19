export type RgbColor = { r: number; g: number; b: number };
export type HsvColor = { h: number; s: number; v: number };
export type PaletteColor = { color: string; label: string };

export const MAX_RECENT_COLORS = 8;
export const RECENT_COLORS_STORAGE_KEY = 'immich-companion:v2:recent-colors';

export const V2_COLOR_PALETTE: PaletteColor[] = [
  { color: '#EF4444', label: 'Red' },
  { color: '#F97316', label: 'Orange' },
  { color: '#F59E0B', label: 'Amber' },
  { color: '#EAB308', label: 'Yellow' },
  { color: '#84CC16', label: 'Lime' },
  { color: '#22C55E', label: 'Green' },
  { color: '#10B981', label: 'Emerald' },
  { color: '#14B8A6', label: 'Teal' },
  { color: '#06B6D4', label: 'Cyan' },
  { color: '#0EA5E9', label: 'Sky' },
  { color: '#3B82F6', label: 'Blue' },
  { color: '#6366F1', label: 'Indigo' },
  { color: '#8B5CF6', label: 'Violet' },
  { color: '#A855F7', label: 'Purple' },
  { color: '#D946EF', label: 'Fuchsia' },
  { color: '#F43F5E', label: 'Rose' },
];

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function wrapHue(hue: number): number {
  return ((hue % 360) + 360) % 360;
}

export function normalizeHex(input: string): string | null {
  const value = input.trim().replace(/^#/, '');
  if (/^[\da-f]{3}$/i.test(value)) {
    return `#${[...value].map((part) => part.repeat(2)).join('').toUpperCase()}`;
  }
  return /^[\da-f]{6}$/i.test(value) ? `#${value.toUpperCase()}` : null;
}

export function hexToRgb(hex: string): RgbColor {
  const normalized = normalizeHex(hex);
  if (!normalized) throw new TypeError(`Invalid HEX color: ${hex}`);
  return {
    r: Number.parseInt(normalized.slice(1, 3), 16),
    g: Number.parseInt(normalized.slice(3, 5), 16),
    b: Number.parseInt(normalized.slice(5, 7), 16),
  };
}

export function rgbToHex(rgb: RgbColor): string {
  const channel = (value: number) => Math.round(clamp(value, 0, 255)).toString(16).padStart(2, '0');
  return `#${channel(rgb.r)}${channel(rgb.g)}${channel(rgb.b)}`.toUpperCase();
}

export function rgbToHsv(rgb: RgbColor): HsvColor {
  const r = clamp(rgb.r, 0, 255) / 255;
  const g = clamp(rgb.g, 0, 255) / 255;
  const b = clamp(rgb.b, 0, 255) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  let h = 0;
  if (delta) {
    if (max === r) h = 60 * (((g - b) / delta) % 6);
    else if (max === g) h = 60 * ((b - r) / delta + 2);
    else h = 60 * ((r - g) / delta + 4);
  }
  return { h: wrapHue(h), s: max ? (delta / max) * 100 : 0, v: max * 100 };
}

export function hsvToRgb(hsv: HsvColor): RgbColor {
  const h = wrapHue(hsv.h);
  const s = clamp(hsv.s, 0, 100) / 100;
  const v = clamp(hsv.v, 0, 100) / 100;
  const chroma = v * s;
  const x = chroma * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - chroma;
  let channels: [number, number, number];
  if (h < 60) channels = [chroma, x, 0];
  else if (h < 120) channels = [x, chroma, 0];
  else if (h < 180) channels = [0, chroma, x];
  else if (h < 240) channels = [0, x, chroma];
  else if (h < 300) channels = [x, 0, chroma];
  else channels = [chroma, 0, x];
  return { r: (channels[0] + m) * 255, g: (channels[1] + m) * 255, b: (channels[2] + m) * 255 };
}

export function relativeLuminance(hex: string): number {
  const rgb = hexToRgb(hex);
  const linear = (channel: number) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return linear(rgb.r) * 0.2126 + linear(rgb.g) * 0.7152 + linear(rgb.b) * 0.0722;
}

export function foregroundForBackground(hex: string): '#000000' | '#FFFFFF' {
  return relativeLuminance(hex) > 0.179 ? '#000000' : '#FFFFFF';
}

export function parseRecentColors(serialized: string | null): string[] {
  if (!serialized) return [];
  try {
    const values: unknown = JSON.parse(serialized);
    if (!Array.isArray(values)) return [];
    return [...new Set(values.flatMap((value) => typeof value === 'string' ? [normalizeHex(value)] : []).filter((value): value is string => value !== null))].slice(0, MAX_RECENT_COLORS);
  } catch {
    return [];
  }
}

export function addRecentColor(colors: readonly string[], color: string): string[] {
  const normalized = normalizeHex(color);
  if (!normalized) return [...colors];
  return [normalized, ...colors.map(normalizeHex).filter((value): value is string => value !== null && value !== normalized)].slice(0, MAX_RECENT_COLORS);
}
