import { duplicateDiscoverySettingsRepository } from '../api/duplicateDiscoverySettingsRepository';
import type { SimilarityValidationMode } from '../types/contracts';
import type { OperationRunOptions } from '../../../lib/state/operationController.svelte';
import { errorMessage } from '../../../lib/api/mutationFeedback';

export type DuplicateDiscoveryState = {
  includeExact: boolean;
  includeSimilar: boolean;
  similarityThreshold: string;
  maximumPerceptualDistance: string;
  validationMode: SimilarityValidationMode;
  maxLinkDepth: string;
  maxCandidates: string;
  maximumMatches: string;
};

type DiscoveryProgress = {
  label: string;
  detail: string;
  completed: number;
  total: number | null;
  percent: number | null;
};

type DiscoveryResult = {
  groupCount: number;
  candidateCount: number;
  retainedMatchCount: number | null;
  retainedMatchLimit: number | null;
  retentionLimitReached: boolean | null;
};

type DiscoveryDependencies = {
  getState: () => DuplicateDiscoveryState;
  setState: (state: DuplicateDiscoveryState) => void;
  isReady: () => boolean;
  isMutating: () => boolean;
  clearOutcome: () => void;
  setError: (message: string) => void;
  setSummary: (summary: string) => void;
  setResult: (result: DiscoveryResult | null) => void;
  resetWorkspace: () => void;
  pending: (action: string) => OperationRunOptions<DiscoveryResult>['pending'];
  runOperation: <T>(action: string, runner: () => Promise<T>, options: OperationRunOptions<T>) => Promise<T | null>;
  runDiscovery: (options: {
    similarityThreshold: number;
    maximumPerceptualDistance: number;
    validationMode: SimilarityValidationMode;
    maxLinkDepth: number;
    anchorAssetId?: string;
    includeSimilar: boolean;
    includeExact: boolean;
    maxCandidates: number;
    maximumMatches: number;
  }, onProgress: (progress: DiscoveryProgress) => void) => Promise<DiscoveryResult>;
  reconcile: () => Promise<void>;
  updateProgress: (progress: DiscoveryProgress) => void;
  startProgress: () => void;
  finishProgress: () => void;
};

export class DuplicateDiscoveryController {
  constructor(private readonly dependencies: DiscoveryDependencies) {}

  async run(anchorAssetId?: string): Promise<void> {
    const { dependencies } = this;
    if (!dependencies.isReady() || dependencies.isMutating()) return;

    dependencies.clearOutcome();
    dependencies.setError('');
    dependencies.setResult(null);
    dependencies.startProgress();
    try {
      const current = dependencies.getState();
      const normalizedThreshold = Math.min(100, Math.max(50, Number(current.similarityThreshold) || 95));
      const normalizedPerceptualDistance = Math.min(64, Math.max(0, Math.round(Number(current.maximumPerceptualDistance) || 0)));
      const normalizedCandidates = Math.min(64, Math.max(1, Math.round(Number(current.maxCandidates) || 8)));
      const normalizedMaximumMatches = Math.min(50_000, Math.max(1, Math.round(Number(current.maximumMatches) || 5000)));
      const normalizedLinkDepth = Math.min(64, Math.max(0, Math.round(Number(current.maxLinkDepth) || 0)));
      dependencies.setState({
        ...current,
        similarityThreshold: String(normalizedThreshold),
        maximumPerceptualDistance: String(normalizedPerceptualDistance),
        maxLinkDepth: String(normalizedLinkDepth),
        maxCandidates: String(normalizedCandidates),
        maximumMatches: String(normalizedMaximumMatches),
      });

      const state = dependencies.getState();
      if (!anchorAssetId) {
        try {
          const saved = await duplicateDiscoverySettingsRepository.patchDiscovery({
            includeExact: state.includeExact,
            includeSimilar: state.includeSimilar,
            similarityThreshold: normalizedThreshold,
            maximumPerceptualDistance: normalizedPerceptualDistance,
            validationMode: state.validationMode,
            maxLinkDepth: normalizedLinkDepth,
            maxCandidates: normalizedCandidates,
            maximumMatches: normalizedMaximumMatches,
          });
          dependencies.setState({
            ...state,
            includeExact: saved.includeExact,
            includeSimilar: saved.includeSimilar,
            similarityThreshold: String(saved.similarityThreshold),
            maximumPerceptualDistance: String(saved.maximumPerceptualDistance),
            validationMode: saved.validationMode,
            maxLinkDepth: String(saved.maxLinkDepth),
            maxCandidates: String(saved.maxCandidates),
            maximumMatches: String(saved.maximumMatches),
          });
        } catch (error) {
          dependencies.setError(errorMessage(error, 'Discovery settings could not be saved to Companion. Discovery was not started.'));
          return;
        }
      }

      const finalState = dependencies.getState();
      const result = await dependencies.runOperation('Duplicate discovery',
        () => dependencies.runDiscovery({
          similarityThreshold: normalizedThreshold,
          maximumPerceptualDistance: normalizedPerceptualDistance,
          validationMode: finalState.validationMode,
          maxLinkDepth: normalizedLinkDepth,
          anchorAssetId,
          includeSimilar: finalState.includeSimilar,
          includeExact: finalState.includeExact,
          maxCandidates: normalizedCandidates,
          maximumMatches: normalizedMaximumMatches,
        }, dependencies.updateProgress),
        {
          pending: dependencies.pending('Duplicate discovery'),
          outcome: (result) => {
            const retained = result.retainedMatchCount;
            const limit = result.retainedMatchLimit;
            const retentionState = result.retentionLimitReached === true
              ? 'retention limit reached'
              : result.retentionLimitReached === false
                ? 'retention limit not reached'
                : 'retention limit status unavailable';
            const retention = retained === null || limit === null
              ? ''
              : ` · ${retained.toLocaleString()} / ${limit.toLocaleString()} matches retained · ${retentionState}`;
            return {
              tone: result.retentionLimitReached === true ? 'warn' : result.retentionLimitReached === null ? 'warn' : 'ok',
              title: result.retentionLimitReached === true
                ? 'Discovery completed · retention limit reached'
                : result.retentionLimitReached === null
                  ? 'Discovery completed · retention status unavailable'
                  : 'Discovery completed',
              detail: `${result.groupCount} groups · ${result.candidateCount} candidates${retention}`,
              failures: [],
            };
          },
          onOutcome: (outcome) => {
            dependencies.setSummary(outcome.detail);
            dependencies.resetWorkspace();
          },
          reconcile: () => {
            dependencies.updateProgress({ label: 'Duplicate discovery · Refreshing results', detail: 'Loading the newly completed duplicate groups for refresh…', completed: 1, total: 1, percent: 99 });
            return dependencies.reconcile();
          },
          reconcileError: 'Duplicate discovery completed, but the latest groups could not be loaded.',
        });
      if (result) dependencies.setResult(result);
    } finally {
      dependencies.finishProgress();
    }
  }
}
