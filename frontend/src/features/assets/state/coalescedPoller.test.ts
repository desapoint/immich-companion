import { afterEach, describe, expect, it, vi } from 'vitest';

import { CoalescedPoller } from './coalescedPoller';

afterEach(() => vi.useRealTimers());

describe('CoalescedPoller', () => {
  it('runs immediately, waits for completion, then schedules the next poll', async () => {
    vi.useFakeTimers();
    let resolveFirst!: () => void;
    const first = new Promise<void>((resolve) => { resolveFirst = resolve; });
    const task = vi.fn().mockReturnValueOnce(first).mockResolvedValue(undefined);
    const poller = new CoalescedPoller(task, () => 1000);

    poller.start();
    expect(task).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(5000);
    expect(task).toHaveBeenCalledTimes(1);

    resolveFirst();
    await first;
    await Promise.resolve();
    vi.advanceTimersByTime(999);
    expect(task).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1);
    expect(task).toHaveBeenCalledTimes(2);
  });

  it('coalesces concurrent refresh requests and shares one forced follow-up request', async () => {
    let resolveFirst!: () => void;
    let resolveFollowUp!: () => void;
    const first = new Promise<void>((resolve) => { resolveFirst = resolve; });
    const followUp = new Promise<void>((resolve) => { resolveFollowUp = resolve; });
    const task = vi.fn()
      .mockReturnValueOnce(first)
      .mockReturnValueOnce(followUp)
      .mockResolvedValue(undefined);
    const poller = new CoalescedPoller(task, () => 1000);

    poller.start();
    const coalesced = poller.refresh();
    const forcedA = poller.refresh(true);
    const forcedB = poller.refresh(true);
    expect(task).toHaveBeenCalledTimes(1);

    resolveFirst();
    await first;
    await Promise.resolve();
    expect(task).toHaveBeenCalledTimes(2);

    resolveFollowUp();
    await Promise.all([coalesced, forcedA, forcedB]);
    expect(task).toHaveBeenCalledTimes(2);
  });

  it('does not reschedule after stop and a later start ignores stale in-flight work', async () => {
    vi.useFakeTimers();
    let resolveOld!: () => void;
    const oldRequest = new Promise<void>((resolve) => { resolveOld = resolve; });
    const task = vi.fn().mockReturnValueOnce(oldRequest).mockResolvedValue(undefined);
    const poller = new CoalescedPoller(task, () => 1000);

    poller.start();
    poller.stop();
    poller.start();
    expect(task).toHaveBeenCalledTimes(2);

    resolveOld();
    await oldRequest;
    await Promise.resolve();
    poller.stop();
    vi.advanceTimersByTime(5000);
    expect(task).toHaveBeenCalledTimes(2);
  });

  it('uses the latest delay when explicitly rescheduled', () => {
    vi.useFakeTimers();
    let delay = 1000;
    const task = vi.fn().mockResolvedValue(undefined);
    const poller = new CoalescedPoller(task, () => delay);

    poller.start(false);
    delay = 5000;
    poller.reschedule();
    vi.advanceTimersByTime(4999);
    expect(task).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(task).toHaveBeenCalledTimes(1);
  });
});
