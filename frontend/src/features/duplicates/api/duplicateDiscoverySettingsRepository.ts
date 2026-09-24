import { jsonRequest, requestJson } from '../../../lib/api/http';
import type { SimilarityValidationMode } from '../types/contracts';

type ApiDuplicateDiscoverySettings = {
  include_exact: boolean;
  include_similar: boolean;
  similarity_threshold: number;
  maximum_perceptual_distance?: number;
  comparison_max_displacement_percent?: number;
  comparison_max_rotation_degrees?: number;
  comparison_max_zoom_percent?: number;
  validation_mode: SimilarityValidationMode;
  max_link_depth?: number;
  max_candidates: number;
  maximum_matches?: number;
};

export type DuplicateDiscoverySettings = {
  includeExact: boolean;
  includeSimilar: boolean;
  similarityThreshold: number;
  maximumPerceptualDistance: number;
  comparisonMaxDisplacementPercent: number;
  comparisonMaxRotationDegrees: number;
  comparisonMaxZoomPercent: number;
  validationMode: SimilarityValidationMode;
  maxLinkDepth: number;
  maxCandidates: number;
  maximumMatches: number;
};

export type DuplicateDiscoverySettingsPatch = Pick<
  DuplicateDiscoverySettings,
  | 'includeExact'
  | 'includeSimilar'
  | 'similarityThreshold'
  | 'maximumPerceptualDistance'
  | 'validationMode'
  | 'maxLinkDepth'
  | 'maxCandidates'
  | 'maximumMatches'
>;

function normalize(value: ApiDuplicateDiscoverySettings): DuplicateDiscoverySettings {
  return {
    includeExact: value.include_exact,
    includeSimilar: value.include_similar,
    similarityThreshold: value.similarity_threshold,
    maximumPerceptualDistance: value.maximum_perceptual_distance ?? 12,
    comparisonMaxDisplacementPercent: value.comparison_max_displacement_percent ?? 10,
    comparisonMaxRotationDegrees: value.comparison_max_rotation_degrees ?? 0,
    comparisonMaxZoomPercent: value.comparison_max_zoom_percent ?? 0,
    validationMode: value.validation_mode,
    maxLinkDepth: value.max_link_depth ?? 2,
    maxCandidates: value.max_candidates,
    maximumMatches: value.maximum_matches ?? 5000,
  };
}

function payload(value: DuplicateDiscoverySettings): ApiDuplicateDiscoverySettings {
  return {
    include_exact: value.includeExact,
    include_similar: value.includeSimilar,
    similarity_threshold: value.similarityThreshold,
    maximum_perceptual_distance: value.maximumPerceptualDistance,
    comparison_max_displacement_percent: value.comparisonMaxDisplacementPercent,
    comparison_max_rotation_degrees: value.comparisonMaxRotationDegrees,
    comparison_max_zoom_percent: value.comparisonMaxZoomPercent,
    validation_mode: value.validationMode,
    max_link_depth: value.maxLinkDepth,
    max_candidates: value.maxCandidates,
    maximum_matches: value.maximumMatches,
  };
}

export const duplicateDiscoverySettingsRepository = {
  async load(signal?: AbortSignal): Promise<DuplicateDiscoverySettings> {
    return normalize(
      await requestJson<ApiDuplicateDiscoverySettings>(
        '/api/settings/duplicates/discovery',
        { signal },
      ),
    );
  },

  async save(value: DuplicateDiscoverySettings): Promise<DuplicateDiscoverySettings> {
    return normalize(
      await requestJson<ApiDuplicateDiscoverySettings>(
        '/api/settings/duplicates/discovery',
        jsonRequest('PUT', payload(value)),
      ),
    );
  },

  async patchDiscovery(value: DuplicateDiscoverySettingsPatch): Promise<DuplicateDiscoverySettings> {
    return normalize(
      await requestJson<ApiDuplicateDiscoverySettings>(
        '/api/settings/duplicates/discovery',
        jsonRequest('PATCH', {
          include_exact: value.includeExact,
          include_similar: value.includeSimilar,
          similarity_threshold: value.similarityThreshold,
          maximum_perceptual_distance: value.maximumPerceptualDistance,
          validation_mode: value.validationMode,
          max_link_depth: value.maxLinkDepth,
          max_candidates: value.maxCandidates,
          maximum_matches: value.maximumMatches,
        }),
      ),
    );
  },
};
