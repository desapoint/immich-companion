import { afterEach, describe, expect, it, vi } from 'vitest';
import { readV2ToastPosition, V2_TOAST_POSITION_STORAGE_KEY, V2ToastController, writeV2ToastPosition } from './toasts.svelte';

afterEach(() => vi.useRealTimers());

describe('V2 toast state', () => {
  it('keeps simultaneous messages in chronological order', () => {
    const controller = new V2ToastController('top-right');
    controller.push({ tone: 'success', title: 'First', message: 'Done', durationMs: 0 });
    controller.push({ tone: 'warning', title: 'Second', message: 'Review', durationMs: 0 });
    expect(controller.toasts.map((toast) => toast.title)).toEqual(['First', 'Second']);
    controller.destroy();
  });

  it('dismisses only the requested toast and expires timed messages', () => {
    vi.useFakeTimers();
    const controller = new V2ToastController();
    const first = controller.push({ tone: 'info', title: 'First', message: 'One', durationMs: 100 });
    controller.push({ tone: 'error', title: 'Second', message: 'Two', durationMs: 0 });
    controller.dismiss(first);
    expect(controller.toasts.map((toast) => toast.title)).toEqual(['Second']);
    controller.push({ tone: 'success', title: 'Timed', message: 'Three', durationMs: 100 });
    vi.advanceTimersByTime(100);
    expect(controller.toasts.map((toast) => toast.title)).toEqual(['Second']);
    controller.destroy();
  });

  it('persists and validates corner preferences', () => {
    const values = new Map<string, string>();
    const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) };
    writeV2ToastPosition('bottom-left', storage);
    expect(values.get(V2_TOAST_POSITION_STORAGE_KEY)).toBe('bottom-left');
    expect(readV2ToastPosition(storage)).toBe('bottom-left');
    values.set(V2_TOAST_POSITION_STORAGE_KEY, 'center');
    expect(readV2ToastPosition(storage)).toBe('top-right');
  });
});
