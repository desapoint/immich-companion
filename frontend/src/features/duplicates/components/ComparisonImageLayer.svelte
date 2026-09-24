<script lang="ts">
  import type { ComparisonImageAsset } from '../types/comparisonLayer';

  let {
    image,
    transform,
    top = false,
    opacity,
    visible = true,
  }: {
    image: ComparisonImageAsset;
    transform: string;
    top?: boolean;
    opacity?: number;
    visible?: boolean;
  } = $props();

  const layerClass = $derived([
    top ? 'top' : '',
  ].filter(Boolean).join(' '));
  const layerStyle = $derived([
    opacity === undefined ? '' : `opacity:${opacity}`,
    `visibility:${visible ? 'visible' : 'hidden'}`,
  ].filter(Boolean).join(';'));
</script>

<div class={`v2-compare-layer${layerClass ? ` ${layerClass}` : ''}`} style={layerStyle} aria-hidden={!visible}>
  <div class="v2-compare-transform" style={`transform:${transform}`}>
    <img src={image.src} alt={image.label} onload={image.onload} onerror={image.onerror}>
  </div>
</div>
