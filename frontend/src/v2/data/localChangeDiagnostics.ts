import { requestJson } from '../../../lib/api/http';

export type LocalChangeDiagnostics = {
  available: boolean;
  selectedAssetId: string;
  referenceAssetId: string;
  changedPercent: number | null;
  localizedChangedPercent: number | null;
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
  rows: number;
  columns: number;
  cells: number[][];
  source: 'original' | 'transcoded' | 'preview' | null;
};

export async function loadLocalChangeDiagnostics(
  selectedAssetId: string,
  referenceAssetId: string,
  signal?: AbortSignal,
): Promise<LocalChangeDiagnostics> {
  const params = new URLSearchParams({
    selected_asset_id: selectedAssetId,
    reference_asset_id: referenceAssetId,
  });
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
    rows: value.rows,
    columns: value.columns,
    cells: value.cells,
    source: value.source,
  };
}
