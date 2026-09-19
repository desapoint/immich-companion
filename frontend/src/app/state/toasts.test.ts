import { afterEach, describe, expect, it, vi } from 'vitest';
import { readToastPosition, TOAST_POSITION_STORAGE_KEY, ToastController, writeToastPosition } from './toasts.svelte';

afterEach(() => vi.useRealTimers());

describe('V2 toast state', () => {
  it('keeps simultaneous messages in chronological order', () => {
    const controller = new ToastController('top-right');
    controller.push({ tone: 'success', title: 'First', message: 'Done', durationMs: 0 });
    controller.push({ tone: 'warning', title: 'Second', message: 'Review', durationMs: 0 });
    expect(controller.toasts.map((toast) => toast.title)).toEqual(['First', 'Second']);
    controller.destroy();
  });

  it('dismisses only the requested toast and expires timed messages', () => {
    vi.useFakeTimers();
    const controller = new ToastController();
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
    writeToastPosition('bottom-left', storage);
    expect(values.get(TOAST_POSITION_STORAGE_KEY)).toBe('bottom-left');
    expect(readToastPosition(storage)).toBe('bottom-left');
    values.set(TOAST_POSITION_STORAGE_KEY, 'center');
    expect(readToastPosition(storage)).toBe('top-right');
  });
});
