import { getContext, setContext } from 'svelte';

export type ToastTone = 'info' | 'success' | 'warning' | 'error';
export type ToastPosition = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
export type ToastAction = { label: string; run: () => void | Promise<void> };
export type Toast = {
  id: number;
  tone: ToastTone;
  title: string;
  message: string;
  action?: ToastAction;
};
export type ToastInput = Omit<Toast, 'id'> & { durationMs?: number };

export const TOAST_POSITION_STORAGE_KEY = 'immich-companion:v2:toast-position';
export const TOAST_POSITIONS: Array<{ value: ToastPosition; label: string }> = [
  { value: 'top-right', label: 'Top right' },
  { value: 'top-left', label: 'Top left' },
  { value: 'bottom-right', label: 'Bottom right' },
  { value: 'bottom-left', label: 'Bottom left' },
];
const POSITION_VALUES = new Set<ToastPosition>(TOAST_POSITIONS.map((option) => option.value));
const TOAST_CONTEXT = Symbol('v2-toasts');

type ToastStorage = Pick<Storage, 'getItem' | 'setItem'>;

export function readToastPosition(storage?: ToastStorage): ToastPosition {
  const target = storage ?? (typeof localStorage === 'undefined' ? undefined : localStorage);
  const value = target?.getItem(TOAST_POSITION_STORAGE_KEY) as ToastPosition | null | undefined;
  return value && POSITION_VALUES.has(value) ? value : 'top-right';
}

export function writeToastPosition(position: ToastPosition, storage?: ToastStorage): void {
  const target = storage ?? (typeof localStorage === 'undefined' ? undefined : localStorage);
  try { target?.setItem(TOAST_POSITION_STORAGE_KEY, position); } catch { /* UI feedback remains usable without storage. */ }
}

export class ToastController {
  toasts = $state<Toast[]>([]);
  position = $state<ToastPosition>('top-right');
  private sequence = 0;
  private timers = new Map<number, ReturnType<typeof setTimeout>>();

  constructor(position = readToastPosition()) { this.position = position; }

  push(input: ToastInput): number {
    const id = ++this.sequence;
    const { durationMs = input.tone === 'error' ? 9000 : input.tone === 'warning' ? 7000 : 5000, ...toast } = input;
    this.toasts = [...this.toasts, { id, ...toast }];
    if (durationMs > 0) this.timers.set(id, setTimeout(() => this.dismiss(id), durationMs));
    return id;
  }

  dismiss(id: number): void {
    const timer = this.timers.get(id);
    if (timer) clearTimeout(timer);
    this.timers.delete(id);
    this.toasts = this.toasts.filter((toast) => toast.id !== id);
  }

  setPosition(position: ToastPosition): void {
    if (!POSITION_VALUES.has(position)) return;
    this.position = position;
    writeToastPosition(position);
  }

  destroy(): void {
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    this.toasts = [];
  }
}

export function provideToasts(controller: ToastController): ToastController {
  setContext(TOAST_CONTEXT, controller);
  return controller;
}

export function useOptionalToasts(): ToastController | null {
  return getContext<ToastController | undefined>(TOAST_CONTEXT) ?? null;
}
