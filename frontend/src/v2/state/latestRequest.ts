export type RequestLease = {
  generation: number;
  signal: AbortSignal;
};

export class LatestRequestController {
  private generation = 0;
  private controller: AbortController | null = null;

  begin(): RequestLease {
    this.controller?.abort();
    this.controller = new AbortController();
    return {
      generation: ++this.generation,
      signal: this.controller.signal,
    };
  }

  isCurrent(lease: RequestLease): boolean {
    return lease.generation === this.generation && !lease.signal.aborted;
  }

  finish(lease: RequestLease): boolean {
    if (!this.isCurrent(lease)) return false;
    this.controller = null;
    return true;
  }

  cancel(): void {
    this.generation += 1;
    this.controller?.abort();
    this.controller = null;
  }
}
