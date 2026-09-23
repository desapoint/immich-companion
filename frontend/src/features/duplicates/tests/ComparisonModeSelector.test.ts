import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import ComparisonModeSelector from '../components/ComparisonModeSelector.svelte';

describe('ComparisonModeSelector', () => {
  it('keeps all comparison modes while separating visual and analysis choices', () => {
    const { body } = render(ComparisonModeSelector, { props: { mode: 'Difference' } });

    expect(body).toContain('Visual modes');
    expect(body).toContain('Analysis modes');
    for (const mode of ['Side by side', 'Swipe', 'Flicker', 'Transparency', 'Difference', 'Local changes']) {
      expect(body).toContain(`>${mode}<`);
    }
    expect(body).toContain('value="Difference" selected');
  });

  it('provides a compact labeled selector for small screens', () => {
    const { body } = render(ComparisonModeSelector);

    expect(body).toContain('comparison-mode-mobile');
    expect(body).toContain('<select aria-label="Comparison mode"');
    expect(body).toContain('<optgroup label="Visual modes">');
    expect(body).toContain('<optgroup label="Analysis modes">');
  });
});
