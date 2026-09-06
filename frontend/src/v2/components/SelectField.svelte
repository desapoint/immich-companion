<script lang="ts">
  import { ArrowDown, ArrowUp, Plus } from '@lucide/svelte';
  import { tick } from 'svelte';
  import { clickOutside } from '../../lib/actions/clickOutside';

  type SortDirection = 'asc' | 'desc';
  type NormalizedSelectOption = { value:string; label:string; subtitle:string; disabled:boolean; direction?:SortDirection };

  export type SelectOption = string | { value:string; label:string; subtitle?:string; disabled?:boolean; direction?:SortDirection };

  let {
    id,label='',value=$bindable<string|number>(''),values=$bindable<string[]>([]),multiple=false,options,width='full',disabled=false,allowEmpty=false,
    placeholder='Choose an option',searchable=false,searchPlaceholder='Search options…',loading=false,hasMore=false,addLabel='',
    onchange,onvalueschange,onsearchchange,onloadmore,onadd,
  }: {
    id:string; label?:string; value?:string|number; values?:string[]; multiple?:boolean; options:SelectOption[]; width?:'full'|'content'; disabled?:boolean;
    allowEmpty?:boolean; placeholder?:string; searchable?:boolean; searchPlaceholder?:string; loading?:boolean; hasMore?:boolean; addLabel?:string;
    onchange?:(value:string)=>void; onvalueschange?:(values:string[])=>void; onsearchchange?:(query:string)=>void; onloadmore?:()=>void; onadd?:(query:string)=>void;
  }=$props();

  let open=$state(false),activeIndex=$state(-1),searchQuery=$state('');
  let trigger=$state<HTMLButtonElement>(),optionsPopup=$state<HTMLDivElement>(),list=$state<HTMLDivElement>(),searchInput=$state<HTMLInputElement>(),widthProbe=$state<HTMLDivElement>();
  let intrinsicPopupWidth=$state(0),popupTop=$state(0),popupLeft=$state(0),popupWidth=$state(0),popupMaxHeight=$state(304);
  let popupPlacement=$state<'down'|'up'>('down'),popupAlignment=$state<'left'|'right'|'viewport'>('left'),multiTriggerText=$state('');
  let nativeScrollbarWidth:number|undefined;

  function normalizeStringOption(option:string):NormalizedSelectOption[]{
    const directional=option.match(/^(.*)\s([↑↓])$/); if(!directional)return[{value:option,label:option,subtitle:'',disabled:false}];
    const[,optionLabel,arrow]=directional; const currentDirection:SortDirection=arrow==='↑'?'asc':'desc'; const alternateDirection:SortDirection=currentDirection==='asc'?'desc':'asc';
    const valueFor=(direction:SortDirection)=>`${optionLabel} ${direction==='asc'?'↑':'↓'}`;
    return([currentDirection,alternateDirection] as SortDirection[]).map((direction)=>({value:valueFor(direction),label:optionLabel,subtitle:'',disabled:false,direction}));
  }
  function normalizeOption(option:SelectOption):NormalizedSelectOption[]{if(typeof option==='string')return normalizeStringOption(option);return[{value:option.value,label:option.label,subtitle:option.subtitle??'',disabled:option.disabled??false,direction:option.direction}]}

  const normalized:NormalizedSelectOption[]=$derived(options.flatMap(normalizeOption));
  const selectedSet=$derived(new Set(values.map(String)));
  const selectedOptions=$derived(normalized.filter((option)=>selectedSet.has(option.value)));
  const selected=$derived(normalized.find((option)=>option.value===String(value))??(!allowEmpty?normalized.find((option)=>!option.disabled):undefined));
  const isEmpty=$derived(multiple?values.length===0:allowEmpty&&String(value)==='');
  const normalizedSearch=$derived(searchQuery.trim().toLocaleLowerCase());
  const visibleOptions:NormalizedSelectOption[]=$derived(onsearchchange||!searchable||!normalizedSearch?normalized:normalized.filter((option)=>`${option.label}\n${option.subtitle}`.toLocaleLowerCase().includes(normalizedSearch)));
  const addText=$derived(searchQuery.trim()?`${addLabel||'Add'} “${searchQuery.trim()}”`:(addLabel||'Add'));

  function firstEnabled(){return visibleOptions.findIndex((option)=>!option.disabled)}
  function move(direction:1|-1){if(!visibleOptions.length)return;let index=activeIndex<0?firstEnabled():activeIndex;for(let attempt=0;attempt<visibleOptions.length;attempt+=1){index=(index+direction+visibleOptions.length)%visibleOptions.length;if(!visibleOptions[index]?.disabled){activeIndex=index;void tick().then(()=>list?.querySelector<HTMLButtonElement>(`[data-index="${index}"]`)?.focus());return}}}
  function getNativeScrollbarWidth(){if(nativeScrollbarWidth!==undefined)return nativeScrollbarWidth;const probe=document.createElement('div');probe.style.position='fixed';probe.style.left='-10000px';probe.style.top='-10000px';probe.style.width='100px';probe.style.height='100px';probe.style.overflow='scroll';probe.style.pointerEvents='none';document.body.appendChild(probe);nativeScrollbarWidth=probe.offsetWidth-probe.clientWidth;probe.remove();return nativeScrollbarWidth}
  function measureIntrinsicPopupWidth(){if(!widthProbe)return;const popupProbe=widthProbe.querySelector<HTMLElement>('[data-select-width-popup]');const measuredPopup=popupProbe?.getBoundingClientRect().width??0;const scrollbarAllowance=getNativeScrollbarWidth();intrinsicPopupWidth=Math.max(Math.ceil(measuredPopup+scrollbarAllowance),searchable?240+scrollbarAllowance:0)}
  function measureText(text:string){if(!trigger)return Number.POSITIVE_INFINITY;const canvas=document.createElement('canvas'),context=canvas.getContext('2d');if(!context)return Number.POSITIVE_INFINITY;const style=getComputedStyle(trigger);context.font=`${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;return context.measureText(text).width}
  function updateMultiTriggerText(){if(!multiple)return;if(selectedOptions.length===0){multiTriggerText=placeholder;return}const available=Math.max(40,(trigger?.clientWidth??0)-74),labels=selectedOptions.map((option)=>option.label),all=labels.join(', ');if(measureText(all)<=available){multiTriggerText=all;return}for(let shown=labels.length-1;shown>=1;shown-=1){const candidate=`${labels.slice(0,shown).join(', ')} +${labels.length-shown}`;if(measureText(candidate)<=available){multiTriggerText=candidate;return}}multiTriggerText=`${labels.length} selected`}
  function positionPopup(){if(!open||!trigger)return;const margin=10,gap=5,desiredMaxHeight=304,minimumUsefulHeight=144,maximumPopupWidth=Math.min(544,window.innerWidth-margin*2),rect=trigger.getBoundingClientRect(),spaceBelow=Math.max(0,window.innerHeight-rect.bottom-gap-margin),spaceAbove=Math.max(0,rect.top-gap-margin),preferDown=spaceBelow>=Math.min(desiredMaxHeight,minimumUsefulHeight)||spaceBelow>=spaceAbove;popupPlacement=preferDown?'down':'up';const available=popupPlacement==='down'?spaceBelow:spaceAbove;popupMaxHeight=Math.max(96,Math.min(desiredMaxHeight,available));popupWidth=Math.min(maximumPopupWidth,Math.max(rect.width,intrinsicPopupWidth));const leftAligned=rect.left,rightAligned=rect.right-popupWidth;if(leftAligned+popupWidth<=window.innerWidth-margin){popupLeft=Math.max(margin,leftAligned);popupAlignment='left'}else if(rightAligned>=margin){popupLeft=rightAligned;popupAlignment='right'}else{popupLeft=Math.min(Math.max(leftAligned,margin),window.innerWidth-popupWidth-margin);popupAlignment='viewport'}popupTop=popupPlacement==='down'?rect.bottom+gap:Math.max(margin,rect.top-gap-Math.min(optionsPopup?.scrollHeight??popupMaxHeight,popupMaxHeight))}
  function show(){if(disabled||(!normalized.length&&!onsearchchange&&!onadd))return;searchQuery='';onsearchchange?.('');activeIndex=multiple?normalized.findIndex((option)=>selectedSet.has(option.value)&&!option.disabled):normalized.findIndex((option)=>option.value===selected?.value&&!option.disabled);if(activeIndex<0)activeIndex=firstEnabled();measureIntrinsicPopupWidth();open=true;void tick().then(()=>{positionPopup();requestAnimationFrame(positionPopup);if(searchable)searchInput?.focus();else list?.querySelector<HTMLButtonElement>(`[data-index="${activeIndex}"]`)?.focus()})}
  function choose(option:NormalizedSelectOption|undefined){if(!option||option.disabled)return;if(multiple){const next=new Set(values.map(String));if(next.has(option.value))next.delete(option.value);else next.add(option.value);values=normalized.filter((candidate)=>next.has(candidate.value)).map((candidate)=>candidate.value);onvalueschange?.(values);void tick().then(updateMultiTriggerText);return}value=option.value;onchange?.(option.value);open=false;searchQuery='';void tick().then(()=>trigger?.focus())}
  function add(event?:MouseEvent){event?.preventDefault();event?.stopPropagation();if(disabled||!onadd)return;const query=searchQuery.trim();open=false;searchQuery='';activeIndex=-1;onadd(query)}
  function clear(event?:MouseEvent){event?.stopPropagation();if(disabled||isEmpty)return;if(multiple){values=[];onvalueschange?.([]);void tick().then(updateMultiTriggerText);return}if(!allowEmpty)return;value='';onchange?.('');open=false;searchQuery='';void tick().then(()=>trigger?.focus())}
  function handleTriggerKey(event:KeyboardEvent){if(event.key==='ArrowDown'||event.key==='ArrowUp'||event.key==='Enter'||event.key===' '){event.preventDefault();show()}}
  function handleSearchKey(event:KeyboardEvent){if(event.key==='ArrowDown'){event.preventDefault();activeIndex=firstEnabled();void tick().then(()=>list?.querySelector<HTMLButtonElement>(`[data-index="${activeIndex}"]`)?.focus())}else if(event.key==='ArrowUp'){event.preventDefault();activeIndex=visibleOptions.length;move(-1)}else if(event.key==='Enter'){const first=visibleOptions[firstEnabled()];if(first){event.preventDefault();choose(first)}else if(onadd){event.preventDefault();add()}}else if(event.key==='Escape'){event.preventDefault();open=false;searchQuery='';void tick().then(()=>trigger?.focus())}}
  function handleOptionKey(event:KeyboardEvent,index:number){if(event.key==='ArrowDown'){event.preventDefault();move(1)}else if(event.key==='ArrowUp'){event.preventDefault();if(searchable&&index===firstEnabled())searchInput?.focus();else move(-1)}else if(event.key==='Enter'||event.key===' '){event.preventDefault();choose(visibleOptions[index])}else if(event.key==='Escape'){event.preventDefault();open=false;searchQuery='';void tick().then(()=>trigger?.focus())}else if(event.key==='Tab')open=false;else if(!searchable&&event.key.length===1&&!event.ctrlKey&&!event.metaKey&&!event.altKey){const query=event.key.toLocaleLowerCase(),match=visibleOptions.findIndex((option)=>!option.disabled&&option.label.toLocaleLowerCase().startsWith(query));if(match>=0){event.preventDefault();activeIndex=match;void tick().then(()=>list?.querySelector<HTMLButtonElement>(`[data-index="${match}"]`)?.focus())}}}
  function handleSearchInput(value:string){searchQuery=value;activeIndex=-1;onsearchchange?.(value);void tick().then(positionPopup)}
  $effect(()=>{const optionSignature=normalized.map((option)=>`${option.label}\u0000${option.subtitle}\u0000${option.direction??''}`).join('\u0001'),currentSearchable=searchable,selectedSignature=multiple?values.join('\u0001'):String(value);void tick().then(()=>{void optionSignature;void currentSearchable;void selectedSignature;measureIntrinsicPopupWidth();updateMultiTriggerText();if(open)positionPopup()})});
  $effect(()=>{if(!open)return;const reposition=()=>{positionPopup();updateMultiTriggerText()};window.addEventListener('resize',reposition);window.addEventListener('scroll',reposition,true);return()=>{window.removeEventListener('resize',reposition);window.removeEventListener('scroll',reposition,true)}});
</script>

<div class="v2-select-field" data-width={width} use:clickOutside={{enabled:open,onoutside:()=>open=false}}>
  {#if label}<label class="v2-field-label" for={id}>{label}</label>{/if}
  <div class="v2-select-control">
    <button bind:this={trigger} {id} class="v2-select-trigger" data-placeholder={isEmpty||undefined} type="button" {disabled} aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-options`} onclick={()=>open?open=false:show()} onkeydown={handleTriggerKey}>
      {#if width==='content'&&!multiple}
        <span class="v2-select-trigger-copy" style="display:grid;overflow:visible"><span style="grid-area:1 / 1;display:inline-flex;align-items:center;gap:6px;min-width:0;overflow:hidden"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{isEmpty?placeholder:selected?.label??placeholder}</span>{#if !isEmpty&&selected?.direction==='asc'}<ArrowUp class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}{#if !isEmpty&&selected?.direction==='desc'}<ArrowDown class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}</span>{#if allowEmpty}<span aria-hidden="true" style="grid-area:1 / 1;visibility:hidden;display:inline-flex;align-items:center;gap:6px;width:max-content;white-space:nowrap"><span>{placeholder}</span></span>{/if}{#each normalized as option (`trigger-sizer-${option.value}`)}<span aria-hidden="true" style="grid-area:1 / 1;visibility:hidden;display:inline-flex;align-items:center;gap:6px;width:max-content;white-space:nowrap"><span>{option.label}</span>{#if option.direction==='asc'}<ArrowUp class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}{#if option.direction==='desc'}<ArrowDown class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}</span>{/each}</span>
      {:else}
        <span class="v2-select-trigger-copy"><span>{multiple?multiTriggerText:isEmpty?placeholder:selected?.label??placeholder}</span>{#if !multiple&&!isEmpty&&selected?.direction==='asc'}<ArrowUp class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}{#if !multiple&&!isEmpty&&selected?.direction==='desc'}<ArrowDown class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}</span>
      {/if}
      <span class="v2-select-chevron" aria-hidden="true"></span>
    </button>
    {#if (multiple&&values.length>0)||(!multiple&&allowEmpty&&!isEmpty)}<button class="v2-select-clear" type="button" disabled={disabled} aria-label={`Clear ${label||(multiple?'selections':'selection')}`} onclick={clear}>×</button>{/if}
  </div>

  <div bind:this={widthProbe} aria-hidden="true" style="position:fixed;left:-10000px;top:-10000px;visibility:hidden;pointer-events:none;width:max-content;max-width:none"><div data-select-width-popup class="v2-select-options" data-searchable={searchable||undefined} style="position:static;left:auto;top:auto;width:max-content;min-width:0;max-width:none;max-height:none;overflow:visible;visibility:hidden">{#if searchable}<div class="v2-select-search" style="width:240px"><input tabindex="-1" value="" placeholder={searchPlaceholder} aria-hidden="true"></div>{/if}<div class="v2-select-option-list" style="width:max-content;max-width:none;overflow:visible">{#each normalized as option (`popup-probe-${option.value}`)}<button type="button" tabindex="-1" style="width:max-content;max-width:none;grid-template-columns:minmax(0,1fr)"><span class="v2-select-option-copy"><span class="v2-select-option-heading"><span class="v2-select-option-label">{option.label}</span></span></span></button>{/each}{#if onadd}<button type="button" tabindex="-1" class="v2-select-add"><Plus size={14}/><span>{addLabel||'Add'}</span></button>{/if}</div></div></div>

  {#if open}
    <div bind:this={optionsPopup} id={`${id}-options`} class="v2-select-options" data-searchable={searchable||undefined} data-placement={popupPlacement} data-alignment={popupAlignment} style={`top:${popupTop}px;left:${popupLeft}px;width:${popupWidth}px;max-height:${popupMaxHeight}px`}>
      {#if searchable}<div class="v2-select-search"><input bind:this={searchInput} value={searchQuery} placeholder={searchPlaceholder} aria-label={`Search ${label||'options'}`} oninput={(event)=>handleSearchInput(event.currentTarget.value)} onkeydown={handleSearchKey}></div>{/if}
      <div bind:this={list} class="v2-select-option-list" role="listbox" aria-multiselectable={multiple||undefined} aria-label={label||undefined}>
        {#each visibleOptions as option,index (option.value)}{@const optionSelected=multiple?selectedSet.has(option.value):!isEmpty&&option.value===selected?.value}<button type="button" role="option" aria-selected={optionSelected} disabled={option.disabled} data-index={index} data-active={index===activeIndex||undefined} data-selected={optionSelected||undefined} style="grid-template-columns:minmax(0,1fr)" onclick={()=>choose(option)} onfocus={()=>activeIndex=index} onkeydown={(event)=>handleOptionKey(event,index)}><span class="v2-select-option-copy"><span class="v2-select-option-heading"><span class="v2-select-option-label">{option.label}</span>{#if option.direction==='asc'}<ArrowUp class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}{#if option.direction==='desc'}<ArrowDown class="v2-select-direction-icon" size={14} aria-hidden="true"/>{/if}</span>{#if option.subtitle}<span class="v2-select-option-subtitle">{option.subtitle}</span>{/if}</span></button>{:else}<div class="v2-select-empty">{loading?'Loading options…':'No matching options'}</div>{/each}
        {#if hasMore}<button type="button" class="v2-select-option-load-more" disabled={loading} onclick={()=>onloadmore?.()}>{loading?'Loading…':'Load more'}</button>{/if}
        {#if onadd}<button type="button" class="v2-select-add" onclick={add}><Plus size={14} aria-hidden="true"/><span>{addText}</span></button>{/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .v2-select-add{width:100%;display:flex;align-items:center;gap:7px;border:0;border-top:1px solid var(--v2-line);border-radius:0;background:transparent;color:#9bb9e2;padding:9px;cursor:pointer;text-align:left;font:inherit}
  .v2-select-add:hover,.v2-select-add:focus-visible{background:#172231;color:var(--v2-text)}
  .v2-select-add:focus-visible{outline:2px solid #4169a8;outline-offset:-2px}
</style>
