import { errorMessage } from '../data/mutationFeedback';
import { LatestRequestController } from './latestRequest';

export type CollectionLoadMode = 'replace' | 'append';

export type CollectionLoadOptions<TResult> = {
  fallbackError: string;
  apply: (result: TResult, mode: CollectionLoadMode) => void | Promise<void>;
  mode?: CollectionLoadMode;
};

export class CollectionRequestController {
  loading = $state(false);
  error = $state('');
  private readonly requests = new LatestRequestController();

  async run<TResult>(
    loader: (signal: AbortSignal) => Promise<TResult>,
    options: CollectionLoadOptions<TResult>,
  ): Promise<TResult | null> {
    const request = this.requests.begin();
    this.loading = true;
    try {
      const result = await loader(request.signal);
      if (!this.requests.isCurrent(request)) return null;
      await options.apply(result, options.mode ?? 'replace');
      if (!this.requests.isCurrent(request)) return null;
      this.error = '';
      return result;
    } catch (error) {
      if (this.requests.isCurrent(request)) this.error = errorMessage(error, options.fallbackError);
      return null;
    } finally {
      if (this.requests.finish(request)) this.loading = false;
    }
  }

  cancel(): void {
    this.requests.cancel();
    this.loading = false;
  }

  clearError(): void {
    this.error = '';
  }
}
