export const SPECTRUM_STOPS = [
  { at: 0, rgb: [255, 0, 0] },
  { at: 0.15, rgb: [255, 255, 0] },
  { at: 0.3, rgb: [0, 255, 0] },
  { at: 0.45, rgb: [0, 255, 255] },
  { at: 0.6, rgb: [0, 0, 255] },
  { at: 0.75, rgb: [255, 0, 255] },
  { at: 0.9, rgb: [255, 0, 0] },
  { at: 1, rgb: [255, 255, 255] },
] as const;

export function rgbToHex(rgb: readonly number[]): string {
  return '#' + rgb.map((channel) => Math.max(0, Math.min(255, Math.round(channel))).toString(16).padStart(2, '0')).join('').toUpperCase();
}

export function spectrumColorAt(nextFraction: number): string {
  const clamped = Math.max(0, Math.min(1, nextFraction));
  for (let index = 1; index < SPECTRUM_STOPS.length; index += 1) {
    const right = SPECTRUM_STOPS[index];
    if (clamped <= right.at) {
      const left = SPECTRUM_STOPS[index - 1];
      const span = right.at - left.at;
      const local = span === 0 ? 0 : (clamped - left.at) / span;
      return rgbToHex(left.rgb.map((channel, channelIndex) => channel + (right.rgb[channelIndex] - channel) * local));
    }
  }
  return '#FFFFFF';
}
