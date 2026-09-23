import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import StatusContent from '../components/StatusContent.svelte';
import type { StatusSnapshot } from '../../../lib/types/status';

const snapshot: StatusSnapshot = {
  health: {
    status: 'ok',
    ready: true,
    environment: 'test',
    safe_mode: false,
    dependencies: {
      immich: { status: 'ok', configured: true, detail: 'Connected in 42ms' },
      companion_database: { status: 'ok', configured: true, detail: 'PostgreSQL is ready' },
    },
  },
  version: { name: 'Companion', version: '2.0.0', environment: 'test' },
  capabilities: {
    destructive_actions: true,
    immich_api: true,
    companion_database: true,
    implemented: ['status'],
    planned: [],
  },
};

describe('StatusContent dependency layout', () => {
  it('keeps the semantic table and renders a stacked mobile representation', () => {
    const { body } = render(StatusContent, {
      props: { state: { kind: 'loaded', snapshot }, onrefresh: () => {} },
    });

    expect(body).toContain('class="status-dependency-table');
    expect(body).toContain('<table class="v2-table"');
    expect(body).toMatch(/class="status-dependency-cards(?: [^"]+)?"/);
    expect(body).toContain('aria-label="Dependency details"');
    expect(body).toContain('Connected in 42ms');
    expect(body).toContain('PostgreSQL is ready');
  });
});
