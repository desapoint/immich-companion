<script lang="ts">
  import { tick } from 'svelte';

  import { clickOutside } from '../../actions/clickOutside';
  import {
    buildCalendarDays,
    dateKey,
    formatLocalDateTime,
    parseDateKey,
    parseLocalDateTime,
    toLocalDateTimeValue,
  } from '../../utils/dateTime';
  import SelectField from './SelectField.svelte';

  interface Props {
    id: string;
    label: string;
    value: string;
    disabled?: boolean;
    required?: boolean;
    onchange: (value: string) => void;
  }

  let { id, label, value, disabled = false, required = false, onchange }: Props = $props();

  const now = new Date();
  const today = dateKey(now.getFullYear(), now.getMonth(), now.getDate());
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const hourOptions = Array.from({ length: 24 }, (_, hour) => ({
    value: String(hour).padStart(2, '0'),
    label: String(hour).padStart(2, '0'),
  }));
  const minuteOptions = Array.from({ length: 60 }, (_, minute) => ({
    value: String(minute).padStart(2, '0'),
    label: String(minute).padStart(2, '0'),
  }));

  let triggerElement = $state<HTMLButtonElement>();
  let calendarElement = $state<HTMLDivElement>();
  let open = $state(false);
  let viewYear = $state(now.getFullYear());
  let viewMonth = $state(now.getMonth());
  let draftDate = $state(today);
  let focusedDate = $state(today);
  let draftHour = $state('00');
  let draftMinute = $state('00');

  const displayValue = $derived(formatLocalDateTime(value));
  const calendarDays = $derived(buildCalendarDays(viewYear, viewMonth));
  const monthLabel = $derived(new Intl.DateTimeFormat(undefined, {
    month: 'long',
    year: 'numeric',
  }).format(new Date(viewYear, viewMonth, 1)));

  async function focusCalendarDay(): Promise<void> {
    await tick();
    calendarElement?.querySelector<HTMLButtonElement>(`[data-date="${focusedDate}"]`)?.focus();
  }

  async function openPicker(): Promise<void> {
    if (disabled) return;
    const parsed = parseLocalDateTime(value);
    const initialDate = parsed?.date ?? today;
    const date = parseDateKey(initialDate) ?? now;
    draftDate = initialDate;
    focusedDate = initialDate;
    draftHour = String(parsed?.hour ?? 0).padStart(2, '0');
    draftMinute = String(parsed?.minute ?? 0).padStart(2, '0');
    viewYear = date.getFullYear();
    viewMonth = date.getMonth();
    open = true;
    await focusCalendarDay();
  }

  async function closePicker(restoreFocus = false): Promise<void> {
    open = false;
    if (restoreFocus) {
      await tick();
      triggerElement?.focus();
    }
  }

  function selectDate(nextDate: string): void {
    const parsed = parseDateKey(nextDate);
    if (!parsed) return;
    draftDate = nextDate;
    focusedDate = nextDate;
    viewYear = parsed.getFullYear();
    viewMonth = parsed.getMonth();
  }

  function dateShiftedByMonths(date: Date, offset: number): Date {
    const targetFirst = new Date(date.getFullYear(), date.getMonth() + offset, 1);
    const targetLast = new Date(targetFirst.getFullYear(), targetFirst.getMonth() + 1, 0).getDate();
    return new Date(
      targetFirst.getFullYear(),
      targetFirst.getMonth(),
      Math.min(date.getDate(), targetLast),
    );
  }

  function changeMonth(offset: number): void {
    const currentFocus = parseDateKey(focusedDate) ?? new Date(viewYear, viewMonth, 1);
    const target = dateShiftedByMonths(currentFocus, offset);
    focusedDate = dateKey(target.getFullYear(), target.getMonth(), target.getDate());
    viewYear = target.getFullYear();
    viewMonth = target.getMonth();
  }

  function moveFocusByDays(offset: number): void {
    const date = parseDateKey(focusedDate);
    if (!date) return;
    date.setDate(date.getDate() + offset);
    focusedDate = dateKey(date.getFullYear(), date.getMonth(), date.getDate());
    viewYear = date.getFullYear();
    viewMonth = date.getMonth();
    void focusCalendarDay();
  }

  function moveFocusByMonths(offset: number): void {
    const date = parseDateKey(focusedDate);
    if (!date) return;
    const target = dateShiftedByMonths(date, offset);
    focusedDate = dateKey(target.getFullYear(), target.getMonth(), target.getDate());
    viewYear = target.getFullYear();
    viewMonth = target.getMonth();
    void focusCalendarDay();
  }

  function handleDayKeydown(event: KeyboardEvent): void {
    const date = parseDateKey(focusedDate);
    if (!date) return;
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      moveFocusByDays(-1);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      moveFocusByDays(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveFocusByDays(-7);
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveFocusByDays(7);
    } else if (event.key === 'Home') {
      event.preventDefault();
      moveFocusByDays(-date.getDay());
    } else if (event.key === 'End') {
      event.preventDefault();
      moveFocusByDays(6 - date.getDay());
    } else if (event.key === 'PageUp') {
      event.preventDefault();
      moveFocusByMonths(event.shiftKey ? -12 : -1);
    } else if (event.key === 'PageDown') {
      event.preventDefault();
      moveFocusByMonths(event.shiftKey ? 12 : 1);
    }
  }

  function handlePanelKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      void closePicker(true);
    }
  }

  function chooseNow(): void {
    const current = new Date();
    selectDate(dateKey(current.getFullYear(), current.getMonth(), current.getDate()));
    draftHour = String(current.getHours()).padStart(2, '0');
    draftMinute = String(current.getMinutes()).padStart(2, '0');
    void focusCalendarDay();
  }

  function applySelection(): void {
    const nextValue = toLocalDateTimeValue(draftDate, Number(draftHour), Number(draftMinute));
    if (!nextValue) return;
    onchange(nextValue);
    void closePicker(true);
  }

  function clearSelection(): void {
    onchange('');
    void closePicker(true);
  }

  $effect(() => {
    if (disabled) open = false;
  });

</script>

<div
  use:clickOutside={{ enabled: open, onoutside: () => void closePicker() }}
  class:open
  class="date-time-picker"
>
  <span id={`${id}-label`} class="field-label">
    {label}
    {#if required}<small>Required</small>{/if}
  </span>
  <button
    bind:this={triggerElement}
    {id}
    class:placeholder={!displayValue}
    class="picker-trigger"
    type="button"
    {disabled}
    aria-haspopup="dialog"
    aria-expanded={open}
    aria-controls={`${id}-picker`}
    aria-labelledby={`${id}-label ${id}-value`}
    onclick={() => (open ? void closePicker() : void openPicker())}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 2v3M17 2v3M3.5 9h17M5.5 4h13a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
    </svg>
    <span id={`${id}-value`} class="picker-value">{displayValue || 'Choose date and time'}</span>
    <span class="chevron" aria-hidden="true"></span>
  </button>

  {#if open}
    <div
      id={`${id}-picker`}
      class="picker-panel"
      role="dialog"
      tabindex="-1"
      aria-modal="false"
      aria-labelledby={`${id}-picker-title`}
      onkeydown={handlePanelKeydown}
    >
      <header class="calendar-header">
        <button type="button" onclick={() => changeMonth(-1)} aria-label="Previous month" title="Previous month">‹</button>
        <strong id={`${id}-picker-title`}>{monthLabel}</strong>
        <button type="button" onclick={() => changeMonth(1)} aria-label="Next month" title="Next month">›</button>
      </header>

      <div class="weekday-grid" aria-hidden="true">
        {#each weekdays as weekday}
          <span>{weekday}</span>
        {/each}
      </div>

      <div bind:this={calendarElement} class="day-grid" aria-label={monthLabel}>
        {#each calendarDays as day (day.date)}
          <button
            class:outside={!day.inCurrentMonth}
            class:selected={day.date === draftDate}
            class:today={day.date === today}
            type="button"
            data-date={day.date}
            tabindex={day.date === focusedDate ? 0 : -1}
            aria-label={new Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(parseDateKey(day.date) ?? now)}
            aria-pressed={day.date === draftDate}
            aria-current={day.date === today ? 'date' : undefined}
            onclick={() => selectDate(day.date)}
            onfocus={() => (focusedDate = day.date)}
            onkeydown={handleDayKeydown}
          >{day.day}</button>
        {/each}
      </div>

      <div class="time-row">
        <SelectField
          id={`${id}-hour`}
          label="Hour"
          value={draftHour}
          options={hourOptions}
          compact
          onchange={(nextHour) => (draftHour = nextHour)}
        />
        <span class="time-separator" aria-hidden="true">:</span>
        <SelectField
          id={`${id}-minute`}
          label="Minute"
          value={draftMinute}
          options={minuteOptions}
          compact
          onchange={(nextMinute) => (draftMinute = nextMinute)}
        />
        <button class="now-button" type="button" onclick={chooseNow}>Now</button>
      </div>

      <footer class="picker-actions">
        <button class="clear" type="button" onclick={clearSelection} disabled={!value}>Clear</button>
        <span></span>
        <button type="button" onclick={() => void closePicker(true)}>Cancel</button>
        <button class="apply" type="button" onclick={applySelection}>Apply</button>
      </footer>
    </div>
  {/if}
</div>

<style>
  .date-time-picker {
    position: relative;
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  .field-label {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  .field-label small {
    margin-left: 0.3rem;
    color: var(--color-accent-strong);
    font-size: 0.56rem;
    letter-spacing: 0.02em;
  }

  .picker-trigger {
    display: grid;
    width: 100%;
    min-width: 0;
    min-height: 2.55rem;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.55rem;
    padding: 0.56rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    text-align: left;
  }

  .picker-trigger:hover:not(:disabled),
  .open .picker-trigger {
    border-color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 5%, var(--color-canvas));
  }

  .picker-trigger:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  .picker-trigger:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  .picker-trigger svg {
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-width: 1.75;
  }

  .picker-value {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .placeholder .picker-value {
    color: var(--color-ink-muted);
  }

  .chevron {
    width: 0.52rem;
    height: 0.52rem;
    border-right: 0.12rem solid currentColor;
    border-bottom: 0.12rem solid currentColor;
    transform: translateY(-0.13rem) rotate(45deg);
    transition: transform 130ms ease;
  }

  .open .chevron {
    transform: translateY(0.13rem) rotate(225deg);
  }

  .picker-panel {
    position: absolute;
    z-index: 60;
    top: calc(100% + 0.4rem);
    left: 0;
    display: grid;
    width: min(22rem, calc(100vw - 2rem));
    gap: 0.55rem;
    padding: 0.72rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: 0 1rem 2.6rem rgb(17 24 19 / 22%);
  }

  .calendar-header {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.5rem;
  }

  .calendar-header strong {
    font-size: 0.84rem;
    text-align: center;
  }

  .calendar-header button,
  .day-grid button,
  .now-button,
  .picker-actions button {
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: transparent;
    cursor: pointer;
    font: inherit;
  }

  .calendar-header button {
    width: 2.15rem;
    height: 2.15rem;
    border-color: var(--color-border-subtle);
    background: var(--color-surface-soft);
    font-size: 1.35rem;
    line-height: 1;
  }

  .calendar-header button:hover,
  .day-grid button:hover,
  .now-button:hover,
  .picker-actions button:hover:not(:disabled) {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  .weekday-grid,
  .day-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 0.16rem;
  }

  .weekday-grid span {
    padding-block: 0.2rem;
    color: var(--color-ink-muted);
    font-size: 0.58rem;
    font-weight: 800;
    text-align: center;
    text-transform: uppercase;
  }

  .day-grid button {
    aspect-ratio: 1;
    min-width: 0;
    padding: 0;
    font-size: 0.72rem;
  }

  .day-grid button.outside {
    color: var(--color-ink-muted);
    opacity: 0.5;
  }

  .day-grid button.today {
    border-color: var(--color-accent-strong);
  }

  .day-grid button.selected {
    border-color: var(--color-accent-strong);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
    font-weight: 820;
    opacity: 1;
  }

  .day-grid button:focus-visible,
  .calendar-header button:focus-visible,
  .now-button:focus-visible,
  .picker-actions button:focus-visible {
    outline: 0.15rem solid var(--color-accent-strong);
    outline-offset: 0.08rem;
  }

  .time-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto;
    align-items: end;
    gap: 0.38rem;
    padding-top: 0.62rem;
    border-top: 1px solid var(--color-border-subtle);
  }

  .time-separator {
    min-height: 2.3rem;
    align-content: center;
    color: var(--color-ink-muted);
    font-weight: 850;
  }

  .now-button {
    min-height: 2.3rem;
    padding-inline: 0.65rem;
    border-color: var(--color-border-strong);
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
    font-size: 0.7rem;
    font-weight: 780;
  }

  .picker-actions {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 0.4rem;
    padding-top: 0.62rem;
    border-top: 1px solid var(--color-border-subtle);
  }

  .picker-actions button {
    min-height: 2.15rem;
    padding-inline: 0.68rem;
    border-color: var(--color-border-strong);
    background: var(--color-surface-soft);
    font-size: 0.68rem;
    font-weight: 780;
  }

  .picker-actions button:disabled {
    cursor: default;
    opacity: 0.42;
  }

  .picker-actions .clear {
    color: var(--color-negative-ink);
  }

  .picker-actions .apply {
    border-color: var(--color-accent-strong);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
  }

  @media (max-width: 30rem) {
    .picker-panel {
      position: fixed;
      top: 50%;
      left: 50%;
      width: min(22rem, calc(100vw - 1rem));
      max-height: calc(100dvh - 1rem);
      overflow-y: auto;
      transform: translate(-50%, -50%);
    }
  }
</style>
