import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';
import V2Pagination from './V2Pagination.svelte';

describe('V2Pagination', () => {
  it('renders shaftless icon controls, accessible hover labels, and clickable gaps', () => {
    const { body } = render(V2Pagination, { props: { page: 10, pageSize: 10, total: 200, onpage: vi.fn() } });
    expect(body).toContain('title="First page"');
    expect(body).toContain('title="Previous page"');
    expect(body).toContain('title="Next page"');
    expect(body).toContain('title="Last page"');
    expect(body).toContain('aria-label="Jump to a page; hidden pages 2 through 6"');
    expect(body).toContain('aria-label="Jump to a page; hidden pages 14 through 19"');
    expect(body).toContain('aria-current="page"');
    for (const page of [7, 8, 9, 10, 11, 12, 13]) expect(body).toContain(page === 10 ? `aria-label="Page ${page}, current page"` : `aria-label="Go to page ${page}"`);
    expect(body).not.toContain('Previous</button>');
    expect(body).not.toContain('Next →');
  });

  it('disables both backward controls on the first page', () => {
    const { body } = render(V2Pagination, { props: { page: 1, pageSize: 24, total: 240, onpage: vi.fn() } });
    expect(body).toMatch(/disabled=""[^>]*title="First page"/);
    expect(body).toMatch(/disabled=""[^>]*title="Previous page"/);
  });
});
