import { describe, expect, it } from 'vitest';

import {
  buildCalendarDays,
  dateKey,
  formatLocalDateTime,
  parseDateKey,
  parseLocalDateTime,
  toLocalDateTimeValue,
} from './dateTime';

describe('custom date-time picker utilities', () => {
  it('parses and serializes valid local date-times', () => {
    expect(parseLocalDateTime('2026-08-24T09:05')).toEqual({
      date: '2026-08-24',
      hour: 9,
      minute: 5,
    });
    expect(toLocalDateTimeValue('2026-08-24', 9, 5)).toBe('2026-08-24T09:05');
    expect(formatLocalDateTime('2026-08-24T09:05', 'en-CA')).not.toBe('');
  });

  it('rejects impossible dates and times', () => {
    expect(parseDateKey('2026-02-29')).toBeNull();
    expect(parseLocalDateTime('2026-08-24T24:00')).toBeNull();
    expect(parseLocalDateTime('not-a-date')).toBeNull();
    expect(toLocalDateTimeValue('2026-13-01', 10, 30)).toBeNull();
  });

  it('builds a stable six-week calendar including adjacent-month days', () => {
    const days = buildCalendarDays(2026, 7);
    expect(days).toHaveLength(42);
    expect(days[0]).toEqual({ date: '2026-07-26', day: 26, inCurrentMonth: false });
    expect(days[6]).toEqual({ date: '2026-08-01', day: 1, inCurrentMonth: true });
    expect(days.at(-1)).toEqual({ date: '2026-09-05', day: 5, inCurrentMonth: false });
    expect(dateKey(2026, 7, 4)).toBe('2026-08-04');
  });
});
