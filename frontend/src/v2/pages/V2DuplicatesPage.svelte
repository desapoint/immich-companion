<script lang="ts">
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { comparisonMemberData, demoCompareImage, demoDifferenceMask } from '../demo/duplicateVisuals';

  type Mode='Side by side'|'Swipe'|'Transparency'|'Difference';
  let tab=$state('Review'), compare=$state(false), group=$state(1), member=$state(0), reference=$state(0), mode=$state<Mode>('Side by side'), zoom=$state(100), split=$state(50), opacity=$state(50), panX=$state(0), panY=$state(0), diffHue=$state(190), diffContrast=$state(180), diffBinary=$state(true), dragging=$state(false), lastX=$state(0), lastY=$state(0), decisions=$state<Record<string,string>>({}), compareViewport=$state<HTMLElement|null>(null);
  const groups=[{id:1,count:2,state:'Actionable',tone:'ok',kind:'Exact pair'},{id:2,count:2,state:'Needs review',tone:'warn',kind:'Similar pair'},{id:3,count:3,state:'Actionable',tone:'ok',kind:'Exact group'},{id:4,count:5,state:'Needs decisions',tone:'warn',kind:'Mixed group'},{id:5,count:6,state:'Actionable',tone:'ok',kind:'Similarity cluster'},{id:6,count:9,state:'Blocked',tone:'bad',kind:'Large cluster'},{id:7,count:10,state:'Needs review',tone:'warn',kind:'Large similarity cluster'}] as const;
  const activeCount=$derived(groups.find(g=>g.id===group)?.count??2);
  const selectedData=$derived(comparisonMemberData(group,member));
  const referenceData=$derived(comparisonMemberData(group,reference));
  const selectedImage=$derived(demoCompareImage(group,member));
  const referenceImage=$derived(demoCompareImage(group,reference));
  const differenceImage=$derived(demoDifferenceMask(group,member,reference,diffHue,diffContrast,diffBinary));
  const transform=$derived(`translate(${panX}px,${panY}px) scale(${zoom/100})`);
  const decisionKey=$derived(`${group}:${member}`);

  function openCompare(g:number,i:number){group=g;member=i;reference=0;compare=true;requestAnimationFrame(fit)}
  function fit(){zoom=100;panX=0;panY=0}
  function actual(){const rect=compareViewport?.getBoundingClientRect();if(!rect?.width||!rect.height){fit();return}const fitScale=Math.min(rect.width/800,rect.height/600);zoom=Math.max(10,Math.min(800,(1/fitScale)*100));panX=0;panY=0}
  function prev(){member=(member-1+activeCount)%activeCount}
  function next(){member=(member+1)%activeCount}
  function pointerDown(e:PointerEvent){if((e.target as HTMLElement).closest('button,input,select,label'))return;dragging=true;lastX=e.clientX;lastY=e.clientY;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)}
  function pointerMove(e:PointerEvent){if(!dragging)return;panX+=e.clientX-lastX;panY+=e.clientY-lastY;lastX=e.clientX;lastY=e.clientY}
  function wheel(e:WheelEvent){e.preventDefault();const rect=(e.currentTarget as HTMLElement).getBoundingClientRect();const anchorX=e.clientX-rect.left-rect.width/2;const anchorY=e.clientY-rect.top-rect.height/2;const old=zoom;const nextZoom=Math.max(10,Math.min(800,zoom*(e.deltaY<0?1.12:1/1.12)));const ratio=nextZoom/old;panX=anchorX-(anchorX-panX)*ratio;panY=anchorY-(anchorY-panY)*ratio;zoom=nextZoom}
  function setMode(next:Mode){mode=next;requestAnimationFrame(fit)}
  function setDecision(decision:string){decisions={...decisions,[decisionKey]:decision}}
</script>

<svelte:window onkeydown={(e)=>{if(e.key==='Escape'&&compare)compare=false}} onpointerup={()=>dragging=false}/>

<V2PageLayout title="Duplicates" description="Review exact and similarity duplicate groups, save member decisions, and process only actionable groups.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Scan similar</V2Button><V2Button variant="primary">Review actions</V2Button></V2Inline>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Review','Rules & discovery','Resolution history']} active={tab} onselect={(value)=>tab=value}/>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Review filter"><V2Stack gap="sm"><SelectField id="duplicate-review-filter" label="Group state" options={['All groups','Needs review','Auto-ready','Blocked']}/><V2Button>Select auto-ready</V2Button></V2Stack></V2Section><V2Section title="Similarity"><V2Field label="Threshold" value="82"/><V2Inline gap="sm"><V2Button>Scan again</V2Button><V2Button>Cancel scan</V2Button></V2Inline><span class="v2-small v2-muted">Similarity is review evidence only.</span></V2Section><V2Section title="Bulk preset"><V2Stack gap="sm"><V2Button>Keep all copies</V2Button><V2Button>Mark all for deletion</V2Button><V2Button>Stack each group</V2Button></V2Stack></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar>
      <V2Badge text="18 groups"/><V2Badge tone="ok" text="7 ready"/><V2Badge tone="warn" text="3 blocked"/>
      {#snippet actions()}<V2Button onclick={()=>decisions={}}>Clear decisions</V2Button>{/snippet}
    </V2Toolbar>
    {#each groups as g}
      <V2Card class="v2-duplicate-group">
        <V2Stack gap="md">
          <V2Inline justify="between" align="start" wrap={true}><V2Inline gap="sm" wrap={true}><input type="checkbox"><b>Group {g.id}</b><V2Badge text={`${g.count} images`}/><V2Badge text={g.kind}/><V2Badge tone={g.tone} text={g.state}/></V2Inline><V2Inline gap="sm" wrap={true}><V2Button>Apply preset</V2Button><V2Button onclick={()=>openCompare(g.id,0)}>Compare</V2Button></V2Inline></V2Inline>
          <div class="v2-duplicate-members">{#each Array.from({length:g.count},(_,i)=>i) as i}<div class="v2-duplicate-member"><button class="v2-duplicate-image" onclick={()=>openCompare(g.id,i)}><img src={demoCompareImage(g.id,i)} alt={`Duplicate member ${i+1}`}><span class="v2-duplicate-image-meta"><b>Member {i+1}</b><small>{i===0?'Suggested keeper':i%3===0?'External':'Immich'}</small></span></button><div class="v2-duplicate-actions"><V2Button variant={i===0?'primary':'default'}>Keep</V2Button><V2Button>Delete</V2Button><V2Button>Stack</V2Button></div></div>{/each}</div>
        </V2Stack>
      </V2Card>
    {/each}
  </V2Zone>

  {#snippet inspector()}<V2Zone><V2Section title="Batch readiness"><V2Card><V2Stack gap="sm"><b>2 selected groups</b><span class="v2-small v2-muted">All selected groups must pass actionability guards before execution.</span><V2Inline gap="sm"><V2Badge tone="ok" text="2 ready"/><V2Badge text="0 blocked"/></V2Inline></V2Stack></V2Card></V2Section><V2Section title="Current group"><V2Card><span class="v2-small">Keeper: Member 1<br>Delete: 1<br>Stack: 0<br>Online: all</span></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>

{#if compare}
  <div class="v2-compare-viewer" role="dialog" aria-modal="true">
    <div class="v2-compare-top">
      <V2Inline gap="sm" wrap={true}><V2Button onclick={()=>compare=false}>✕</V2Button><b>Duplicate comparison</b><V2Badge text={`Group ${group}`}/><V2Badge text={`${activeCount} images`}/></V2Inline>
      <V2Inline gap="sm" wrap={true}><V2Segmented items={['Side by side','Swipe','Transparency','Difference']} active={mode} onselect={(value)=>setMode(value as Mode)} ariaLabel="Comparison mode"/><V2Button onclick={()=>zoom=Math.max(10,zoom/1.25)}>−</V2Button><span class="v2-zoom-readout">{Math.round(zoom)}%</span><V2Button onclick={()=>zoom=Math.min(800,zoom*1.25)}>+</V2Button><V2Button onclick={fit}>Fit</V2Button><V2Button onclick={actual}>1:1</V2Button><V2Button onclick={prev}>← Previous</V2Button><V2Button onclick={next}>Next →</V2Button><V2Button onclick={()=>reference=member}>Set as reference</V2Button><V2Button onclick={()=>window.alert('Mock integrity analysis: current asset is healthy.')}>Analyze integrity</V2Button></V2Inline>
    </div>

    <div class="v2-compare-main">
      <section class="v2-compare-visual">
        <div class="v2-compare-stage" class:single={mode!=='Side by side'} onpointerdown={pointerDown} onpointermove={pointerMove} onwheel={wheel}>
          {#if mode==='Side by side'}
            <div class="v2-compare-pane" bind:this={compareViewport}><span class="v2-compare-label">Selected image</span><div class="v2-compare-transform" style={`transform:${transform}`}><img src={selectedImage} alt={`Member ${member+1}`}></div></div>
            <div class="v2-compare-pane reference"><span class="v2-compare-label">Reference / keeper candidate</span><div class="v2-compare-transform" style={`transform:${transform}`}><img src={referenceImage} alt={`Reference member ${reference+1}`}></div></div>
          {:else}
            <div class={`v2-compare-overlay mode-${mode.toLowerCase().replaceAll(' ','-')}`} bind:this={compareViewport}>
              {#if mode==='Difference'}
                <div class="v2-compare-transform" style={`transform:${transform}`}><img src={differenceImage} alt="Generated difference preview"></div>
                <div class="v2-difference-controls"><label><span>Color</span><input type="range" min="0" max="360" bind:value={diffHue}><b>{diffHue}°</b></label><V2Checkbox label="Two colors only" checked={diffBinary} onchange={(checked)=>diffBinary=checked}/>{#if !diffBinary}<label><span>Contrast</span><input type="range" min="50" max="300" bind:value={diffContrast}><b>{diffContrast}%</b></label>{/if}</div>
              {:else}
                <div class="v2-compare-layer"><div class="v2-compare-transform" style={`transform:${transform}`}><img src={referenceImage} alt={`Reference member ${reference+1}`}></div></div>
                <div class="v2-compare-layer top" style={mode==='Transparency'?`opacity:${opacity/100}`:`clip-path:inset(0 ${100-split}% 0 0)`}><div class="v2-compare-transform" style={`transform:${transform}`}><img src={selectedImage} alt={`Selected member ${member+1}`}></div></div>
                {#if mode==='Swipe'}<div class="v2-compare-hover"><span>Split</span><input type="range" min="0" max="100" bind:value={split}><b>{split}%</b></div>{/if}
                {#if mode==='Transparency'}<div class="v2-compare-hover"><span>Transparency</span><input type="range" min="0" max="100" bind:value={opacity}><b>{opacity}%</b></div>{/if}
              {/if}
              <div class="v2-compare-legend"><span>Reference {reference+1}</span><span>Selected {member+1}</span></div>
            </div>
          {/if}
        </div>

        <div class="v2-filmstrip">{#each Array.from({length:activeCount},(_,i)=>i) as i}{@const data=comparisonMemberData(group,i)}<button class="v2-thumb" class:active={i===member} class:reference={i===reference} onclick={()=>member=i}><img src={demoCompareImage(group,i)} alt={`Member ${i+1} example`}><small>Member {i+1}</small><small class="v2-muted">{data.size} · {data.similarity}%</small></button>{/each}</div>
      </section>

      <aside class="v2-compare-data">
        <V2Section title="Quick comparison" actions={undefined}><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>Visual similarity</span><b>{selectedData.similarity}%</b></V2Inline><V2Inline justify="between"><span>File size difference</span><b>{selectedData.sizeNum-referenceData.sizeNum>=0?'+':''}{(selectedData.sizeNum-referenceData.sizeNum).toFixed(1)} MB</b></V2Inline><V2Inline justify="between"><span>Resolution</span><b>{selectedData.dims===referenceData.dims?'Same':'Different'}</b></V2Inline><V2Inline justify="between"><span>Integrity</span><V2Badge tone="ok" text="Healthy"/></V2Inline></V2Stack></V2Card></V2Section>
        <V2Section title="Metadata side by side"><div class="v2-compare-grid"><b>Selected</b><b>Reference</b><span>{selectedData.name}</span><span>{referenceData.name}</span><span>{selectedData.source}</span><span>{referenceData.source}</span><span class:changed={selectedData.size!==referenceData.size}>{selectedData.size}</span><span class:changed={selectedData.size!==referenceData.size}>{referenceData.size}</span><span class:changed={selectedData.dims!==referenceData.dims}>{selectedData.dims}</span><span class:changed={selectedData.dims!==referenceData.dims}>{referenceData.dims}</span><span class:changed={selectedData.taken!==referenceData.taken}>{selectedData.taken}</span><span class:changed={selectedData.taken!==referenceData.taken}>{referenceData.taken}</span><span>{selectedData.codec}</span><span>{referenceData.codec}</span><span>{selectedData.library}</span><span>{referenceData.library}</span><span class:changed={selectedData.uploaded!==referenceData.uploaded}>{selectedData.uploaded}</span><span class:changed={selectedData.uploaded!==referenceData.uploaded}>{referenceData.uploaded}</span></div></V2Section>
        <V2Section title="Decision context"><V2Card><V2Stack gap="sm"><b>Highlighted cells differ.</b><span class="v2-small v2-muted">Use image evidence and metadata together. Similarity alone does not authorize deletion.</span></V2Stack></V2Card></V2Section>
      </aside>
    </div>

    <div class="v2-compare-actions"><span><b>Member {member+1}</b> <span class="v2-small v2-muted">Choose disposition for this member</span></span><V2Inline gap="sm" wrap={true}>{#each ['keep','delete','stack'] as decision}<V2Button active={decisions[decisionKey]===decision} onclick={()=>setDecision(decision)}>{decision[0].toUpperCase()+decision.slice(1)}</V2Button>{/each}<V2Button disabled={decisions[decisionKey]!=='stack'} onclick={()=>window.alert(`Member ${member+1} set as stack primary in this mockup.`)}>Set stack primary</V2Button></V2Inline></div>
  </div>
{/if}