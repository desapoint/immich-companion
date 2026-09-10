import { libraryData } from './currentDataSource.svelte';

export type ComparisonMemberData = {
  name: string;
  source: string;
  size: string;
  sizeNum: number;
  dims: string;
  taken: string;
  codec: string;
  library: string;
  uploaded: string;
  similarity: string;
};

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

export async function comparisonMemberData(assetId: string, similarityPercent: number): Promise<ComparisonMemberData> {
  const asset = await libraryData.assets.getById(assetId);
  const sizeNum = (asset?.file_size_bytes ?? 0) / 1_048_576;
  const library = asset?.library_id ? 'External library' : 'Default library';
  return {
    name: asset?.original_file_name ?? 'Unknown asset',
    source: library,
    size: asset?.file_size_bytes ? `${sizeNum.toFixed(1)} MB` : '—',
    sizeNum,
    dims: asset?.width && asset?.height ? `${asset.width} × ${asset.height}` : '—',
    taken: formatDate(asset?.file_created_at),
    codec: asset?.original_mime_type ?? 'Unknown type',
    library,
    uploaded: formatDate(asset?.immich_created_at),
    similarity: similarityPercent.toFixed(1),
  };
}
