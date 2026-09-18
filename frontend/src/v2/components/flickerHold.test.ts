import { describe, expect, it } from 'vitest';
import { FlickerHoldController } from './flickerHold';

describe('FlickerHoldController', () => {
  it('shows the reference only for the active captured pointer', () => {
    const changes: boolean[] = [];
    const hold = new FlickerHoldController((active) => changes.push(active));

    expect(hold.active).toBe(false);
    expect(hold.pointerDown(7)).toBe(true);
    expect(hold.active).toBe(true);
    expect(hold.pointerDown(9)).toBe(false);
    expect(hold.pointerUp(9)).toBe(false);
    expect(hold.active).toBe(true);
    expect(hold.pointerUp(7)).toBe(true);
    expect(hold.active).toBe(false);
    expect(changes).toEqual([true, false]);
  });

  it('supports Space and Enter hold semantics without latching', () => {
    const changes: boolean[] = [];
    const hold = new FlickerHoldController((active) => changes.push(active));

    expect(hold.keyDown(' ')).toBe(true);
    expect(hold.active).toBe(true);
    expect(hold.keyDown('Enter')).toBe(true);
    expect(hold.keyUp(' ')).toBe(true);
    expect(hold.active).toBe(true);
    expect(hold.keyUp('Enter')).toBe(true);
    expect(hold.active).toBe(false);
    expect(changes).toEqual([true, false]);
  });

  it('keeps the reference visible until every simultaneous hold is released', () => {
    const changes: boolean[] = [];
    const hold = new FlickerHoldController((active) => changes.push(active));

    hold.pointerDown(3);
    hold.keyDown(' ');
    hold.pointerUp(3);
    expect(hold.active).toBe(true);
    hold.keyUp(' ');
    expect(hold.active).toBe(false);
    expect(changes).toEqual([true, false]);
  });

  it('cancels every hold for blur, capture loss, mode exit, or teardown', () => {
    const changes: boolean[] = [];
    const hold = new FlickerHoldController((active) => changes.push(active));

    hold.pointerDown(4);
    hold.keyDown('Enter');
    hold.cancel();

    expect(hold.active).toBe(false);
    expect(changes).toEqual([true, false]);
    expect(hold.keyDown('Escape')).toBe(false);
    expect(hold.keyUp('Escape')).toBe(false);
    expect(hold.active).toBe(false);
  });
});
