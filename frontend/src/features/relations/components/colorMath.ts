export interface RgbColor { r: number; g: number; b: number; }
export interface HsvColor { h: number; s: number; v: number; }
export interface HslColor { h: number; s: number; l: number; }

export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function normalizeHex(value: string): string | null {
  const candidate = value.trim().replace(/^#?/, '#');
  if (/^#[0-9a-f]{3}$/i.test(candidate)) {
    return `#${candidate.slice(1).split('').map((channel) => channel + channel).join('').toUpperCase()}`;
  }
  return /^#[0-9a-f]{6}$/i.test(candidate) ? candidate.toUpperCase() : null;
}

export function rgbToHex({ r, g, b }: RgbColor): string {
  return `#${[r, g, b].map((channel) => Math.round(clamp(channel, 0, 255)).toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

export function hexToRgb(value: string): RgbColor {
  const hex = normalizeHex(value) ?? '#6B7CFF';
  return { r: parseInt(hex.slice(1, 3), 16), g: parseInt(hex.slice(3, 5), 16), b: parseInt(hex.slice(5, 7), 16) };
}

export function rgbToHsv({ r, g, b }: RgbColor): HsvColor {
  const red = r / 255, green = g / 255, blue = b / 255;
  const maximum = Math.max(red, green, blue), minimum = Math.min(red, green, blue), delta = maximum - minimum;
  let h = 0;
  if (delta) {
    if (maximum === red) h = 60 * (((green - blue) / delta) % 6);
    else if (maximum === green) h = 60 * ((blue - red) / delta + 2);
    else h = 60 * ((red - green) / delta + 4);
  }
  if (h < 0) h += 360;
  return { h, s: maximum ? (delta / maximum) * 100 : 0, v: maximum * 100 };
}

export function hsvToRgb({ h, s, v }: HsvColor): RgbColor {
  const hue = ((h % 360) + 360) % 360, saturation = clamp(s, 0, 100) / 100, value = clamp(v, 0, 100) / 100;
  const chroma = value * saturation, x = chroma * (1 - Math.abs((hue / 60) % 2 - 1)), match = value - chroma;
  const rgb = hue < 60 ? [chroma, x, 0] : hue < 120 ? [x, chroma, 0] : hue < 180 ? [0, chroma, x] : hue < 240 ? [0, x, chroma] : hue < 300 ? [x, 0, chroma] : [chroma, 0, x];
  return { r: (rgb[0] + match) * 255, g: (rgb[1] + match) * 255, b: (rgb[2] + match) * 255 };
}

export function hsvToHsl({ h, s, v }: HsvColor): HslColor {
  const saturation = clamp(s, 0, 100) / 100, value = clamp(v, 0, 100) / 100;
  const lightness = value * (1 - saturation / 2);
  const hslSaturation = lightness === 0 || lightness === 1 ? 0 : (value - lightness) / Math.min(lightness, 1 - lightness);
  return { h, s: hslSaturation * 100, l: lightness * 100 };
}

export function hslToHsv({ h, s, l }: HslColor): HsvColor {
  const lightness = clamp(l, 0, 100) / 100, saturation = clamp(s, 0, 100) / 100;
  const value = lightness + saturation * Math.min(lightness, 1 - lightness);
  return { h, s: value === 0 ? 0 : ((2 * (value - lightness)) / value) * 100, v: value * 100 };
}

export function colorFromHex(value: string): { hex: string; rgb: RgbColor; hsv: HsvColor; hsl: HslColor } {
  const hex = normalizeHex(value) ?? '#6B7CFF';
  const rgb = hexToRgb(hex), hsv = rgbToHsv(rgb);
  return { hex, rgb, hsv, hsl: hsvToHsl(hsv) };
}

export function huePointToDegrees(x: number, y: number, size: number): number {
  const center = size / 2;
  let hue = Math.atan2(y - center, x - center) * 180 / Math.PI + 90;
  if (hue < 0) hue += 360;
  return hue % 360;
}

export function hsvPointToValues(x: number, y: number, width: number, height: number): Pick<HsvColor, 's' | 'v'> {
  return { s: clamp((x / width) * 100, 0, 100), v: clamp((1 - y / height) * 100, 0, 100) };
}
