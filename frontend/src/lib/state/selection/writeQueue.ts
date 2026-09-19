export class SelectionWriteQueue {
  private chain: Promise<void> = Promise.resolve();
  private timer: ReturnType<typeof setTimeout> | null = null;

  enqueue(operation: () => Promise<void>): Promise<void> {
    const next = this.chain.then(operation);
    this.chain = next.catch(() => {});
    return next;
  }

  schedule(operation: () => Promise<void>, delay: number, onerror: (error: unknown) => void): void {
    this.cancelTimer();
    this.timer = setTimeout(() => { void operation().catch(onerror); }, delay);
  }

  cancelTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }
}
