import { libraryData } from '../data/currentDataSource.svelte';
import type { SyncCoordinatorStatus, TaskConnectionState, TaskSubscription } from '../data/syncContracts';

const POLL_INTERVAL_MS = 10_000;

export class SyncStatusController {
  status = $state<SyncCoordinatorStatus | null>(null);
  connectionState = $state<TaskConnectionState>('disconnected');
  loading = $state(false);
  error = $state('');
  lastUpdatedAt = $state<number | null>(null);

  private subscribers = 0;
  private taskSubscription: TaskSubscription | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private refreshGeneration = 0;

  get stale(): boolean {
    return this.connectionState === 'reconnecting' || this.connectionState === 'disconnected' || Boolean(this.error);
  }

  acquire(): () => void {
    this.subscribers += 1;
    if (this.subscribers === 1) this.start();
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.subscribers = Math.max(0, this.subscribers - 1);
      if (this.subscribers === 0) this.stop();
    };
  }

  async refresh(): Promise<void> {
    const generation = ++this.refreshGeneration;
    this.loading = this.status === null;
    try {
      const next = await libraryData.sync.status();
      if (generation !== this.refreshGeneration) return;
      this.status = next;
      this.error = '';
      this.lastUpdatedAt = Date.now();
    } catch (error) {
      if (generation !== this.refreshGeneration) return;
      this.error = error instanceof Error && error.message.trim()
        ? error.message
        : 'Synchronization status could not be loaded.';
    } finally {
      if (generation === this.refreshGeneration) this.loading = false;
    }
  }

  private start(): void {
    void this.refresh();
    this.taskSubscription = libraryData.tasks.subscribe({
      onTask: (task) => {
        if (task.taskType === 'asset_sync') void this.refresh();
      },
      onConnectionState: (state) => {
        this.connectionState = state;
      },
      onRecovered: () => {
        void this.refresh();
      },
      onError: () => undefined,
    });
    this.pollTimer = setInterval(() => void this.refresh(), POLL_INTERVAL_MS);
  }

  private stop(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = null;
    this.taskSubscription?.close();
    this.taskSubscription = null;
    this.connectionState = 'disconnected';
    this.refreshGeneration += 1;
    this.loading = false;
  }
}

export const syncStatus = new SyncStatusController();
