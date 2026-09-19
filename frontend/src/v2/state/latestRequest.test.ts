import { describe, expect, it } from 'vitest';

import { LatestRequestController } from './latestRequest';

describe('LatestRequestController', () => {
  it('aborts and invalidates the previous request', () => {
    const requests = new LatestRequestController();
    const first = requests.begin();
    const second = requests.begin();

    expect(first.signal.aborted).toBe(true);
    expect(requests.isCurrent(first)).toBe(false);
    expect(requests.isCurrent(second)).toBe(true);
  });

  it('only lets the current request finish shared loading state', () => {
    const requests = new LatestRequestController();
    const first = requests.begin();
    const second = requests.begin();

    expect(requests.finish(first)).toBe(false);
    expect(requests.finish(second)).toBe(true);
  });

  it('aborts and invalidates the current request when cancelled', () => {
    const requests = new LatestRequestController();
    const current = requests.begin();

    requests.cancel();

    expect(current.signal.aborted).toBe(true);
    expect(requests.isCurrent(current)).toBe(false);
    expect(requests.finish(current)).toBe(false);
  });
});
