import type { AssetRecord, DuplicateSimilarityEvidence } from './contracts';
import { formatBytes } from '../../lib/utils/fileSize';
import { duplicateAssetSourceLabel } from './duplicatePresentation';

export const FULL_RESOLUTION_VALIDATION_PIXEL_LIMIT = 64_000_000;

export type SimilarityValidationEvidenceTier = 'bounded' | 'full-resolution' | 'search-only';
export type SimilarityValidationSide = 'member' | 'reference';

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

export function linkedIntermediateCount(linkDepth: number): number {
  return Math.max(0, linkDepth - 1);
}

export function formatImageDimensions(
  width: number | null | undefined,
  height: number | null | undefined,
): string | null {
  if (!Number.isFinite(width) || !Number.isFinite(height) || (width ?? 0) <= 0 || (height ?? 0) <= 0) return null;
  return `${Math.trunc(width as number)} × ${Math.trunc(height as number)}`;
}

export function similarityValidatedDimensions(
  evidence: Pick<DuplicateSimilarityEvidence, 'validatedWidth' | 'validatedHeight' | 'referenceValidatedWidth' | 'referenceValidatedHeight'> | null | undefined,
  side: SimilarityValidationSide = 'member',
): string | null {
  if (!evidence) return null;
  return side === 'reference'
    ? formatImageDimensions(evidence.referenceValidatedWidth, evidence.referenceValidatedHeight)
    : formatImageDimensions(evidence.validatedWidth, evidence.validatedHeight);
}

export function similarityValidationEvidenceTier(
  similarityPercent: number | null,
  evidence: Pick<DuplicateSimilarityEvidence, 'detailSource'> | null | undefined,
): SimilarityValidationEvidenceTier | null {
  if (similarityPercent === null) return null;
  if (evidence?.detailSource === 'preview') return 'bounded';
  if (evidence?.detailSource === 'original' || evidence?.detailSource === 'transcoded') return 'full-resolution';
  return 'search-only';
}

export function similarityValidationEvidenceLabel(
  similarityPercent: number | null,
  evidence: Pick<DuplicateSimilarityEvidence, 'detailSource'> | null | undefined,
): string | null {
  const tier = similarityValidationEvidenceTier(similarityPercent, evidence);
  if (tier === 'bounded') return 'Bounded validation';
  if (tier === 'full-resolution') return 'Full-resolution validation';
  if (tier === 'search-only') return 'Search-only appearance';
  return null;
}

export function usesBoundedValidation(
  value:
    | Pick<AssetRecord, 'width' | 'height'>
    | Pick<DuplicateSimilarityEvidence, 'detailSource'>
    | null
    | undefined,
): boolean {
  return Boolean(value && 'detailSource' in value && value.detailSource === 'preview');
}

export function duplicateListMemberMeta(
  asset: Pick<AssetRecord, 'library_id' | 'file_size_bytes' | 'width' | 'height'>,
  similarityPercent: number | null,
): string {
  const parts = [duplicateAssetSourceLabel(asset.library_id), formatBytes(asset.file_size_bytes)];
  if (similarityPercent !== null) parts.push(`${formatSimilarityPercent(similarityPercent)} similarity`);
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
    dims: formatImageDimensions(asset?.width, asset?.height) ?? '—',
    taken: formatDate(asset?.file_created_at),
    codec: asset?.original_mime_type ?? 'Unknown type',
    library,
    libraryId,
    folder,
    uploaded: formatDate(asset?.immich_created_at),
    similarity: formatSimilarityPercent(similarityPercent),
  };
}
