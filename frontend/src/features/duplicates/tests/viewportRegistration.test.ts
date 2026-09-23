import { describe, expect, it, vi } from 'vitest';
import { createViewportAttachment } from '../state/comparisonViewportAttachment';

describe('createViewportAttachment', () => {
  it('registers the exact viewport node and clears it on detach', () => {
    const node = {} as HTMLElement;
    const registered: HTMLElement[] = [];
    const register = vi.fn((value: HTMLElement | null) => {
      if (value) registered.push(value);
    });
    const attachment = createViewportAttachment(register);

    const cleanup = attachment(node);
    expect(registered).toEqual([node]);
    expect(register).toHaveBeenCalledWith(node);

    cleanup?.();
    expect(register).toHaveBeenLastCalledWith(null);
  });

  it('observes resize and disconnects the observer when detached', () => {
    const node = {} as HTMLElement;
    const disconnect = vi.fn();
    const observe = vi.fn();
    const ResizeObserverMock = vi.fn(function (this: ResizeObserver) {
      Object.assign(this, { disconnect, observe });
    });
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    const onresize = vi.fn();

    const cleanup = createViewportAttachment(vi.fn(), onresize)(node);
    expect(observe).toHaveBeenCalledWith(node);
    expect(onresize).toHaveBeenCalledTimes(1);

    cleanup?.();
    expect(disconnect).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });
});
