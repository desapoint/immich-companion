export type FlickerHeldKey = ' ' | 'Enter';

function normalizeHeldKey(key: string): FlickerHeldKey | null {
  if (key === ' ' || key === 'Spacebar') return ' ';
  if (key === 'Enter') return 'Enter';
  return null;
}

export class FlickerHoldController {
  private pointerId: number | null = null;
  private readonly heldKeys = new Set<FlickerHeldKey>();
  private currentActive = false;

  constructor(private readonly onactivechange: (active: boolean) => void) {}

  get active(): boolean {
    return this.currentActive;
  }

  pointerDown(pointerId: number): boolean {
    if (this.pointerId !== null && this.pointerId !== pointerId) return false;
    this.pointerId = pointerId;
    this.sync();
    return true;
  }

  pointerUp(pointerId: number): boolean {
    if (this.pointerId !== pointerId) return false;
    this.pointerId = null;
    this.sync();
    return true;
  }

  keyDown(key: string): boolean {
    const heldKey = normalizeHeldKey(key);
    if (!heldKey) return false;
    this.heldKeys.add(heldKey);
    this.sync();
    return true;
  }

  keyUp(key: string): boolean {
    const heldKey = normalizeHeldKey(key);
    if (!heldKey) return false;
    this.heldKeys.delete(heldKey);
    this.sync();
    return true;
  }

  cancel(): void {
    this.pointerId = null;
    this.heldKeys.clear();
    this.sync();
  }

  private sync(): void {
    const active = this.pointerId !== null || this.heldKeys.size > 0;
    if (active === this.currentActive) return;
    this.currentActive = active;
    this.onactivechange(active);
  }
}
