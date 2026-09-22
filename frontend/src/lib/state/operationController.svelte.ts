import { errorMessage, type OperationFeedback } from '../api/mutationFeedback';

export type OperationPhase = 'idle' | 'applying' | 'reconciling';
export type OperationErrorHandler = (message: string) => void;

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
  reconciling = $state(false);
  phase = $state<OperationPhase>('idle');
  action = $state('');
  retry = $state<(() => Promise<void>) | null>(null);
  private revision = 0;
  private pendingReconcile: { run: () => Promise<void>; context: string; revision: number; outcome: OperationFeedback | null } | null = null;
  private reconcileTask: Promise<void> | null = null;

  constructor(private readonly onError?: OperationErrorHandler) {}

  private publishError(message: string): void {
    this.error = message;
    if (message) this.onError?.(message);
  }

  clearError(): void {
    this.error = '';
  }

  setError(error: unknown, fallback = 'The operation could not be completed.'): void {
    this.feedback = null;
    this.publishError(errorMessage(error, fallback));
  }

  clearOutcome(): void {
    this.revision += 1;
    this.feedback = null;
    this.error = '';
    this.retry = null;
  }

  private scheduleReconcile(run: () => Promise<void>, context: string, revision: number, outcome: OperationFeedback, pending: OperationFeedback): void {
    // A refresh loads the current collection, so only the newest queued refresh
    // is useful. Keep one active request and one trailing request at most.
    this.pendingReconcile = { run, context, revision, outcome };
    this.reconciling = true;
    this.phase = 'reconciling';
    this.feedback = pending;
    if (this.reconcileTask) return;
    this.reconcileTask = Promise.resolve().then(() => this.drainReconciles());
  }

  private async drainReconciles(): Promise<void> {
    try {
      while (this.pendingReconcile) {
        const job = this.pendingReconcile;
        this.pendingReconcile = null;
        try {
          await job.run();
          if (job.revision === this.revision) this.feedback = job.outcome;
        } catch (error) {
          if (job.revision === this.revision) {
            this.feedback = job.outcome;
            const detail = errorMessage(error, '');
            this.publishError(detail ? `${job.context} ${detail}` : job.context);
          }
        }
      }
    } finally {
      this.reconcileTask = null;
      this.reconciling = false;
      if (!this.pendingReconcile) {
        this.busy = false;
        this.phase = 'idle';
        this.action = '';
      }
    }
  }

  async waitForReconciliation(): Promise<void> {
    await this.reconcileTask;
  }

  async run<TResult>(action: string, runner: () => Promise<TResult>, options: OperationRunOptions<TResult>): Promise<TResult | null> {
    if (this.busy) return null;
    const revision = ++this.revision;
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
        this.publishError(errorMessage(error, `${action} could not be completed.`));
        return null;
      }

      const outcome = options.outcome(result);
      options.onOutcome?.(outcome, result);
      this.retry = options.retry?.(result) ?? null;

      this.feedback = outcome;
      if (options.reconcile) {
        this.scheduleReconcile(
          () => options.reconcile!(result),
          options.reconcileError ?? `${action} was applied, but the latest state could not be loaded.`,
          revision,
          outcome,
          options.pending('reconciling'),
        );
      }
      return result;
    } finally {
      // Keep the operation locked while the trailing reconciliation is active.
      // The confirmation dialog and page controls must not look idle between
      // the mutation response and the refreshed collection.
      if (!this.reconciling) {
        this.busy = false;
        this.phase = 'idle';
        this.action = '';
      }
    }
  }
}
