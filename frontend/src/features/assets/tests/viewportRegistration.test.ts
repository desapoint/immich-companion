import { describe, expect, it, vi } from 'vitest';
import { ViewportRegistrationController, type ResizeObserverFactory } from '../state/viewportRegistration';

function observerDouble() {
  return {
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  } as unknown as ResizeObserver;
}

describe('ViewportRegistrationController', () => {
  it('registers a viewport once and remaps it from resize observation', () => {
    const viewport = {} as HTMLElement;
    const applyViewport = vi.fn();
    const remapViewport = vi.fn();
    const observer = observerDouble();
    const resizeCallbacks: ResizeObserverCallback[] = [];
    const createResizeObserver: ResizeObserverFactory = vi.fn((callback) => {
      resizeCallbacks.push(callback);
      return observer;
    });
    const controller = new ViewportRegistrationController(
      applyViewport,
      remapViewport,
      createResizeObserver,
    );

    controller.set(viewport);
    controller.set(viewport);

    expect(applyViewport).toHaveBeenCalledTimes(1);
    expect(applyViewport).toHaveBeenLastCalledWith(viewport);
    expect(createResizeObserver).toHaveBeenCalledTimes(1);
    expect(observer.observe).toHaveBeenCalledTimes(1);
    expect(observer.observe).toHaveBeenLastCalledWith(viewport);
    expect(resizeCallbacks).toHaveLength(1);

    resizeCallbacks[0]([], observer);
    expect(remapViewport).toHaveBeenCalledTimes(1);
  });

  it('disconnects stale observers when the comparison mode replaces its viewport', () => {
    const firstViewport = {} as HTMLElement;
    const secondViewport = {} as HTMLElement;
    const applyViewport = vi.fn();
    const firstObserver = observerDouble();
    const secondObserver = observerDouble();
    const observers = [firstObserver, secondObserver];
    const createResizeObserver: ResizeObserverFactory = vi.fn(
      () => observers.shift() ?? observerDouble(),
    );
    const controller = new ViewportRegistrationController(
      applyViewport,
      vi.fn(),
      createResizeObserver,
    );

    controller.set(firstViewport);
    controller.set(secondViewport);

    expect(firstObserver.disconnect).toHaveBeenCalledTimes(1);
    expect(secondObserver.observe).toHaveBeenCalledWith(secondViewport);
    expect(applyViewport.mock.calls).toEqual([[firstViewport], [secondViewport]]);
  });

  it('handles the real mode lifecycle of unmounting before mounting the next viewport', () => {
    const firstViewport = {} as HTMLElement;
    const secondViewport = {} as HTMLElement;
    const applyViewport = vi.fn();
    const firstObserver = observerDouble();
    const secondObserver = observerDouble();
    const observers = [firstObserver, secondObserver];
    const controller = new ViewportRegistrationController(
      applyViewport,
      vi.fn(),
      () => observers.shift() ?? observerDouble(),
    );

    controller.set(firstViewport);
    controller.set(null);
    controller.set(secondViewport);

    expect(firstObserver.disconnect).toHaveBeenCalledTimes(1);
    expect(secondObserver.observe).toHaveBeenCalledWith(secondViewport);
    expect(applyViewport.mock.calls).toEqual([[firstViewport], [null], [secondViewport]]);
  });

  it('clears the camera viewport and observer on teardown', () => {
    const viewport = {} as HTMLElement;
    const applyViewport = vi.fn();
    const observer = observerDouble();
    const controller = new ViewportRegistrationController(
      applyViewport,
      vi.fn(),
      () => observer,
    );

    controller.set(viewport);
    controller.destroy();
    controller.destroy();

    expect(observer.disconnect).toHaveBeenCalledTimes(1);
    expect(applyViewport.mock.calls).toEqual([[viewport], [null]]);
  });
});
