export type ParsedAspectRatio = {
  source: 'ratio' | 'decimal';
  decimal: number;
  ratio: string;
};

const RATIO_SEPARATOR = /\s*[:/xX×-]\s*/;

function gcd(a: number, b: number): number {
  let left = Math.abs(Math.trunc(a));
  let right = Math.abs(Math.trunc(b));
  while (right) [left, right] = [right, left % right];
  return left || 1;
}

function decimalToFraction(value: number): [number, number] {
  const tolerance = Math.max(1e-6, Math.abs(value) * 0.0005);
  for (let denominator = 1; denominator <= 1000; denominator += 1) {
    const numerator = Math.max(1, Math.round(value * denominator));
    if (Math.abs(numerator / denominator - value) <= tolerance) {
      const divisor = gcd(numerator, denominator);
      return [numerator / divisor, denominator / divisor];
    }
  }
  const denominator = 1000;
  const numerator = Math.max(1, Math.round(value * denominator));
  const divisor = gcd(numerator, denominator);
  return [numerator / divisor, denominator / divisor];
}

export function parseAspectRatio(input: string): ParsedAspectRatio | null {
  const raw = input.trim();
  if (!raw) return null;

  const parts = raw.split(RATIO_SEPARATOR);
  let source: ParsedAspectRatio['source'] = 'decimal';
  let decimal: number;

  if (parts.length === 2 && parts.every((part) => part.trim())) {
    const width = Number(parts[0]);
    const height = Number(parts[1]);
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
    source = 'ratio';
    decimal = width / height;
  } else if (parts.length === 1) {
    decimal = Number(raw);
    if (!Number.isFinite(decimal) || decimal <= 0) return null;
  } else {
    return null;
  }

  const [numerator, denominator] = decimalToFraction(decimal);
  return { source, decimal, ratio: `${numerator}:${denominator}` };
}

export function formatAspectDecimal(value: number): string {
  return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
}

export function invertAspectRatio(input: string): string | null {
  const parsed = parseAspectRatio(input);
  if (!parsed) return null;
  const [width, height] = parsed.ratio.split(':');
  return `${height}:${width}`;
}
