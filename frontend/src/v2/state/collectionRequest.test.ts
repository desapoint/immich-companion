import { describe, expect, it } from 'vitest';

import { CollectionRequestController } from './collectionRequest.svelte';

describe('CollectionRequestController', () => {
  it('lets only the latest request apply results', async () => {
    const controller = new CollectionRequestController();
    let releaseFirst!: (value: string) => void;
    let releaseSecond!: (value: string) => void;
    const first = new Promise<string>((resolve) => releaseFirst = resolve);
    const second = new Promise<string>((resolve) => releaseSecond = resolve);
    const applied: string[] = [];

    const firstRun = controller.run(() => first, { fallbackError: 'first failed', apply: (value) => { applied.push(value); } });
    const secondRun = controller.run(() => second, { fallbackError: 'second failed', apply: (value) => { applied.push(value); } });

    releaseFirst('old');
    releaseSecond('new');
    await Promise.all([firstRun, secondRun]);

    expect(applied).toEqual(['new']);
    expect(controller.loading).toBe(false);
  });

  it('keeps the latest load error separate from prior results', async () => {
    const controller = new CollectionRequestController();
    await controller.run(async () => { throw new Error('boom'); }, { fallbackError: 'fallback', apply: () => undefined });
    expect(controller.error).toBe('boom');
  });
});
