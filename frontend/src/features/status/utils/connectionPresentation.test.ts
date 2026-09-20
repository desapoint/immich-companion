import { describe, expect, it } from 'vitest';

import { connectionLabel, connectionTone } from './connectionPresentation';

describe('task connection presentation', () => {
  it.each([
    ['connected', 'Live', 'ok'],
    ['connecting', 'Connecting', 'default'],
    ['reconnecting', 'Reconnecting', 'default'],
    ['disconnected', 'Disconnected', 'warn'],
  ] as const)('maps %s to a consistent label and tone', (state, label, tone) => {
    expect(connectionLabel(state)).toBe(label);
    expect(connectionTone(state)).toBe(tone);
  });
});
