import { mutationFeedback, pendingOperationFeedback, type OperationFeedback } from '../data/mutationFeedback';
import type { AssetSelectionTarget, MutationResult } from '../data/contracts';
import { OperationController } from './operationController.svelte';

export type AssetMutationRunner = (target: AssetSelectionTarget) => Promise<MutationResult>;
export type AssetMutationPhase = 'idle' | 'applying' | 'refreshing';
export type AssetMutationRunOptions = {
  refresh?: (result: MutationResult) => Promise<void>;
  refreshError?: string;
};

export class AssetMutationController {
  private readonly operation = new OperationController();

  constructor(private refresh: () => Promise<void>, private onSummary: (summary: string) => void) {}

  get feedback(): OperationFeedback | null { return this.operation.feedback; }
  set feedback(value: OperationFeedback | null) { this.operation.feedback = value; }
  get error(): string { return this.operation.error; }
  set error(value: string) { this.operation.error = value; }
  get busy(): boolean { return this.operation.busy; }
  get phase(): AssetMutationPhase {
    return this.operation.phase === 'reconciling' ? 'refreshing' : this.operation.phase;
  }
  get action(): string { return this.operation.action; }
  get retry(): (() => Promise<void>) | null { return this.operation.retry; }

  clearError(): void { this.operation.clearError(); }
  clearOutcome(): void { this.operation.clearOutcome(); }

  async run(action: string, runner: AssetMutationRunner, target: AssetSelectionTarget, options: AssetMutationRunOptions = {}): Promise<MutationResult | null> {
    return this.operation.run(action, () => runner(target), {
      pending: (phase) => pendingOperationFeedback(action, phase === 'applying' ? 'applying' : 'refreshing'),
      outcome: (result) => mutationFeedback(action, result),
      onOutcome: (feedback) => this.onSummary(feedback.detail),
      retry: (result) => result.failed.length
        ? () => this.run(action, runner, { kind: 'ids', ids: result.failed.map((failure) => failure.id) }, options).then(() => {})
        : null,
      reconcile: options.refresh ? (result) => options.refresh!(result) : () => this.refresh(),
      reconcileError: options.refreshError ?? `${action} was applied, but the latest asset state could not be loaded.`,
    });
  }
}
