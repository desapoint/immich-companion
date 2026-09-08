<script lang="ts">
  let {
    size = '1.4rem',
    thickness = '0.16rem',
    trackColor = 'var(--color-border-strong)',
    accentColor = 'var(--color-accent-strong)',
  }: {
    size?: string;
    thickness?: string;
    trackColor?: string;
    accentColor?: string;
  } = $props();

  const spinnerStyle = $derived(
    `--loading-spinner-size:${size};--loading-spinner-thickness:${thickness};--loading-spinner-track:${trackColor};--loading-spinner-accent:${accentColor}`,
  );
</script>

<span class="loading-spinner" aria-hidden="true" style={spinnerStyle}></span>

<style>
  .loading-spinner {
    display: inline-block;
    flex: none;
    width: var(--loading-spinner-size);
    height: var(--loading-spinner-size);
    box-sizing: border-box;
    border: var(--loading-spinner-thickness) solid var(--loading-spinner-track);
    border-top-color: var(--loading-spinner-accent);
    border-radius: 50%;
    animation: loading-spinner-spin 800ms linear infinite;
  }

  @keyframes loading-spinner-spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .loading-spinner {
      animation: none;
    }
  }
</style>
