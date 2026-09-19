<script lang="ts">
  import SelectField from './SelectField.svelte';
  import DateTimeCalendar from './DateTimeCalendar.svelte';
  import type { CalendarDay } from '../../utils/dateTime';

  type Option = { value: string; label: string };

  let {
    id, monthLabel, days, today, selectedDate, focusedDate, hour, minute, hourOptions, minuteOptions,
    hasValue, element = $bindable<HTMLDivElement>(), onmonthchange, onselect, onfocusdate, onkeydown, onpanelkeydown,
    onhourchange, onminutechange, onnow, onclear, oncancel, onapply,
  }: {
    id: string; monthLabel: string; days: CalendarDay[]; today: string; selectedDate: string; focusedDate: string;
    hour: string; minute: string; hourOptions: Option[]; minuteOptions: Option[]; hasValue: boolean;
    element?: HTMLDivElement; onmonthchange: (offset: number) => void; onselect: (date: string) => void;
    onfocusdate: (date: string) => void; onkeydown: (event: KeyboardEvent) => void; onpanelkeydown: (event: KeyboardEvent) => void; onhourchange: (value: string) => void;
    onminutechange: (value: string) => void; onnow: () => void; onclear: () => void; oncancel: () => void; onapply: () => void;
  } = $props();
</script>

<div id={`${id}-picker`} class="picker-panel" role="dialog" tabindex="-1" aria-modal="false" aria-labelledby={`${id}-picker-title`} onkeydown={onpanelkeydown}>
  <DateTimeCalendar {id} {monthLabel} {days} {today} {selectedDate} {focusedDate} onmonthchange={onmonthchange} onselect={onselect} onfocusdate={onfocusdate} onkeydown={onkeydown} bind:element />
  <div class="time-row">
    <SelectField id={`${id}-hour`} label="Hour" value={hour} options={hourOptions} compact onchange={onhourchange} />
    <span class="time-separator" aria-hidden="true">:</span>
    <SelectField id={`${id}-minute`} label="Minute" value={minute} options={minuteOptions} compact onchange={onminutechange} />
    <button class="now-button" type="button" onclick={onnow}>Now</button>
  </div>
  <footer class="picker-actions">
    <button class="clear" type="button" onclick={onclear} disabled={!hasValue}>Clear</button>
    <span></span>
    <button type="button" onclick={oncancel}>Cancel</button>
    <button class="apply" type="button" onclick={onapply}>Apply</button>
  </footer>
</div>

<style>
  .picker-panel{position:absolute;z-index:60;top:calc(100% + .4rem);left:0;display:grid;width:min(22rem,calc(100vw - 2rem));gap:.55rem;padding:.72rem;border:1px solid var(--color-border-strong);border-radius:var(--radius-md);color:var(--color-ink-strong);background:var(--color-surface-raised);box-shadow:0 1rem 2.6rem rgb(17 24 19 / 22%)}
  .now-button,.picker-actions button{border:1px solid transparent;border-radius:var(--radius-sm);color:var(--color-ink-strong);background:transparent;cursor:pointer;font:inherit}.now-button:hover,.picker-actions button:hover:not(:disabled){border-color:var(--color-accent-strong);color:var(--color-accent-strong);background:var(--color-surface-soft)}.now-button:focus-visible,.picker-actions button:focus-visible{outline:.15rem solid var(--color-accent-strong);outline-offset:.08rem}
  .time-row{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr) auto;align-items:end;gap:.38rem;padding-top:.62rem;border-top:1px solid var(--color-border-subtle)}.time-separator{min-height:2.3rem;align-content:center;color:var(--color-ink-muted);font-weight:850}.now-button{min-height:2.3rem;padding-inline:.65rem;border-color:var(--color-border-strong);color:var(--color-accent-strong);background:var(--color-surface-soft);font-size:.7rem;font-weight:780}
  .picker-actions{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;align-items:center;gap:.4rem;padding-top:.62rem;border-top:1px solid var(--color-border-subtle)}.picker-actions button{min-height:2.15rem;padding-inline:.68rem;border-color:var(--color-border-strong);background:var(--color-surface-soft);font-size:.68rem;font-weight:780}.picker-actions button:disabled{cursor:default;opacity:.42}.picker-actions .clear{color:var(--color-negative-ink)}.picker-actions .apply{border-color:var(--color-accent-strong);color:var(--color-ink-inverse);background:var(--color-accent-strong)}
  @media(max-width:30rem){.picker-panel{position:fixed;top:50%;left:50%;width:min(22rem,calc(100vw - 1rem));max-height:calc(100dvh - 1rem);overflow-y:auto;transform:translate(-50%,-50%)}}
</style>
