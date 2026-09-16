import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import V2VideoPlayer, { formatMediaTime } from './V2VideoPlayer.svelte';

describe('V2VideoPlayer', () => {
  it('formats short and long media durations', () => {
    expect(formatMediaTime(0)).toBe('0:00');
    expect(formatMediaTime(65.9)).toBe('1:05');
    expect(formatMediaTime(3661)).toBe('1:01:01');
    expect(formatMediaTime(Number.NaN)).toBe('0:00');
  });

  it('renders an obvious play affordance and complete playback controls', () => {
    const { body } = render(V2VideoPlayer, { props: { src: '/video', poster: '/poster', label: 'Fixture movie' } });
    expect(body).toContain('aria-label="Play Fixture movie"');
    expect(body).toContain('aria-label="Seek video"');
    expect(body).toContain('aria-label="Video volume"');
    expect(body).toContain('aria-label="Toggle fullscreen video"');
    expect(body).toContain('poster="/poster"');
  });
});
