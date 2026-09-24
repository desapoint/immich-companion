import { jsonRequest, requestJson } from '../../../lib/api/http';

export type ComparisonAlignmentSettings = {
  maxDisplacementPercent: number;
  maxRotationDegrees: number;
  maxZoomPercent: number;
};

type ApiComparisonAlignmentSettings = {
  comparison_max_displacement_percent: number;
  comparison_max_rotation_degrees: number;
  comparison_max_zoom_percent: number;
};

function normalize(value: ApiComparisonAlignmentSettings): ComparisonAlignmentSettings {
  return {
    maxDisplacementPercent: value.comparison_max_displacement_percent,
    maxRotationDegrees: value.comparison_max_rotation_degrees,
    maxZoomPercent: value.comparison_max_zoom_percent ?? 0,
  };
}

function payload(value: ComparisonAlignmentSettings): ApiComparisonAlignmentSettings {
  return {
    comparison_max_displacement_percent: value.maxDisplacementPercent,
    comparison_max_rotation_degrees: value.maxRotationDegrees,
    comparison_max_zoom_percent: value.maxZoomPercent,
  };
}

export const comparisonAlignmentSettingsRepository = {
  async load(signal?: AbortSignal): Promise<ComparisonAlignmentSettings> {
    return normalize(await requestJson<ApiComparisonAlignmentSettings>(
      '/api/settings/duplicates/comparison-alignment',
      { signal },
    ));
  },

  async save(value: ComparisonAlignmentSettings): Promise<ComparisonAlignmentSettings> {
    return normalize(await requestJson<ApiComparisonAlignmentSettings>(
      '/api/settings/duplicates/comparison-alignment',
      jsonRequest('PUT', payload(value)),
    ));
  },
};
