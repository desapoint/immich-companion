import { jsonRequest, requestJson } from '../../../lib/api/http';
import type { SimilarityValidationMode } from '../types/contracts';

type ApiDuplicateDiscoverySettings = {
  include_exact: boolean;
  include_similar: boolean;
  similarity_threshold: number;
  maximum_perceptual_distance?: number;
  validation_mode: SimilarityValidationMode;
  max_link_depth?: number;
  max_candidates: number;
};

export type DuplicateDiscoverySettings = {
  includeExact: boolean;
  includeSimilar: boolean;
  similarityThreshold: number;
  maximumPerceptualDistance: number;
  validationMode: SimilarityValidationMode;
  maxLinkDepth: number;
  maxCandidates: number;
};

function normalize(value: ApiDuplicateDiscoverySettings): DuplicateDiscoverySettings {
  return {
    includeExact: value.include_exact,
    includeSimilar: value.include_similar,
    similarityThreshold: value.similarity_threshold,
    maximumPerceptualDistance: value.maximum_perceptual_distance ?? 12,
    validationMode: value.validation_mode,
    maxLinkDepth: value.max_link_depth ?? 2,
    maxCandidates: value.max_candidates,
  };
}

function payload(value: DuplicateDiscoverySettings): ApiDuplicateDiscoverySettings {
  return {
    include_exact: value.includeExact,
    include_similar: value.includeSimilar,
    similarity_threshold: value.similarityThreshold,
    maximum_perceptual_distance: value.maximumPerceptualDistance,
    validation_mode: value.validationMode,
    max_link_depth: value.maxLinkDepth,
    max_candidates: value.maxCandidates,
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
};
