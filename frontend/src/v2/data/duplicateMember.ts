import type { AssetRecord } from './contracts';
import { formatBytes } from '../../lib/utils/fileSize';
import { duplicateAssetSourceLabel } from './duplicatePresentation';

export const FULL_RESOLUTION_VALIDATION_PIXEL_LIMIT = 64_000_000;

export type ComparisonMemberData = {
  name: string;
  source: string;
  size: string;
  sizeBytes: number | null;
  dims: string;
  taken: string;
  codec: string;
  library: string;
  libraryId: string | null;
  folder: string;
  uploaded: string;
  similarity: string;
};

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

const similarityNumberFormat = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function formatSimilarityPercent(value: number | null): string {
  return value === null ? 'Not calculated' : `${similarityNumberFormat.format(value)}%`;
}

export function usesBoundedValidation(
  asset: Pick<AssetRecord, 'width' | 'height'> | null | undefined,
): boolean {
  return Boolean(
    asset?.width
    && asset?.height
    && asset.width * asset.height > FULL_RESOLUTION_VALIDATION_PIXEL_LIMIT
  );
}

export function duplicateListMemberMeta(
  asset: Pick<AssetRecord, 'library_id' | 'file_size_bytes' | 'width' | 'height'>,
  similarityPercent: number | null,
): string {
  const parts = [duplicateAssetSourceLabel(asset.library_id), formatBytes(asset.file_size_bytes)];
  if (similarityPercent !== null) parts.push(`${formatSimilarityPercent(similarityPercent)} similarity`);
  if (similarityPercent !== null && usesBoundedValidation(asset)) parts.push('bounded validation');
  return parts.join(' · ');
}

export function assetFolder(path: string | null | undefined): string | null {
  if (!path) return null;
  const normalized = path.replaceAll('\\', '/').replace(/\/+$/, '');
  const separator = normalized.lastIndexOf('/');
  if (separator < 0) return null;
  return normalized.slice(0, separator) || '/';
}

export function comparisonMemberData(
  asset: AssetRecord | undefined,
  similarityPercent: number | null,
  libraryNames: ReadonlyMap<string, string> = new Map(),
): ComparisonMemberData {
  const sizeBytes = asset?.file_size_bytes ?? null;
  const libraryId = asset?.library_id ?? null;
  const library = libraryId ? (libraryNames.get(libraryId) ?? `Library ${libraryId}`) : 'Immich uploads';
  const folder = assetFolder(asset?.original_path) ?? 'Unavailable';
  return {
    name: asset?.original_file_name ?? 'Unknown asset',
    source: duplicateAssetSourceLabel(libraryId, libraryId ? library : undefined),
    size: formatBytes(sizeBytes),
    sizeBytes,
    dims: asset?.width && asset?.height ? `${asset.width} × ${asset.height}` : '—',
    taken: formatDate(asset?.file_created_at),
    codec: asset?.original_mime_type ?? 'Unknown type',
    library,
    libraryId,
    folder,
    uploaded: formatDate(asset?.immich_created_at),
    similarity: formatSimilarityPercent(similarityPercent),
  };
}
