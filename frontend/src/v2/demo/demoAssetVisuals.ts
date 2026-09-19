export type DemoVisualAsset = {
  id: string;
  original_file_name?: string | null;
  width?: number | null;
  height?: number | null;
  asset_type?: string | null;
  type?: string | null;
};

type VisualSize = 'preview' | 'full';

const cache = new Map<string, string>();

function hashString(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seeded(seed: number, offset: number): number {
  let value = (seed + Math.imul(offset + 1, 0x9e3779b1)) >>> 0;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  return (value >>> 0) / 0xffffffff;
}

function escapeXml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
  })[character] ?? character);
}

function inferredShape(asset: DemoVisualAsset): { width: number; height: number; type: string | null } {
  if (asset.width && asset.height) return { width: asset.width, height: asset.height, type: asset.asset_type ?? asset.type ?? null };
  const uuidTail = asset.id.match(/-([0-9a-f]{12})$/i)?.[1];
  const ordinal = uuidTail ? Number.parseInt(uuidTail, 16) : Number.NaN;
  if (Number.isFinite(ordinal) && ordinal > 0 && ordinal < 100000) {
    const index = ordinal - 1;
    const isVideo = index % 11 === 0;
    return {
      width: isVideo ? 1920 : index % 4 === 0 ? 4032 : 3024,
      height: isVideo ? 1080 : index % 4 === 0 ? 3024 : 4032,
      type: asset.asset_type ?? asset.type ?? (isVideo ? 'VIDEO' : 'IMAGE'),
    };
  }
  const landscape = hashString(asset.id) % 3 !== 0;
  return { width: landscape ? 4 : 3, height: landscape ? 3 : 4, type: asset.asset_type ?? asset.type ?? null };
}

function dimensions(asset: DemoVisualAsset, size: VisualSize): { width: number; height: number } {
  const source = inferredShape(asset);
  const landscape = source.width >= source.height;
  if (size === 'preview') return landscape ? { width: 420, height: 315 } : { width: 315, height: 420 };
  return landscape ? { width: 1600, height: 1200 } : { width: 1200, height: 1600 };
}

function buildSvg(asset: DemoVisualAsset, size: VisualSize): string {
  const seed = hashString(asset.id);
  const source = inferredShape(asset);
  const { width, height } = dimensions(asset, size);
  const horizon = Math.round(height * (0.48 + seeded(seed, 1) * 0.16));
  const hue = Math.round(seeded(seed, 2) * 360);
  const hue2 = (hue + 28 + Math.round(seeded(seed, 3) * 70)) % 360;
  const sunX = Math.round(width * (0.14 + seeded(seed, 4) * 0.7));
  const sunY = Math.round(height * (0.12 + seeded(seed, 5) * 0.22));
  const sunR = Math.round(Math.min(width, height) * (0.045 + seeded(seed, 6) * 0.035));
  const mountainA = Math.round(width * (0.12 + seeded(seed, 7) * 0.18));
  const mountainB = Math.round(width * (0.48 + seeded(seed, 8) * 0.18));
  const mountainC = Math.round(width * (0.72 + seeded(seed, 9) * 0.2));
  const foregroundY = Math.round(height * (0.73 + seeded(seed, 10) * 0.08));
  const subjectX = Math.round(width * (0.16 + seeded(seed, 11) * 0.68));
  const subjectY = Math.round(height * (0.54 + seeded(seed, 12) * 0.19));
  const subjectScale = 0.75 + seeded(seed, 13) * 0.8;
  const cloudX = Math.round(width * (0.12 + seeded(seed, 14) * 0.64));
  const cloudY = Math.round(height * (0.1 + seeded(seed, 15) * 0.2));
  const label = escapeXml(asset.original_file_name ?? 'Demo asset');
  const noiseOpacity = size === 'preview' ? 0.055 : 0.038;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <defs>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="hsl(${hue} 52% 43%)"/>
        <stop offset=".58" stop-color="hsl(${hue2} 62% 67%)"/>
        <stop offset="1" stop-color="hsl(${(hue2 + 18) % 360} 48% 82%)"/>
      </linearGradient>
      <linearGradient id="ground" x1="0" y1="0" x2="1" y2="1">
        <stop stop-color="hsl(${(hue + 118) % 360} 35% 27%)"/>
        <stop offset="1" stop-color="hsl(${(hue + 152) % 360} 29% 17%)"/>
      </linearGradient>
      <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".72" numOctaves="2" seed="${seed % 997}"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="table" tableValues="0 ${noiseOpacity}"/></feComponentTransfer></filter>
      <filter id="soft"><feGaussianBlur stdDeviation="${Math.max(2, width / 420)}"/></filter>
    </defs>
    <rect width="${width}" height="${height}" fill="url(#sky)"/>
    <circle cx="${sunX}" cy="${sunY}" r="${sunR * 1.8}" fill="hsl(${(hue2 + 35) % 360} 90% 78%)" opacity=".2" filter="url(#soft)"/>
    <circle cx="${sunX}" cy="${sunY}" r="${sunR}" fill="hsl(${(hue2 + 38) % 360} 92% 82%)" opacity=".92"/>
    <g fill="#fff" opacity=".28" filter="url(#soft)"><ellipse cx="${cloudX}" cy="${cloudY}" rx="${width * .105}" ry="${height * .025}"/><ellipse cx="${cloudX + width * .08}" cy="${cloudY + height * .03}" rx="${width * .075}" ry="${height * .018}"/></g>
    <path d="M0 ${horizon} L${mountainA} ${Math.round(horizon * .58)} L${Math.round(width * .32)} ${Math.round(horizon * .88)} L${mountainB} ${Math.round(horizon * .48)} L${Math.round(width * .66)} ${Math.round(horizon * .86)} L${mountainC} ${Math.round(horizon * .56)} L${width} ${Math.round(horizon * .78)} V${height} H0Z" fill="hsl(${(hue + 132) % 360} 24% 26%)" opacity=".94"/>
    <path d="M0 ${Math.round(horizon * 1.08)} L${Math.round(width * .2)} ${Math.round(horizon * .82)} L${Math.round(width * .42)} ${Math.round(horizon * 1.04)} L${Math.round(width * .64)} ${Math.round(horizon * .76)} L${width} ${Math.round(horizon * 1.03)} V${height} H0Z" fill="hsl(${(hue + 142) % 360} 28% 20%)"/>
    <rect y="${foregroundY}" width="${width}" height="${height - foregroundY}" fill="url(#ground)"/>
    <g transform="translate(${subjectX} ${subjectY}) scale(${subjectScale})">
      <rect x="-8" y="32" width="16" height="${height * .17}" rx="5" fill="#4a3428"/>
      <circle cy="10" r="${Math.min(width, height) * .072}" fill="hsl(${(hue + 118) % 360} 38% 27%)"/>
      <circle cx="-${Math.min(width, height) * .045}" cy="25" r="${Math.min(width, height) * .047}" fill="hsl(${(hue + 118) % 360} 37% 25%)"/>
      <circle cx="${Math.min(width, height) * .05}" cy="28" r="${Math.min(width, height) * .04}" fill="hsl(${(hue + 118) % 360} 36% 24%)"/>
    </g>
    <path d="M${Math.round(width * .68)} ${Math.round(foregroundY * .94)} h${Math.round(width * .13)} v${Math.round(height * .085)} h-${Math.round(width * .13)}z" fill="hsl(${(hue + 25) % 360} 38% 46%)" opacity=".9"/>
    <path d="M${Math.round(width * .665)} ${Math.round(foregroundY * .94)} l${Math.round(width * .08)} -${Math.round(height * .065)} l${Math.round(width * .075)} ${Math.round(height * .065)}z" fill="hsl(${(hue + 8) % 360} 25% 25%)"/>
    <rect width="${width}" height="${height}" filter="url(#grain)" opacity="1"/>
    ${size === 'full' ? `<g opacity=".5"><rect x="${width * .025}" y="${height * .94}" width="${Math.min(width * .38, 520)}" height="${height * .036}" rx="${height * .012}" fill="#000" opacity=".28"/><text x="${width * .04}" y="${height * .965}" fill="#fff" font-family="system-ui,sans-serif" font-size="${Math.max(16, height * .018)}">${label}</text></g>` : ''}
  </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function visual(asset: DemoVisualAsset, size: VisualSize): string {
  const source = inferredShape(asset);
  if (source.type === 'VIDEO') return size === 'preview' ? '/demo-fixtures/video-poster.jpg' : '/demo-fixtures/clip.mp4';
  const key = `${size}:${asset.id}:${asset.width ?? ''}:${asset.height ?? ''}:${asset.asset_type ?? asset.type ?? ''}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const value = buildSvg(asset, size);
  cache.set(key, value);
  return value;
}

export function demoAssetPreview(asset: DemoVisualAsset): string {
  return visual(asset, 'preview');
}

export function demoAssetFullSize(asset: DemoVisualAsset): string {
  return visual(asset, 'full');
}
