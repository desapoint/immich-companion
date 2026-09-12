<script lang="ts">
  import { CalendarDays, ChevronLeft, ChevronRight } from '@lucide/svelte';
  import { tick } from 'svelte';
  import { clickOutside } from '../../lib/actions/clickOutside';

  type DateParts = {
    year: number;
    month: number;
    day: number;
    hour: number;
    minute: number;
  };

  let {
    id,
    label = '',
    value = $bindable(''),
    placeholder = '',
    showTime = true,
    disabled = false,
    onchange,
  }: {
    id: string;
    label?: string;
    value?: string;
    placeholder?: string;
    showTime?: boolean;
    disabled?: boolean;
    onchange?: (value: string) => void;
  } = $props();

  let open = $state(false);
  let trigger = $state<HTMLButtonElement>();
  let popup = $state<HTMLDivElement>();
  let viewYear = $state(new Date().getFullYear());
  let viewMonth = $state(new Date().getMonth());
  let popupTop = $state(0);
  let popupLeft = $state(0);
  let popupPlacement = $state<'down' | 'up'>('down');
  let timeDraft = $state('00:00');
  let timeInvalid = $state(false);

  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const monthFormatter = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' });
  const dateFormatter = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  const resolvedPlaceholder = $derived(placeholder || (showTime ? 'Choose date and time' : 'Choose date'));

  function parseValue(input: string): DateParts | undefined {
    const match = input.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?$/);
    if (!match) return undefined;
    const [, year, month, day, hour = '0', minute = '0'] = match;
    const parts = {
      year: Number(year),
      month: Number(month),
      day: Number(day),
      hour: Number(hour),
      minute: Number(minute),
    };
    if (
      parts.month < 1 || parts.month > 12
      || parts.day < 1 || parts.day > 31
      || parts.hour < 0 || parts.hour > 23
      || parts.minute < 0 || parts.minute > 59
    ) return undefined;
    return parts;
  }

  function pad(input: number): string {
    return String(input).padStart(2, '0');
  }

  function serialize(parts: DateParts): string {
    const date = `${parts.year}-${pad(parts.month)}-${pad(parts.day)}`;
    return showTime ? `${date}T${pad(parts.hour)}:${pad(parts.minute)}` : date;
  }

  function formatValue(input: string): string {
    const parts = parseValue(input);
    if (!parts) return resolvedPlaceholder;
    const date = dateFormatter.format(new Date(parts.year, parts.month - 1, parts.day));
    return showTime ? `${date} · ${pad(parts.hour)}:${pad(parts.minute)}` : date;
  }

  const selected = $derived(parseValue(value));
  const displayValue = $derived(formatValue(value));

  const calendarDays = $derived.by(() => {
    const first = new Date(viewYear, viewMonth, 1);
    const start = new Date(viewYear, viewMonth, 1 - first.getDay());
    return Array.from({ length: 42 }, (_, index) => {
      const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
      return {
        year: date.getFullYear(),
        month: date.getMonth(),
        day: date.getDate(),
        currentMonth: date.getMonth() === viewMonth,
      };
    });
  });

  function isSelectedDay(year: number, month: number, day: number): boolean {
    return selected?.year === year && selected.month === month + 1 && selected.day === day;
  }

  function isToday(year: number, month: number, day: number): boolean {
    const today = new Date();
    return today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;
  }

  function setValue(next: string): void {
    value = next;
    onchange?.(next);
  }

  function chooseDay(year: number, month: number, day: number): void {
    const current = selected;
    const next = {
      year,
      month: month + 1,
      day,
      hour: current?.hour ?? 0,
      minute: current?.minute ?? 0,
    };
    setValue(serialize(next));
    timeDraft = `${pad(next.hour)}:${pad(next.minute)}`;
    timeInvalid = false;
    viewYear = year;
    viewMonth = month;
  }

  function commitTime(): void {
    if (!showTime || !selected) return;
    const match = timeDraft.trim().match(/^(\d{1,2}):(\d{2})$/);
    if (!match) { timeInvalid = true; return; }
    const hour = Number(match[1]);
    const minute = Number(match[2]);
    if (hour > 23 || minute > 59) { timeInvalid = true; return; }
    timeInvalid = false;
    timeDraft = `${pad(hour)}:${pad(minute)}`;
    setValue(serialize({ ...selected, hour, minute }));
  }

  function chooseToday(): void {
    const now = new Date();
    const current = selected;
    const next = {
      year: now.getFullYear(),
      month: now.getMonth() + 1,
      day: now.getDate(),
      hour: current?.hour ?? now.getHours(),
      minute: current?.minute ?? now.getMinutes(),
    };
    setValue(serialize(next));
    timeDraft = `${pad(next.hour)}:${pad(next.minute)}`;
    timeInvalid = false;
    viewYear = now.getFullYear();
    viewMonth = now.getMonth();
  }

  function clear(): void {
    setValue('');
    timeInvalid = false;
    open = false;
    void tick().then(() => trigger?.focus());
  }

  function shiftMonth(delta: number): void {
    const next = new Date(viewYear, viewMonth + delta, 1);
    viewYear = next.getFullYear();
    viewMonth = next.getMonth();
  }

  function positionPopup(): void {
    if (!open || !trigger) return;
    const margin = 10;
    const gap = 5;
    const width = Math.min(320, window.innerWidth - margin * 2);
    const rect = trigger.getBoundingClientRect();
    const measuredHeight = Math.min(popup?.scrollHeight ?? (showTime ? 390 : 340), window.innerHeight - margin * 2);
    const spaceBelow = window.innerHeight - rect.bottom - gap - margin;
    const spaceAbove = rect.top - gap - margin;
    popupPlacement = spaceBelow >= Math.min(measuredHeight, 260) || spaceBelow >= spaceAbove ? 'down' : 'up';
    popupLeft = Math.min(Math.max(rect.left, margin), window.innerWidth - width - margin);
    popupTop = popupPlacement === 'down' ? rect.bottom + gap : Math.max(margin, rect.top - gap - measuredHeight);
  }

  function show(): void {
    if (disabled) return;
    const parts = selected;
    const base = parts ? new Date(parts.year, parts.month - 1, parts.day) : new Date();
    viewYear = base.getFullYear();
    viewMonth = base.getMonth();
    timeDraft = parts ? `${pad(parts.hour)}:${pad(parts.minute)}` : '00:00';
    timeInvalid = false;
    open = true;
    void tick().then(() => {
      positionPopup();
      requestAnimationFrame(positionPopup);
    });
  }

  function close(): void {
    if (showTime && selected) commitTime();
    if (timeInvalid) return;
    open = false;
    void tick().then(() => trigger?.focus());
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && open) {
      event.preventDefault();
      event.stopPropagation();
      open = false;
      timeInvalid = false;
      void tick().then(() => trigger?.focus());
    }
  }

  $effect(() => {
    if (!open) return;
    const reposition = () => positionPopup();
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
  });
</script>

<div class="v2-date-time-field" role="group" aria-label={label || (showTime ? 'Date and time' : 'Date')} use:clickOutside={{ enabled: open, onoutside: () => (open = false) }}>
  {#if label}<label class="v2-field-label" for={id}>{label}</label>{/if}
  <div class="v2-date-time-control">
    <button
      bind:this={trigger}
      {id}
      class="v2-date-time-trigger"
      type="button"
      {disabled}
      data-placeholder={!selected || undefined}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={`${id}-picker`}
      onclick={() => (open ? open = false : show())}
      onkeydown={handleKeydown}
    >
      <span>{displayValue}</span>
      <CalendarDays size={16} aria-hidden="true" />
    </button>
    {#if selected}
      <button class="v2-date-time-clear" type="button" {disabled} aria-label={`Clear ${label || (showTime ? 'date and time' : 'date')}`} onclick={clear} onkeydown={handleKeydown}>×</button>
    {/if}
  </div>

  {#if open}
    <div
      bind:this={popup}
      id={`${id}-picker`}
      class="v2-date-time-popup"
      data-placement={popupPlacement}
      role="dialog"
      tabindex="-1"
      aria-label={label ? `${label} ${showTime ? 'date and time' : 'date'} picker` : showTime ? 'Date and time picker' : 'Date picker'}
      style={`top:${popupTop}px;left:${popupLeft}px;width:min(320px,calc(100vw - 20px))`}
      onkeydown={handleKeydown}
    >
      <div class="v2-date-time-month-head">
        <button type="button" aria-label="Previous month" onclick={() => shiftMonth(-1)}><ChevronLeft size={17}/></button>
        <strong>{monthFormatter.format(new Date(viewYear, viewMonth, 1))}</strong>
        <button type="button" aria-label="Next month" onclick={() => shiftMonth(1)}><ChevronRight size={17}/></button>
      </div>

      <div class="v2-date-time-weekdays" aria-hidden="true">
        {#each weekdays as weekday (weekday)}<span>{weekday}</span>{/each}
      </div>

      <div class="v2-date-time-calendar" aria-label={monthFormatter.format(new Date(viewYear, viewMonth, 1))}>
        {#each calendarDays as date (`${date.year}-${date.month}-${date.day}`)}
          <button
            type="button"
            data-outside-month={!date.currentMonth || undefined}
            data-selected={isSelectedDay(date.year, date.month, date.day) || undefined}
            data-today={isToday(date.year, date.month, date.day) || undefined}
            aria-label={new Date(date.year, date.month, date.day).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            onclick={() => chooseDay(date.year, date.month, date.day)}
          >{date.day}</button>
        {/each}
      </div>

      {#if showTime}
        <div class="v2-date-time-time-row">
          <label for={`${id}-time`}>Time <span>24-hour</span></label>
          <input
            id={`${id}-time`}
            class="v2-date-time-time-input"
            data-invalid={timeInvalid || undefined}
            inputmode="numeric"
            autocomplete="off"
            placeholder="HH:MM"
            maxlength="5"
            value={timeDraft}
            disabled={!selected}
            aria-invalid={timeInvalid}
            oninput={(event) => { timeDraft = event.currentTarget.value; timeInvalid = false; }}
            onblur={commitTime}
            onkeydown={(event) => { if (event.key === 'Enter') { event.preventDefault(); commitTime(); } }}
          />
        </div>
        {#if timeInvalid}<div class="v2-date-time-error">Enter a 24-hour time from 00:00 to 23:59.</div>{/if}
      {/if}

      <div class="v2-date-time-actions">
        <button type="button" onclick={chooseToday}>Today</button>
        <button type="button" disabled={!selected} onclick={clear}>Clear</button>
        <button type="button" class="v2-date-time-done" onclick={close}>Done</button>
      </div>
    </div>
  {/if}
</div>

<style>
  .v2-date-time-field{display:flex;flex-direction:column;gap:5px;min-width:0;position:relative;width:100%}
  .v2-date-time-control{display:flex;align-items:stretch;min-width:0}
  .v2-date-time-trigger{width:100%;min-width:0;display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;border:1px solid var(--v2-line);background:#0f151d;color:var(--v2-text);border-radius:8px;padding:8px 10px;cursor:pointer;text-align:left;font:inherit}
  .v2-date-time-trigger:not(:only-child){border-radius:8px 0 0 8px}
  .v2-date-time-trigger>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-date-time-trigger[data-placeholder="true"]{color:var(--v2-muted)}
  .v2-date-time-trigger:hover:not(:disabled),.v2-date-time-trigger[aria-expanded="true"]{border-color:#4d607a}
  .v2-date-time-trigger:focus-visible,.v2-date-time-clear:focus-visible{outline:2px solid #4169a8;outline-offset:1px;position:relative;z-index:1}
  .v2-date-time-trigger:disabled,.v2-date-time-clear:disabled{cursor:default;opacity:.5}
  .v2-date-time-clear{flex:0 0 auto;border:1px solid var(--v2-line);border-left:0;background:#0f151d;color:var(--v2-muted);border-radius:0 8px 8px 0;padding:0 10px;cursor:pointer;font:inherit;font-size:16px;line-height:1}
  .v2-date-time-clear:hover:not(:disabled){color:var(--v2-text);border-color:#4d607a}
  .v2-date-time-popup{position:fixed;z-index:190;padding:8px;border:1px solid var(--v2-line);border-radius:9px;background:var(--v2-surface-2);box-shadow:0 14px 32px rgba(0,0,0,.34)}
  .v2-date-time-month-head{display:grid;grid-template-columns:34px minmax(0,1fr) 34px;align-items:center;gap:6px;margin-bottom:6px}
  .v2-date-time-month-head strong{text-align:center;font-size:13px;font-weight:600}
  .v2-date-time-month-head button,.v2-date-time-actions button{border:1px solid transparent;border-radius:7px;background:transparent;color:var(--v2-text);font:inherit;cursor:pointer}
  .v2-date-time-month-head button{width:34px;height:34px;display:grid;place-items:center;padding:0}
  .v2-date-time-month-head button:hover,.v2-date-time-actions button:hover:not(:disabled){background:#172231}
  .v2-date-time-weekdays,.v2-date-time-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:2px}
  .v2-date-time-weekdays{margin-bottom:3px}
  .v2-date-time-weekdays span{text-align:center;font-size:10px;color:var(--v2-muted);padding:3px 0}
  .v2-date-time-calendar button{aspect-ratio:1;border:0;border-radius:7px;background:transparent;color:var(--v2-text);font:inherit;font-size:12px;cursor:pointer;padding:0}
  .v2-date-time-calendar button[data-outside-month="true"]{color:#6f7d8e}
  .v2-date-time-calendar button:hover{background:#172231;color:var(--v2-text)}
  .v2-date-time-calendar button[data-today="true"]{box-shadow:inset 0 0 0 1px #4e6e9b}
  .v2-date-time-calendar button[data-selected="true"]{background:var(--v2-accent-2);color:#eaf1ff;box-shadow:none}
  .v2-date-time-calendar button[data-selected="true"]:hover{background:color-mix(in srgb,var(--v2-accent-2) 86%,white)}
  .v2-date-time-calendar button:focus-visible,.v2-date-time-month-head button:focus-visible,.v2-date-time-actions button:focus-visible{outline:2px solid #4169a8;outline-offset:-2px}
  .v2-date-time-time-row{display:grid;grid-template-columns:minmax(0,1fr) 84px;align-items:center;gap:10px;border-top:1px solid var(--v2-line);margin-top:8px;padding-top:8px}
  .v2-date-time-time-row label{font-size:12px;color:var(--v2-text);display:flex;align-items:baseline;gap:6px}
  .v2-date-time-time-row label span{font-size:10px;color:var(--v2-muted)}
  .v2-date-time-time-input{width:84px;min-width:0;text-align:center;font-variant-numeric:tabular-nums;letter-spacing:.04em;padding:7px 8px}
  .v2-date-time-time-input[data-invalid="true"]{border-color:#7a3f46;color:#ffb1b1}
  .v2-date-time-error{margin-top:5px;color:#ffb1b1;font-size:11px;text-align:right}
  .v2-date-time-actions{display:flex;justify-content:flex-end;gap:4px;border-top:1px solid var(--v2-line);margin-top:8px;padding-top:8px}
  .v2-date-time-actions button{padding:6px 9px;font-size:12px}
  .v2-date-time-actions button:disabled{opacity:.45;cursor:default}
  .v2-date-time-actions .v2-date-time-done{background:var(--v2-accent-2);color:#eaf1ff}
</style>
