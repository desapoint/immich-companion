import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import Pagination from './Pagination.svelte';

describe('Pagination', () => {
  it('renders the visible item range and current page summary', () => {
    const { body } = render(Pagination, {
      props: {
        currentPage: 4,
        totalPages: 4,
        totalItems: 83,
        pageSize: 25,
        onpagechange: () => {},
      },
    });

    expect(body).toContain('76–83 of 83');
    expect(body).toContain('Page 4 of 4');
    expect(body).toContain('aria-current="page"');
  });

  it('keeps page-size controls opt-in', () => {
    const { body } = render(Pagination, {
      props: {
        currentPage: 1,
        totalPages: 3,
        totalItems: 60,
        pageSize: 24,
        onpagechange: () => {},
      },
    });

    expect(body).not.toContain('Items per page');
  });
});
