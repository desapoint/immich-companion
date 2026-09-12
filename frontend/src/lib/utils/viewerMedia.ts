const HEIC_MIME_TYPES = new Set(['image/heic', 'image/heif']);
const BROWSER_IMAGE_MIME_TYPES = new Set([
  'image/avif',
  'image/bmp',
  'image/gif',
  'image/jpeg',
  'image/png',
  'image/svg+xml',
  'image/webp',
  'image/x-icon',
]);

// Same tiny, valid HEIC image used by Immich to test actual browser decode support.
const HEIC_PROBE_DATA_URL =
  'data:image/heic;base64,AAAAGGZ0eXBoZWljAAAAAG1pZjFoZWljAAABrW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAHBpY3QAAAAAAAAAAAAAAAAAAAAADnBpdG0AAAAAAAIAAAAQaWRhdAAAAAAAAQABAAAAOGlsb2MBAAAAREAAAgABAAAAAAAAAc0AAQAAAAAAAAAsAAIAAQAAAAAAAAABAAAAAAAAAAgAAAA4aWluZgAAAAAAAgAAABVpbmZlAgAAAQABAABodmMxAAAAABVpbmZlAgAAAAACAABncmlkAAAAANhpcHJwAAAAtmlwY28AAAB2aHZjQwEDcAAAAAAAAAAAAB7wAPz9+PgAAA8DIAABABhAAQwB//8DcAAAAwCQAAADAAADAB66AkAhAAEAKkIBAQNwAAADAJAAAAMAAAMAHqAggQWW6q6a5uBAQMCAAAADAIAAAAMAhCIAAQAGRAHBc8GJAAAAFGlzcGUAAAAAAAAAAQAAAAEAAAAUaXNwZQAAAAAAAABAAAAAQAAAABBwaXhpAAAAAAMICAgAAAAaaXBtYQAAAAAAAAACAAECgQMAAgIChAAAABppcmVmAAAAAAAAAA5kaW1nAAIAAQABAAAANG1kYXQAAAAoKAGvCchMZYA50NoPIfzz81Qfsm577GJt3lf8kLAr+NbNIoeRR7JeYA==';

let heicSupportPromise: Promise<boolean> | null = null;

export function assetThumbnailUrl(
  assetId: string,
  size: 'thumbnail' | 'preview' | 'fullsize',
): string {
  return `/api/assets/${encodeURIComponent(assetId)}/thumbnail?size=${size}`;
}

export function assetOriginalUrl(assetId: string): string {
  return `/api/assets/${encodeURIComponent(assetId)}/original`;
}

export function assetVideoPlaybackUrl(assetId: string): string {
  return `/api/assets/${encodeURIComponent(assetId)}/video/playback`;
}

export function isHeicMimeType(mimeType: string | null | undefined): boolean {
  return mimeType !== null && mimeType !== undefined && HEIC_MIME_TYPES.has(mimeType.toLowerCase());
}

export function isBrowserImageMimeType(mimeType: string | null | undefined): boolean {
  if (!mimeType) return true;
  const normalized = mimeType.split(';', 1)[0]?.trim().toLowerCase() ?? '';
  return HEIC_MIME_TYPES.has(normalized) || BROWSER_IMAGE_MIME_TYPES.has(normalized);
}

export function probeHeicSupport(): Promise<boolean> {
  if (heicSupportPromise) return heicSupportPromise;
  if (typeof Image === 'undefined') return Promise.resolve(false);

  heicSupportPromise = new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(true);
    image.onerror = () => resolve(false);
    image.src = HEIC_PROBE_DATA_URL;
  });
  return heicSupportPromise;
}

export function buildViewerMediaUrls(
  assetId: string,
  mimeType: string | null | undefined,
  heicSupported: boolean,
): string[] {
  const fallbackUrls = [
    assetThumbnailUrl(assetId, 'fullsize'),
    assetThumbnailUrl(assetId, 'preview'),
  ];
  if (!isBrowserImageMimeType(mimeType)) return fallbackUrls;
  if (isHeicMimeType(mimeType) && !heicSupported) return fallbackUrls;
  return [assetOriginalUrl(assetId), ...fallbackUrls];
}

export async function resolveViewerMediaUrls(
  assetId: string,
  mimeType: string | null | undefined,
): Promise<string[]> {
  const heicSupported = isHeicMimeType(mimeType) ? await probeHeicSupport() : true;
  return buildViewerMediaUrls(assetId, mimeType, heicSupported);
}
