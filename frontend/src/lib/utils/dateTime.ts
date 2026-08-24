export interface LocalDateTimeParts {
  date: string;
  hour: number;
  minute: number;
}

export interface CalendarDay {
  date: string;
  day: number;
  inCurrentMonth: boolean;
}

const localDateTimePattern = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;
const datePattern = /^(\d{4})-(\d{2})-(\d{2})$/;

function pad(value: number): string {
  return String(value).padStart(2, '0');
}

export function dateKey(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, '0')}-${pad(month + 1)}-${pad(day)}`;
}

export function parseDateKey(value: string): Date | null {
  const match = datePattern.exec(value);
  if (!match) return null;
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText) - 1;
  const day = Number(dayText);
  const parsed = new Date(year, month, day);
  if (
    parsed.getFullYear() !== year
    || parsed.getMonth() !== month
    || parsed.getDate() !== day
  ) return null;
  return parsed;
}

export function parseLocalDateTime(value: string): LocalDateTimeParts | null {
  const match = localDateTimePattern.exec(value);
  if (!match) return null;
  const [, yearText, monthText, dayText, hourText, minuteText] = match;
  const date = `${yearText}-${monthText}-${dayText}`;
  const hour = Number(hourText);
  const minute = Number(minuteText);
  if (!parseDateKey(date) || hour > 23 || minute > 59) return null;
  return { date, hour, minute };
}

export function toLocalDateTimeValue(date: string, hour: number, minute: number): string | null {
  if (!parseDateKey(date) || !Number.isInteger(hour) || !Number.isInteger(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return `${date}T${pad(hour)}:${pad(minute)}`;
}

export function buildCalendarDays(year: number, month: number): CalendarDay[] {
  const firstDay = new Date(year, month, 1);
  const gridStart = new Date(year, month, 1 - firstDay.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const current = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
    return {
      date: dateKey(current.getFullYear(), current.getMonth(), current.getDate()),
      day: current.getDate(),
      inCurrentMonth: current.getMonth() === month,
    };
  });
}

export function formatLocalDateTime(value: string, locale?: string): string {
  const parts = parseLocalDateTime(value);
  if (!parts) return '';
  const date = parseDateKey(parts.date);
  if (!date) return '';
  date.setHours(parts.hour, parts.minute, 0, 0);
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
