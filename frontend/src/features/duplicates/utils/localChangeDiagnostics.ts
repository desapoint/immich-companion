import { requestJson } from '../../../lib/api/http';

export type LocalChangeDiagnostics = {
  available: boolean;
  selectedAssetId: string;
  referenceAssetId: string;
  changedPercent: number | null;
  localizedChangedPercent: number | null;
  coherentChangedPercent?: number | null;
  largestChangedRegionPercent?: number | null;
  substantialRegionCount?: number | null;
  alignedChangedPercent?: number | null;
  rawSimilarityPercent?: number | null;
  alignedSimilarityPercent?: number | null;
  alignmentApplied?: boolean;
  alignmentShiftPercent?: number | null;
  alignmentRotationDegrees?: number;
  alignmentOverlapPercent?: number | null;
  comparisonMaxDisplacementPercent?: number;
  comparisonMaxRotationDegrees?: number;
  rows: number;
  columns: number;
  cells: number[][];
  source: 'original' | 'transcoded' | 'preview' | null;
};

type ApiLocalChangeDiagnostics = {
  available: boolean;
  selected_asset_id: string;
  reference_asset_id: string;
  changed_percent: number | null;
  localized_changed_percent: number | null;
  coherent_changed_percent?: number | null;
  largest_changed_region_percent?: number | null;
  substantial_region_count?: number | null;
  aligned_changed_percent?: number | null;
  raw_similarity_percent?: number | null;
  aligned_similarity_percent?: number | null;
  alignment_applied?: boolean;
  alignment_shift_percent?: number | null;
  alignment_rotation_degrees?: number;
  alignment_overlap_percent?: number | null;
  comparison_max_displacement_percent?: number;
  comparison_max_rotation_degrees?: number;
  rows: number;
  columns: number;
  cells: number[][];
  source: 'original' | 'transcoded' | 'preview' | null;
};

export async function loadLocalChangeDiagnostics(
  selectedAssetId: string,
  referenceAssetId: string,
  signal?: AbortSignal,
  settings?: { maxDisplacementPercent: number; maxRotationDegrees: number },
): Promise<LocalChangeDiagnostics> {
  const params = new URLSearchParams({
    selected_asset_id: selectedAssetId,
    reference_asset_id: referenceAssetId,
  });
  if (settings) {
    params.set('comparison_max_displacement_percent', String(settings.maxDisplacementPercent));
    params.set('comparison_max_rotation_degrees', String(settings.maxRotationDegrees));
  }
  const value = await requestJson<ApiLocalChangeDiagnostics>(
    `/api/v2/duplicates/similarity-local-changes?${params.toString()}`,
    { signal },
  );
  return {
    available: value.available,
    selectedAssetId: value.selected_asset_id,
    referenceAssetId: value.reference_asset_id,
    changedPercent: value.changed_percent,
    localizedChangedPercent: value.localized_changed_percent,
    coherentChangedPercent: value.coherent_changed_percent ?? null,
    largestChangedRegionPercent: value.largest_changed_region_percent ?? null,
    substantialRegionCount: value.substantial_region_count ?? null,
    alignedChangedPercent: value.aligned_changed_percent ?? null,
    rawSimilarityPercent: value.raw_similarity_percent ?? null,
    alignedSimilarityPercent: value.aligned_similarity_percent ?? null,
    alignmentApplied: value.alignment_applied ?? false,
    alignmentShiftPercent: value.alignment_shift_percent ?? null,
    alignmentRotationDegrees: value.alignment_rotation_degrees ?? 0,
    alignmentOverlapPercent: value.alignment_overlap_percent ?? null,
    comparisonMaxDisplacementPercent: value.comparison_max_displacement_percent,
    comparisonMaxRotationDegrees: value.comparison_max_rotation_degrees,
    rows: value.rows,
    columns: value.columns,
    cells: value.cells,
    source: value.source,
  };
}
