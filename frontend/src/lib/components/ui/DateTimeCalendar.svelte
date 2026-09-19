<script lang="ts">
  import type { CalendarDay } from '../../utils/dateTime';

  let {
    id,
    monthLabel,
    days,
    today,
    selectedDate,
    focusedDate,
    onmonthchange,
    onselect,
    onfocusdate,
    onkeydown,
    element = $bindable<HTMLDivElement>(),
  }: {
    id: string;
    monthLabel: string;
    days: readonly CalendarDay[];
    today: string;
    selectedDate: string;
    focusedDate: string;
    onmonthchange: (offset: number) => void;
    onselect: (date: string) => void;
    onfocusdate: (date: string) => void;
    onkeydown: (event: KeyboardEvent) => void;
    element?: HTMLDivElement;
  } = $props();
</script>

<header class="calendar-header">
  <button type="button" onclick={() => onmonthchange(-1)} aria-label="Previous month" title="Previous month">‹</button>
  <strong id={`${id}-picker-title`}>{monthLabel}</strong>
  <button type="button" onclick={() => onmonthchange(1)} aria-label="Next month" title="Next month">›</button>
</header>
<div class="weekday-grid" aria-hidden="true">
  {#each ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as weekday (weekday)}<span>{weekday}</span>{/each}
</div>
<div bind:this={element} class="day-grid" aria-label={monthLabel}>
  {#each days as day (day.date)}
    <button
      class:outside={!day.inCurrentMonth}
      class:selected={day.date === selectedDate}
      class:today={day.date === today}
      type="button"
      data-date={day.date}
      tabindex={day.date === focusedDate ? 0 : -1}
      aria-label={new Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(new Date(`${day.date}T00:00:00`))}
      aria-pressed={day.date === selectedDate}
      aria-current={day.date === today ? 'date' : undefined}
      onclick={() => onselect(day.date)}
      onfocus={() => onfocusdate(day.date)}
      onkeydown={onkeydown}
    >{day.day}</button>
  {/each}
</div>

<style>
  .calendar-header{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:.5rem}
  .calendar-header strong{font-size:.84rem;text-align:center}
  .calendar-header button,.day-grid button{border:1px solid transparent;border-radius:var(--radius-sm);color:var(--color-ink-strong);background:transparent;cursor:pointer;font:inherit}
  .calendar-header button{width:2.15rem;height:2.15rem;border-color:var(--color-border-subtle);background:var(--color-surface-soft);font-size:1.35rem;line-height:1}
  .calendar-header button:hover,.day-grid button:hover{border-color:var(--color-border-strong);background:var(--color-surface-soft)}
  .weekday-grid,.day-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.16rem}
  .weekday-grid span{padding-block:.2rem;color:var(--color-ink-muted);font-size:.58rem;font-weight:800;text-align:center;text-transform:uppercase}
  .day-grid button{aspect-ratio:1;min-width:0;padding:0;font-size:.72rem}
  .day-grid button.outside{color:var(--color-ink-muted);opacity:.5}
  .day-grid button.today{border-color:var(--color-accent-strong)}
  .day-grid button.selected{border-color:var(--color-accent-strong);color:var(--color-ink-inverse);background:var(--color-accent-strong);font-weight:820;opacity:1}
  .day-grid button:focus-visible,.calendar-header button:focus-visible{outline:.15rem solid var(--color-accent-strong);outline-offset:.08rem}
</style>
