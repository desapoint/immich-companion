<script lang="ts">
  import SelectField from './SelectField.svelte';
  import V2Button from './V2Button.svelte';

  type ScheduleMode = 'Interval' | 'Hourly' | 'Daily' | 'Weekly' | 'Monthly' | 'Custom';
  type ParsedSchedule = { mode: ScheduleMode; interval: string; minute: string; time: string; weekday: string; monthday: string };

  let {
    id,
    label = 'Schedule',
    value = $bindable('0 * * * *'),
    enabled = true,
    onchange,
    onvaliditychange,
  }: {
    id: string;
    label?: string;
    value?: string;
    enabled?: boolean;
    onchange?: (value: string) => void;
    onvaliditychange?: (valid: boolean) => void;
  } = $props();

  const weekdayOptions = [
    { value: '0', label: 'Sunday' }, { value: '1', label: 'Monday' }, { value: '2', label: 'Tuesday' },
    { value: '3', label: 'Wednesday' }, { value: '4', label: 'Thursday' }, { value: '5', label: 'Friday' }, { value: '6', label: 'Saturday' },
  ];
  const intervalOptions = ['5','10','15','20','30'];
  const minuteOptions = ['0','5','10','15','20','30','45'].map((minute) => ({ value: minute, label: minute === '0' ? 'On the hour' : `${minute} minutes past` }));
  const quickPresets = [
    { label: 'Every 15 min', cron: '*/15 * * * *' }, { label: 'Every hour', cron: '0 * * * *' },
    { label: 'Every day', cron: '0 0 * * *' }, { label: 'Daily · 2 AM', cron: '0 2 * * *' },
    { label: 'Weekdays · 2 AM', cron: '0 2 * * 1-5' }, { label: 'Weekly · Sunday', cron: '0 0 * * 0' },
    { label: 'Monthly · 1st', cron: '0 0 1 * *' },
  ];

  const initial = parseCron(value);
  let mode = $state<ScheduleMode>(initial.mode), interval = $state(initial.interval), minute = $state(initial.minute), time = $state(initial.time), weekday = $state(initial.weekday), monthday = $state(initial.monthday), lastValue = $state(value);

  function parseCron(cron: string): ParsedSchedule {
    const parts = cron.trim().split(/\s+/), fallback: ParsedSchedule = { mode: 'Custom', interval: '15', minute: '0', time: '00:00', weekday: '0', monthday: '1' };
    if (parts.length !== 5) return fallback;
    const [min, hour, day, month, week] = parts;
    if (month !== '*') return fallback;
    const intervalMatch = min.match(/^\*\/(\d+)$/);
    if (intervalMatch && hour === '*' && day === '*' && week === '*') return { ...fallback, mode: 'Interval', interval: intervalMatch[1] };
    if (/^\d+$/.test(min) && hour === '*' && day === '*' && week === '*') return { ...fallback, mode: 'Hourly', minute: min };
    if (/^\d+$/.test(min) && /^\d+$/.test(hour) && day === '*' && week === '*') return { ...fallback, mode: 'Daily', time: `${hour.padStart(2,'0')}:${min.padStart(2,'0')}` };
    if (/^\d+$/.test(min) && /^\d+$/.test(hour) && day === '*' && /^[0-6]$/.test(week)) return { ...fallback, mode: 'Weekly', weekday: week, time: `${hour.padStart(2,'0')}:${min.padStart(2,'0')}` };
    if (/^\d+$/.test(min) && /^\d+$/.test(hour) && /^\d+$/.test(day) && week === '*') return { ...fallback, mode: 'Monthly', monthday: day, time: `${hour.padStart(2,'0')}:${min.padStart(2,'0')}` };
    return fallback;
  }

  function fieldMatches(source: string, current: number, min: number, max: number, sunday = false): boolean {
    const normalize = (n: number) => sunday && n === 7 ? 0 : n;
    return source.split(',').some((part) => {
      const [base, stepText] = part.split('/');
      const step = stepText ? Number(stepText) : 1;
      if (!Number.isInteger(step) || step < 1) return false;
      if (base === '*') return (current - min) % step === 0;
      const range = base.split('-').map(Number);
      if (range.some(Number.isNaN)) return false;
      if (range.length === 1) return normalize(range[0]) === current;
      const start = normalize(range[0]), end = normalize(range[1]);
      return current >= start && current <= end && (current - start) % step === 0;
    });
  }

  function fieldValid(source: string, min: number, max: number, sunday = false): boolean {
    if (!source) return false;
    return source.split(',').every((part) => {
      const [base, stepText] = part.split('/');
      if (stepText && (!/^\d+$/.test(stepText) || Number(stepText) < 1)) return false;
      if (base === '*') return true;
      const nums = base.split('-');
      if (nums.length > 2 || nums.some((item) => !/^\d+$/.test(item))) return false;
      const values = nums.map(Number);
      const upper = sunday ? 7 : max;
      return values.every((n) => n >= min && n <= upper) && (values.length < 2 || values[0] <= values[1]);
    });
  }

  function validationError(cron: string): string {
    const parts = cron.trim().split(/\s+/);
    if (parts.length !== 5) return 'Cron must contain exactly 5 fields.';
    const rules: [number,number,boolean,string][] = [[0,59,false,'minute'],[0,23,false,'hour'],[1,31,false,'day of month'],[1,12,false,'month'],[0,6,true,'day of week']];
    for (let i = 0; i < rules.length; i += 1) if (!fieldValid(parts[i], rules[i][0], rules[i][1], rules[i][2])) return `Invalid ${rules[i][3]} field.`;
    return '';
  }

  function nextRun(cron: string): Date | null {
    if (validationError(cron)) return null;
    const [min,hour,dom,month,dow] = cron.trim().split(/\s+/);
    const cursor = new Date(); cursor.setSeconds(0,0); cursor.setMinutes(cursor.getMinutes()+1);
    for (let i=0;i<1051200;i+=1) {
      const domMatch = fieldMatches(dom,cursor.getDate(),1,31), dowMatch = fieldMatches(dow,cursor.getDay(),0,6,true);
      const dayMatch = dom === '*' && dow === '*' ? true : dom === '*' ? dowMatch : dow === '*' ? domMatch : domMatch || dowMatch;
      if (fieldMatches(min,cursor.getMinutes(),0,59) && fieldMatches(hour,cursor.getHours(),0,23) && dayMatch && fieldMatches(month,cursor.getMonth()+1,1,12)) return cursor;
      cursor.setMinutes(cursor.getMinutes()+1);
    }
    return null;
  }

  const error = $derived(validationError(value));
  const valid = $derived(error === '');
  const next = $derived(valid && enabled ? nextRun(value) : null);

  function hydrate(cron: string): void { const parsed=parseCron(cron); mode=parsed.mode; interval=parsed.interval; minute=parsed.minute; time=parsed.time; weekday=parsed.weekday; monthday=parsed.monthday; }
  function emit(cron: string): void { lastValue=cron; value=cron; onchange?.(cron); }
  function timeParts(): [string,string] { const [hour='0',min='0']=time.split(':'); return [String(Number(hour)),String(Number(min))]; }
  function rebuild(): void { const [hour,min]=timeParts(); if(mode==='Interval')emit(`*/${interval} * * * *`); else if(mode==='Hourly')emit(`${minute} * * * *`); else if(mode==='Daily')emit(`${min} ${hour} * * *`); else if(mode==='Weekly')emit(`${min} ${hour} * * ${weekday}`); else if(mode==='Monthly')emit(`${min} ${hour} ${monthday} * *`); }
  function setMode(next:string):void{mode=next as ScheduleMode;if(mode!=='Custom')rebuild()}
  function setRaw(cron:string):void{emit(cron);hydrate(cron)}
  function applyPreset(cron:string):void{emit(cron);hydrate(cron)}
  function description(cron:string):string{const parsed=parseCron(cron);if(parsed.mode==='Interval')return `Runs every ${parsed.interval} minutes.`;if(parsed.mode==='Hourly')return parsed.minute==='0'?'Runs at the start of every hour.':`Runs ${parsed.minute} minutes past every hour.`;if(parsed.mode==='Daily')return `Runs every day at ${parsed.time}.`;if(parsed.mode==='Weekly')return `Runs every ${weekdayOptions.find((day)=>day.value===parsed.weekday)?.label??'week'} at ${parsed.time}.`;if(parsed.mode==='Monthly')return `Runs on day ${parsed.monthday} of every month at ${parsed.time}.`;if(cron==='0 2 * * 1-5')return 'Runs every weekday at 02:00.';return valid?'Custom five-field cron expression.':'Invalid cron expression.'}
  function nextLabel(): string { if(!enabled)return 'Disabled'; if(!valid)return 'Unavailable until cron is valid'; if(!next)return 'No run found in the next 2 years'; return next.toLocaleString(); }

  $effect(()=>{onvaliditychange?.(valid)});
  $effect(()=>{if(value!==lastValue){lastValue=value;hydrate(value)}});
</script>

<div class="v2-cron-field" data-invalid={!valid || undefined}>
  <div class="v2-cron-heading"><div><span class="v2-field-label">{label}</span><strong>{description(value)}</strong></div><code>{value}</code></div>
  <div class="v2-cron-presets" aria-label={`${label} quick schedules`}>{#each quickPresets as preset}<V2Button active={value===preset.cron} onclick={()=>applyPreset(preset.cron)}>{preset.label}</V2Button>{/each}</div>
  <div class="v2-cron-builder"><SelectField id={`${id}-mode`} label="Repeat" value={mode} options={['Interval','Hourly','Daily','Weekly','Monthly','Custom']} onchange={setMode}/>{#if mode==='Interval'}<SelectField id={`${id}-interval`} label="Every" value={interval} options={intervalOptions.map((item)=>({value:item,label:`${item} minutes`}))} onchange={(next)=>{interval=next;rebuild()}}/>{:else if mode==='Hourly'}<SelectField id={`${id}-minute`} label="Minute" value={minute} options={minuteOptions} onchange={(next)=>{minute=next;rebuild()}}/>{:else if mode==='Daily'}<label class="v2-field"><span class="v2-field-label">Time</span><input type="time" value={time} onchange={(event)=>{time=event.currentTarget.value||'00:00';rebuild()}}></label>{:else if mode==='Weekly'}<SelectField id={`${id}-weekday`} label="Day" value={weekday} options={weekdayOptions} onchange={(next)=>{weekday=next;rebuild()}}/><label class="v2-field"><span class="v2-field-label">Time</span><input type="time" value={time} onchange={(event)=>{time=event.currentTarget.value||'00:00';rebuild()}}></label>{:else if mode==='Monthly'}<label class="v2-field"><span class="v2-field-label">Day of month</span><input type="number" min="1" max="31" value={monthday} onchange={(event)=>{monthday=String(Math.min(31,Math.max(1,Number(event.currentTarget.value)||1)));rebuild()}}></label><label class="v2-field"><span class="v2-field-label">Time</span><input type="time" value={time} onchange={(event)=>{time=event.currentTarget.value||'00:00';rebuild()}}></label>{/if}</div>
  <label class="v2-field v2-cron-raw"><span class="v2-field-label">Cron expression</span><input id={id} value={value} aria-invalid={!valid} aria-describedby={`${id}-status`} spellcheck="false" autocomplete="off" oninput={(event)=>setRaw(event.currentTarget.value)}><small>Minute · Hour · Day of month · Month · Day of week</small></label>
  <div id={`${id}-status`} class="v2-cron-status" data-invalid={!valid || undefined} role={valid?'status':'alert'}>{#if !valid}<strong>⚠ {error}</strong><span>Fix this value before saving.</span>{:else}<strong>Next run</strong><span>{nextLabel()}</span>{/if}</div>
</div>
