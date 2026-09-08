import { errorMessage, type OperationFeedback } from '../data/mutationFeedback';

export type OperationPhase = 'idle' | 'applying' | 'reconciling';

export type OperationRunOptions<TResult> = {
  pending: (phase: Exclude<OperationPhase, 'idle'>) => OperationFeedback;
  outcome: (result: TResult) => OperationFeedback;
  reconcile?: (result: TResult) => Promise<void>;
  reconcileError?: string;
  retry?: (result: TResult) => (() => Promise<void>) | null;
  onOutcome?: (feedback: OperationFeedback, result: TResult) => void;
};

export class OperationController {
  feedback = $state<OperationFeedback | null>(null);
  error = $state('');
  busy = $state(false);
  phase = $state<OperationPhase>('idle');
  action = $state('');
  retry = $state<(() => Promise<void>) | null>(null);

  clearError(): void {
    this.error = '';
  }

  setError(error: unknown, fallback = 'The operation could not be completed.'): void {
    this.feedback = null;
    this.error = errorMessage(error, fallback);
  }

  clearOutcome(): void {
    this.feedback = null;
    this.error = '';
    this.retry = null;
  }

  async run<TResult>(action: string, runner: () => Promise<TResult>, options: OperationRunOptions<TResult>): Promise<TResult | null> {
    if (this.busy) return null;
    this.busy = true;
    this.phase = 'applying';
    this.action = action;
    this.error = '';
    this.feedback = options.pending('applying');
    this.retry = null;

    try {
      let result: TResult;
      try {
        result = await runner();
      } catch (error) {
        this.feedback = null;
        this.error = errorMessage(error, `${action} could not be completed.`);
        return null;
      }

      const outcome = options.outcome(result);
      options.onOutcome?.(outcome, result);
      this.retry = options.retry?.(result) ?? null;

      if (options.reconcile) {
        this.phase = 'reconciling';
        this.feedback = options.pending('reconciling');
        try {
          await options.reconcile(result);
        } catch (error) {
          const context = options.reconcileError ?? `${action} was applied, but the latest state could not be loaded.`;
          const detail = errorMessage(error, '');
          this.error = detail ? `${context} ${detail}` : context;
        }
      }

      this.feedback = outcome;
      return result;
    } finally {
      this.busy = false;
      this.phase = 'idle';
      this.action = '';
    }
  }
}
