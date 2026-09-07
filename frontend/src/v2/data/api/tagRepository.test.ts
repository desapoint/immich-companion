import { describe, expect, it, vi } from 'vitest';

import { createTagRepository, type TagApiFetcher } from './tagRepository';

const parent = {
  id: '11111111-1111-4111-8111-111111111111',
  name: 'Places',
  color: '#7ea6ff',
  parent_id: null,
  parent_path: [],
  asset_count: 8,
  child_count: 1,
  children: [],
};
const child = {
  id: '22222222-2222-4222-8222-222222222222',
  name: 'Montréal',
  color: '#68d391',
  parent_id: parent.id,
  parent_path: ['Places'],
  asset_count: 5,
  child_count: 0,
  children: [],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function page(items = [parent, child], currentPage = 1, pages = 1) {
  return { items, total: items.length, page: currentPage, page_size: 200, pages };
}

describe('live V2 tag repository', () => {
  it('maps flat hierarchy rows and all demo sort and search modes', async () => {
    const fetcher = vi.fn<TagApiFetcher>(async () => jsonResponse({
      items: [child], total: 42, page: 2, page_size: 48, pages: 3,
    }));
    const repository = createTagRepository(fetcher);

    const result = await repository.search({
      page: 2,
      pageSize: 48,
      query: ' Montréal ',
      includeHierarchy: true,
      sort: { field: 'children', direction: 'desc' },
    });

    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/tags/manage?page=2&page_size=48&sort=child_count&direction=desc&flat=true&include_hierarchy=true&search=Montr%C3%A9al');
    expect(result).toEqual({
      items: [{
        id: child.id,
        name: 'Montréal',
        path: 'Places / Montréal',
        parent: 'Places',
        assets: 5,
        children: 0,
        color: '#68d391',
        synthetic: false,
        realTagIds: [child.id],
      }],
      total: 42,
      pageSize: 48,
      page: 2,
      nextCursor: '3',
    });
  });

  it('uses cursor pages for searchable tag options', async () => {
    const fetcher = vi.fn<TagApiFetcher>(async () => jsonResponse({
      items: [child], total: 3, page: 2, page_size: 1, pages: 3,
    }));
    const repository = createTagRepository(fetcher);

    const result = await repository.searchOptions({ query: 'Places', pageSize: 1, cursor: '2' });

    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/tags/manage?page=2&page_size=1&sort=path&direction=asc&flat=true&include_hierarchy=true&search=Places');
    expect(result).toEqual({
      items: [{ value: child.id, label: 'Places / Montréal', subtitle: '5 assets' }],
      nextCursor: '3',
    });
  });

  it('excludes the edited tag and its descendants from parent choices', async () => {
    const grandchild = {
      ...child,
      id: '33333333-3333-4333-8333-333333333333',
      name: 'Old Port',
      parent_id: child.id,
      parent_path: ['Places', 'Montréal'],
    };
    const fetcher = vi.fn<TagApiFetcher>(async () => jsonResponse(page([parent, child, grandchild])));
    const repository = createTagRepository(fetcher);

    expect(await repository.parentOptions(child.id)).toEqual([
      { value: 'Places', label: 'Places', subtitle: 'Root' },
    ]);
  });

  it('resolves canonical parent paths for create and reparent operations', async () => {
    const requests: Array<{ path: string; method: string; body: unknown }> = [];
    const fetcher = vi.fn<TagApiFetcher>(async (input, init) => {
      const path = String(input);
      if (path.startsWith('/api/tags/manage?')) return jsonResponse(page());
      requests.push({
        path,
        method: init?.method ?? 'GET',
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      return jsonResponse(child);
    });
    const repository = createTagRepository(fetcher);

    expect(await repository.create('Montréal', '#68d391', 'Places')).toMatchObject({
      id: child.id,
      tag_name: 'Places / Montréal',
    });
    expect(await repository.update(child.id, { parentPath: '', name: 'Montreal' })).toEqual({
      affectedIds: [child.id],
      failed: [],
    });
    expect(requests).toEqual([
      {
        path: '/api/tags/manage',
        method: 'POST',
        body: { name: 'Montréal', color: '#68d391', parent_id: parent.id },
      },
      {
        path: `/api/tags/manage/${child.id}`,
        method: 'PATCH',
        body: { name: 'Montreal', parent_id: null },
      },
    ]);
  });

  it('connects detail and batch deletion while retaining failure context', async () => {
    const fetcher = vi.fn<TagApiFetcher>(async (input) => {
      const path = String(input);
      if (path.endsWith('/missing')) return jsonResponse({ detail: 'Tag not found.' }, 404);
      if (path.endsWith('/batch-delete')) {
        return jsonResponse({ completed: [child.id], failed: [parent.id], total: 2 });
      }
      return jsonResponse(child);
    });
    const repository = createTagRepository(fetcher);

    expect(await repository.getById(child.id)).toMatchObject({
      id: child.id,
      tag_name: 'Places / Montréal',
    });
    expect(await repository.getById('missing')).toBeUndefined();
    expect(await repository.delete([child.id, parent.id])).toEqual({
      affectedIds: [child.id],
      failed: [{
        id: parent.id,
        reason: 'Immich could not delete this tag. Delete child tags first if it is a parent.',
      }],
    });
  });

  it('returns an update failure when a selected parent disappeared', async () => {
    const fetcher = vi.fn<TagApiFetcher>(async () => jsonResponse(page([parent])));
    const repository = createTagRepository(fetcher);

    expect(await repository.update(child.id, { parentPath: 'Missing' })).toEqual({
      affectedIds: [],
      failed: [{ id: child.id, reason: 'Parent tag “Missing” no longer exists.' }],
    });
  });
});
