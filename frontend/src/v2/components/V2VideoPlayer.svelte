<script module lang="ts">
  export function formatMediaTime(value: number): string {
    if (!Number.isFinite(value) || value < 0) return '0:00';
    const seconds = Math.floor(value);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainder = seconds % 60;
    return hours > 0
      ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
      : `${minutes}:${String(remainder).padStart(2, '0')}`;
  }
</script>

<script lang="ts">
  import { Expand, LoaderCircle, Pause, Play, Volume2, VolumeX } from '@lucide/svelte';
  import V2RangeSlider from './V2RangeSlider.svelte';

  let { src, poster = null, label, onerror }: { src: string; poster?: string | null; label: string; onerror?: () => void } = $props();

  let root = $state<HTMLDivElement>();
  let video = $state<HTMLVideoElement>();
  let playing = $state(false);
  let waiting = $state(false);
  let currentTime = $state(0);
  let duration = $state(0);
  let volume = $state(1);
  let muted = $state(false);

  async function togglePlayback(): Promise<void> {
    if (!video) return;
    if (video.paused || video.ended) {
      try { await video.play(); } catch { playing = false; waiting = false; }
    } else video.pause();
  }

  function seek(value: number | string): void {
    if (!video || !duration) return;
    const next = Number(value);
    if (!Number.isFinite(next)) return;
    const target = Math.min(duration, Math.max(0, next));
    video.currentTime = target;
    currentTime = target;
  }

  function setVolume(value: number | string): void {
    if (!video) return;
    const next = Math.min(1, Math.max(0, Number(value)));
    if (!Number.isFinite(next)) return;
    video.volume = next;
    video.muted = next === 0;
    volume = video.volume;
    muted = video.muted;
  }

  function toggleMute(): void {
    if (!video) return;
    video.muted = !video.muted;
    muted = video.muted;
  }

  async function toggleFullscreen(): Promise<void> {
    if (!root) return;
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await root.requestFullscreen();
    } catch { /* Fullscreen can be unavailable under embedded browser policies. */ }
  }

  function syncMetadata(): void {
    if (!video) return;
    duration = Number.isFinite(video.duration) ? video.duration : 0;
    currentTime = Number.isFinite(video.currentTime) ? video.currentTime : 0;
    volume = video.volume;
    muted = video.muted;
  }
</script>

<div class="v2-video-player" bind:this={root} role="group" aria-label={`Video player · ${label}`}>
  <!-- svelte-ignore a11y_media_has_caption -->
  <video
    bind:this={video}
    {src}
    poster={poster ?? undefined}
    playsinline
    preload="metadata"
    aria-label={label}
    onclick={() => void togglePlayback()}
    onloadedmetadata={syncMetadata}
    onloadeddata={syncMetadata}
    ondurationchange={syncMetadata}
    ontimeupdate={() => { if (video) currentTime = video.currentTime; }}
    onseeking={() => waiting = true}
    onseeked={() => { waiting = false; syncMetadata(); }}
    oncanplay={() => waiting = false}
    onplay={() => { playing = true; waiting = false; }}
    onpause={() => playing = false}
    onended={() => { playing = false; waiting = false; }}
    onwaiting={() => waiting = true}
    onplaying={() => waiting = false}
    onvolumechange={() => { if (video) { volume = video.volume; muted = video.muted; } }}
    onerror={onerror}
  >Your browser cannot play the compatible video stream.</video>

  {#if !playing && !waiting}
    <button type="button" class="v2-video-primary-play" aria-label={`Play ${label}`} onclick={() => void togglePlayback()}><Play size={34} fill="currentColor"/></button>
  {/if}
  {#if waiting}<span class="v2-video-waiting" aria-label="Video buffering"><LoaderCircle size={28}/></span>{/if}

  <div class="v2-video-controls">
    <V2RangeSlider class="v2-video-seek" min={0} max={duration || 1} step={0.1} value={currentTime} grow={true} showValue={false} trackHeight={4} thumbSize={14} thumbBorderWidth={2} hitHeight={22} ariaLabel="Seek video" disabled={!duration} onchange={seek}/>
    <div class="v2-video-control-row">
      <button type="button" class="v2-video-control" aria-label={playing ? 'Pause video' : 'Play video'} title={playing ? 'Pause' : 'Play'} onclick={() => void togglePlayback()}>{#if playing}<Pause size={20} fill="currentColor"/>{:else}<Play size={20} fill="currentColor"/>{/if}</button>
      <span class="v2-video-time">{formatMediaTime(currentTime)} / {formatMediaTime(duration)}</span>
      <div class="v2-video-spacer"></div>
      <button type="button" class="v2-video-control" aria-label={muted || volume === 0 ? 'Unmute video' : 'Mute video'} title="Mute" onclick={toggleMute}>{#if muted || volume === 0}<VolumeX size={20}/>{:else}<Volume2 size={20}/>{/if}</button>
      <V2RangeSlider class="v2-video-volume" min={0} max={1} step={0.05} value={muted ? 0 : volume} width={88} showValue={false} trackHeight={4} thumbSize={14} thumbBorderWidth={2} hitHeight={22} ariaLabel="Video volume" onchange={setVolume}/>
      <button type="button" class="v2-video-control" aria-label="Toggle fullscreen video" title="Fullscreen" onclick={() => void toggleFullscreen()}><Expand size={20}/></button>
    </div>
  </div>
</div>

<style>
  .v2-video-player{position:relative;width:100%;height:100%;min-height:0;overflow:hidden;background:#000;color:#fff}
  video{display:block;width:100%;height:100%;object-fit:contain;background:#000;cursor:pointer}
  .v2-video-primary-play{position:absolute;left:50%;top:50%;display:grid;place-items:center;width:4.5rem;height:4.5rem;transform:translate(-50%,-50%);border:1px solid rgb(255 255 255/.7);border-radius:50%;background:rgb(0 0 0/.58);color:#fff;cursor:pointer;backdrop-filter:blur(5px);transition:transform 120ms ease,background 120ms ease}.v2-video-primary-play:hover{transform:translate(-50%,-50%) scale(1.06);background:rgb(0 0 0/.72)}.v2-video-primary-play:focus-visible,.v2-video-control:focus-visible{outline:2px solid #fff;outline-offset:2px}
  .v2-video-waiting{position:absolute;left:50%;top:50%;display:grid;place-items:center;transform:translate(-50%,-50%);filter:drop-shadow(0 1px 4px #000)}.v2-video-waiting :global(svg){animation:v2-video-spin .8s linear infinite}
  .v2-video-controls{position:absolute;z-index:2;left:0;right:0;bottom:0;display:grid;gap:.25rem;padding:2.5rem .75rem .65rem;background:linear-gradient(transparent,rgb(0 0 0/.82));opacity:1;transition:opacity 140ms ease}
  .v2-video-control-row{display:flex;align-items:center;gap:.5rem;min-width:0}.v2-video-control{display:grid;place-items:center;flex:0 0 auto;border:0;border-radius:.4rem;background:transparent;color:#fff;padding:.3rem;cursor:pointer}.v2-video-control:hover{background:rgb(255 255 255/.16)}.v2-video-spacer{flex:1}.v2-video-time{font-variant-numeric:tabular-nums;font-size:.75rem;text-shadow:0 1px 3px #000;white-space:nowrap}
  :global(.v2-video-seek){width:100%;min-width:0}.v2-video-controls :global(.v2-range-track){background:rgb(255 255 255/.35)}.v2-video-controls :global(.v2-range-fill){background:var(--v2-accent,#7ea6ff)}.v2-video-controls :global(.v2-range-thumb){border-color:var(--v2-accent,#7ea6ff)}
  @keyframes v2-video-spin{to{transform:rotate(360deg)}}
  @media(max-width:620px){:global(.v2-video-volume){display:none}.v2-video-primary-play{width:4rem;height:4rem}.v2-video-controls{padding-inline:.45rem}}
</style>
