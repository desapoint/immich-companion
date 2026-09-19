const POSITIVE_DECIMAL = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

function parsePositiveDecimal(value: string): number {
  if (!POSITIVE_DECIMAL.test(value)) throw new Error('Use a positive decimal or fraction.');
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error('Aspect ratio values must be greater than zero.');
  }
  return parsed;
}

export function parseAspectRatioInput(value: string): number {
  const normalized = value.trim();
  const parts = normalized.split('/').map((part) => part.trim());
  if (parts.length === 1) return parsePositiveDecimal(parts[0]);
  if (parts.length !== 2) throw new Error('Use one fraction slash, for example 16/9.');
  const numerator = parsePositiveDecimal(parts[0]);
  const denominator = parsePositiveDecimal(parts[1]);
  return numerator / denominator;
}

export function aspectRatioValidationMessage(value: string): string {
  if (!value.trim()) return '';
  try {
    parseAspectRatioInput(value);
    return '';
  } catch (error) {
    return error instanceof Error ? error.message : 'Enter a valid aspect ratio.';
  }
}

export type ParsedAspectRatio = {
  source: 'ratio' | 'decimal';
  decimal: number;
  ratio: string;
};

export function parseAspectRatio(input: string): ParsedAspectRatio | null {
  const raw = input.trim();
  if (!raw) return null;
  const parts = raw.split(/\s*[:/xX×-]\s*/);
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
  } else return null;
  const tolerance = Math.max(1e-6, Math.abs(decimal) * 0.0005);
  let numerator = Math.max(1, Math.round(decimal));
  let denominator = 1;
  for (let candidate = 1; candidate <= 1000; candidate += 1) {
    const next = Math.max(1, Math.round(decimal * candidate));
    if (Math.abs(next / candidate - decimal) <= tolerance) {
      numerator = next;
      denominator = candidate;
      break;
    }
  }
  const gcd = (left: number, right: number): number => right ? gcd(right, left % right) : left || 1;
  const divisor = gcd(numerator, denominator);
  return { source, decimal, ratio: `${numerator / divisor}:${denominator / divisor}` };
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
