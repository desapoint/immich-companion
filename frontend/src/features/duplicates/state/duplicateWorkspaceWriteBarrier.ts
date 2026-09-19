import type { DuplicateRepository } from '../types/contracts';

type SelectionSnapshot = {
  groupIds: string[];
  activeGroupId: string | null;
};

/**
 * Keep persisted duplicate-selection writes ordered without making the UI wait for them.
 *
 * Selection changes are snapshots, so only their ordering matters. A reset advances the
 * epoch: writes that have not started yet become stale and are skipped, while a write that
 * is already in flight is allowed to finish before the reset reaches the repository. Draft
 * writes keep using the repository's existing per-group queues; clearDecisions already waits
 * for those queues before calling the reset endpoint.
 */
export function withDuplicateWorkspaceWriteBarrier(repository: DuplicateRepository): DuplicateRepository {
  let selectionEpoch = 0;
  let selectionTail: Promise<void> = Promise.resolve();
  let selectionError: unknown = null;

  const enqueueSelection = (snapshot: SelectionSnapshot): Promise<void> => {
    const epoch = selectionEpoch;
    const queued = selectionTail.then(async () => {
      if (epoch !== selectionEpoch) return;
      await repository.saveSelection(snapshot.groupIds, snapshot.activeGroupId);
    });

    selectionTail = queued.then(
      () => {
        if (epoch === selectionEpoch) selectionError = null;
      },
      (error) => {
        if (epoch === selectionEpoch) selectionError = error;
      },
    );

    // Selection persistence is intentionally detached from the interaction. Callers can
    // render the new selection immediately; flushDrafts() remains the explicit durability
    // barrier before refreshes and destructive operations.
    return Promise.resolve();
  };

  const flushSelection = async (): Promise<void> => {
    await selectionTail;
    if (selectionError !== null) throw selectionError;
  };

  return new Proxy(repository, {
    get(target, property, receiver) {
      if (property === 'saveSelection') {
        return (groupIds: readonly string[], activeGroupId: string | null) => enqueueSelection({
          groupIds: [...groupIds],
          activeGroupId,
        });
      }

      if (property === 'flushDrafts') {
        return async () => {
          await Promise.all([target.flushDrafts(), flushSelection()]);
        };
      }

      if (property === 'clearDecisions') {
        return async () => {
          // Prevent queued snapshots from being written after the reset. A selection request
          // that already started is represented by selectionTail and must finish first.
          selectionEpoch += 1;
          await selectionTail;
          selectionError = null;
          return target.clearDecisions();
        };
      }

      if (property === 'previewKeeperRules') {
        return async (...args: Parameters<DuplicateRepository['previewKeeperRules']>) => {
          await flushSelection();
          return target.previewKeeperRules(...args);
        };
      }

      if (property === 'applyKeeperRules') {
        return async (...args: Parameters<DuplicateRepository['applyKeeperRules']>) => {
          await flushSelection();
          return target.applyKeeperRules(...args);
        };
      }

      if (property === 'applyPreset') {
        return async (...args: Parameters<DuplicateRepository['applyPreset']>) => {
          await flushSelection();
          return target.applyPreset(...args);
        };
      }

      return Reflect.get(target, property, receiver);
    },
  });
}
