import { describe, expect, it } from 'vitest';

import { RevisionedMutationQueue } from './revisionedMutationQueue';

interface View {
  revision: number;
  selected_count: number;
}

describe('RevisionedMutationQueue', () => {
  it('keeps causal follow-up mutations ahead of older concurrent work', async () => {
    const queue = new RevisionedMutationQueue<View>();
    const calls: string[] = [];
    let serverRevision = 1;

    const mutate = (label: string) => async (revision: number): Promise<View> => {
      calls.push(`${label}:${revision}`);
      expect(revision).toBe(serverRevision);
      serverRevision += 1;
      return { revision: serverRevision, selected_count: 0 };
    };

    const persist = async (label: string): Promise<void> => {
      let revision = 1;
      const selected = await queue.enqueue('selection-1', revision, mutate(`${label}-selected`));
      revision = selected.revision;
      await queue.enqueue('selection-1', revision, mutate(`${label}-unselected`));
    };

    await Promise.all([persist('first'), persist('second')]);

    expect(calls).toEqual([
      'first-selected:1',
      'first-unselected:2',
      'second-selected:3',
      'second-unselected:4',
    ]);
    expect(serverRevision).toBe(5);
  });

  it('waits for all queued mutations before releasing dependent reads', async () => {
    const queue = new RevisionedMutationQueue<View>();
    let resolveMutation!: (value: View) => void;
    const mutation = queue.enqueue('selection-1', 3, () => new Promise<View>((resolve) => {
      resolveMutation = resolve;
    }));
    let idle = false;
    const barrier = queue.waitForIdle('selection-1').then(() => { idle = true; });

    await Promise.resolve();
    expect(idle).toBe(false);

    resolveMutation({ revision: 4, selected_count: 1 });
    await mutation;
    await barrier;
    expect(idle).toBe(true);
  });

  it('keeps independent resources independent', async () => {
    const queue = new RevisionedMutationQueue<View>();

    const [first, second] = await Promise.all([
      queue.enqueue('selection-a', 2, async (revision) => ({
        revision: revision + 1,
        selected_count: 1,
      })),
      queue.enqueue('selection-b', 7, async (revision) => ({
        revision: revision + 1,
        selected_count: 2,
      })),
    ]);

    expect(first.revision).toBe(3);
    expect(second.revision).toBe(8);
  });

  it('rejects queued work and dependent reads after a mutation conflict', async () => {
    const queue = new RevisionedMutationQueue<View>();
    let rejectFirst!: (reason: unknown) => void;
    const first = queue.enqueue('selection-1', 1, () => new Promise<View>((_resolve, reject) => {
      rejectFirst = reject;
    }));
    const second = queue.enqueue('selection-1', 1, async (revision) => ({
      revision: revision + 1,
      selected_count: 2,
    }));
    const barrier = queue.waitForIdle('selection-1');
    const firstExpectation = expect(first).rejects.toThrow('Selection set changed');
    const secondExpectation = expect(second).rejects.toThrow('Selection set changed');
    const barrierExpectation = expect(barrier).rejects.toThrow('Selection set changed');

    rejectFirst(new Error('Selection set changed; reload its membership'));

    await firstExpectation;
    await secondExpectation;
    await barrierExpectation;
  });
});
