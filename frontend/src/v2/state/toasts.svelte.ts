import { getContext, setContext } from 'svelte';

export type V2ToastTone = 'info' | 'success' | 'warning' | 'error';
export type V2ToastPosition = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
export type V2ToastAction = { label: string; run: () => void | Promise<void> };
export type V2Toast = {
  id: number;
  tone: V2ToastTone;
  title: string;
  message: string;
  action?: V2ToastAction;
};
export type V2ToastInput = Omit<V2Toast, 'id'> & { durationMs?: number };

export const V2_TOAST_POSITION_STORAGE_KEY = 'immich-companion:v2:toast-position';
export const V2_TOAST_POSITIONS: Array<{ value: V2ToastPosition; label: string }> = [
  { value: 'top-right', label: 'Top right' },
  { value: 'top-left', label: 'Top left' },
  { value: 'bottom-right', label: 'Bottom right' },
  { value: 'bottom-left', label: 'Bottom left' },
];
const POSITION_VALUES = new Set<V2ToastPosition>(V2_TOAST_POSITIONS.map((option) => option.value));
const TOAST_CONTEXT = Symbol('v2-toasts');

type ToastStorage = Pick<Storage, 'getItem' | 'setItem'>;

export function readV2ToastPosition(storage?: ToastStorage): V2ToastPosition {
  const target = storage ?? (typeof localStorage === 'undefined' ? undefined : localStorage);
  const value = target?.getItem(V2_TOAST_POSITION_STORAGE_KEY) as V2ToastPosition | null | undefined;
  return value && POSITION_VALUES.has(value) ? value : 'top-right';
}

export function writeV2ToastPosition(position: V2ToastPosition, storage?: ToastStorage): void {
  const target = storage ?? (typeof localStorage === 'undefined' ? undefined : localStorage);
  try { target?.setItem(V2_TOAST_POSITION_STORAGE_KEY, position); } catch { /* UI feedback remains usable without storage. */ }
}

export class V2ToastController {
  toasts = $state<V2Toast[]>([]);
  position = $state<V2ToastPosition>('top-right');
  private sequence = 0;
  private timers = new Map<number, ReturnType<typeof setTimeout>>();

  constructor(position = readV2ToastPosition()) { this.position = position; }

  push(input: V2ToastInput): number {
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

  setPosition(position: V2ToastPosition): void {
    if (!POSITION_VALUES.has(position)) return;
    this.position = position;
    writeV2ToastPosition(position);
  }

  destroy(): void {
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    this.toasts = [];
  }
}

export function provideV2Toasts(controller: V2ToastController): V2ToastController {
  setContext(TOAST_CONTEXT, controller);
  return controller;
}

export function useOptionalV2Toasts(): V2ToastController | null {
  return getContext<V2ToastController | undefined>(TOAST_CONTEXT) ?? null;
}
