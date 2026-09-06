import type { AssetSelectionState } from '../components/assetSelection';

export type DemoAssetRecord = {
  id: string;
  owner_id: string | null;
  library_id: string | null;
  asset_type: 'IMAGE' | 'VIDEO' | 'AUDIO' | 'OTHER';
  original_file_name: string;
  original_path: string | null;
  original_mime_type: string | null;
  checksum: string | null;
  file_size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  file_created_at: string;
  file_modified_at: string;
  local_date_time: string | null;
  immich_created_at: string | null;
  immich_updated_at: string | null;
  is_favorite: boolean;
  is_archived: boolean;
  is_offline: boolean;
  is_edited: boolean;
  has_metadata: boolean;
  visibility: string | null;
  live_photo_video_id: string | null;
  tags: DemoAssetTagSnapshot[];
  stack: DemoAssetStackSnapshot | null;
  synced_at: string;
};

export type DemoTrashApiAsset = {
  id: string;
  type: DemoAssetRecord['asset_type'];
  original_file_name: string;
  original_mime_type: string | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  taken_at: string;
  file_modified_at: string;
  is_favorite: boolean;
  is_archived: boolean;
  restore_path: string | null;
};

export type DemoAssetTagSnapshot = { id: string; name: string; value: string; color: string | null };
export type DemoAssetStackSnapshot = { id: string; primaryAssetId: string; assetCount: number; assets: string[] };

export type DemoAlbumRecord = {
  id: string;
  album_name: string;
  description: string;
  album_thumbnail_asset_id: string | null;
  asset_count: number;
  immich_created_at: string;
  immich_updated_at: string;
  synced_at: string;
};

export type DemoAlbumAssetRecord = { album_id: string; asset_id: string };
export type DemoTagRecord = { id: string; tag_name: string; tag_value: string; color: string | null; asset_count: number; synced_at: string };
export type DemoTagAssetRecord = { tag_id: string; asset_id: string };
type DemoTrashRelationshipSnapshot = { album_ids: string[]; tag_ids: string[]; stack: DemoAssetStackSnapshot | null };
type DemoAssetOverride = Pick<DemoAssetRecord, 'is_favorite' | 'is_archived'>;

type PersistedDemoState = {
  version: 4;
  asset_overrides: Record<string, DemoAssetOverride>;
  trash_api_ids: string[];
  albums: DemoAlbumRecord[];
  tags: DemoTagRecord[];
  album_assets: DemoAlbumAssetRecord[];
  tag_assets: DemoTagAssetRecord[];
  trash_relationships: Record<string, DemoTrashRelationshipSnapshot>;
  stacks: Record<string, DemoAssetStackSnapshot | null>;
};

type PersistedDemoStateV3 = Omit<PersistedDemoState, 'version' | 'albums' | 'tags' | 'trash_relationships'> & { version: 3 };

const STORAGE_KEY = 'immichCompanionV2DemoAssetState.v4';
const PREVIOUS_STORAGE_KEY = 'immichCompanionV2DemoAssetState.v3';
const LEGACY_STORAGE_KEYS = ['immichCompanionV2DemoAssetState.v1', 'immichCompanionV2DemoAssetState.v2'];
const INDEXED_ASSET_COUNT = 2418;
const INITIAL_TRASH_COUNT = 126;
const TOTAL_DEMO_ASSET_COUNT = INDEXED_ASSET_COUNT + INITIAL_TRASH_COUNT;
const TAG_COUNT = 100;
const ALBUM_COUNT = 25;
const DEMO_OWNER_ID = uuidFor(900001);
const DEMO_LIBRARY_ID = uuidFor(900002);
const SYNCED_AT = '2026-09-05T20:00:00.000Z';
const TAG_COLORS = ['#8ab4f8', '#f7c66b', '#81c995', '#f28b82', '#c58af9', '#78d9ec', '#fdd663', null] as const;
let mutableSequence = 0;

const DEEP_TAG_PATHS: Record<string, string> = {
  'People / Family': 'People / Family / Immediate family',
  'People / Parents': 'People / Family / Parents',
  'People / Grandparents': 'People / Family / Parents / Grandparents',
  'People / Siblings': 'People / Family / Siblings',
  'People / Kids': 'People / Family / Children / Kids',
  'People / Friends': 'People / Friends / Close friends',
  'People / Coworkers': 'People / Work / Coworkers',
  'Places / Home': 'Places / Canada / Québec / Montréal / Home',
  'Places / Cottage': 'Places / Canada / Québec / Laurentides / Cottage',
  'Places / City': 'Places / Canada / Québec / Montréal / Downtown',
  'Places / Park': 'Places / Canada / Québec / Montréal / Parks',
  'Places / Museum': 'Places / Canada / Québec / Montréal / Museums',
  'Places / Restaurant': 'Places / Canada / Québec / Montréal / Restaurants',
  'Places / Airport': 'Places / Canada / Québec / Montréal / Airport',
  'Events / Birthday': 'Events / Family / Celebrations / Birthday',
  'Events / Wedding': 'Events / Family / Celebrations / Wedding',
  'Events / Holiday': 'Events / Family / Holidays',
  'Events / School': 'Events / Family / School',
  'Events / Work': 'Events / Work / Company events',
  'Events / Concert': 'Events / Entertainment / Music / Concert',
  'Events / Festival': 'Events / Entertainment / Festivals',
  'Events / Sports': 'Events / Sports / Games',
  'Subjects / Nature': 'Subjects / Outdoors / Nature',
  'Subjects / Flowers': 'Subjects / Outdoors / Nature / Flowers',
  'Subjects / Sunset': 'Subjects / Outdoors / Sky / Sunset',
  'Subjects / Architecture': 'Subjects / Places / Architecture',
  'Subjects / Food': 'Subjects / Food / Meals',
  'Subjects / Pet': 'Subjects / Animals / Pets',
  'Workflow / To print': 'Workflow / Output / Print / To print',
  'Workflow / To share': 'Workflow / Output / Share / To share',
  'Workflow / To edit': 'Workflow / Editing / To edit',
  'Workflow / Needs metadata': 'Workflow / Review / Metadata / Needs metadata',
  'Workflow / Needs location': 'Workflow / Review / Metadata / Needs location',
  'Workflow / Needs date': 'Workflow / Review / Metadata / Needs date',
  'Quality / Best shot': 'Quality / Keep / Best shot',
  'Quality / Duplicate candidate': 'Quality / Review / Duplicate candidate',
  'Media / RAW': 'Media / Photo / RAW',
  'Media / JPEG': 'Media / Photo / JPEG',
  'Media / HEIC': 'Media / Photo / HEIC',
  'Media / MP4': 'Media / Video / MP4',
  'Theme / Hiking': 'Theme / Outdoors / Hiking',
  'Theme / Camping': 'Theme / Outdoors / Camping',
  'Theme / Cooking': 'Theme / Home / Cooking',
  'Theme / Garden': 'Theme / Home / Garden',
};

function uuidFor(index: number): string {
  return `00000000-0000-4000-8000-${index.toString(16).padStart(12, '0')}`;
}

function newDemoId(kind: string): string {
  mutableSequence += 1;
  return `demo-${kind}-${Date.now().toString(36)}-${mutableSequence.toString(36)}`;
}

function isoFor(index: number): string {
  const day = 21 - (index % 18);
  const hour = index % 24;
  return `2026-08-${String(Math.max(1, day)).padStart(2, '0')}T${String(hour).padStart(2, '0')}:00:00.000Z`;
}

function slug(value: string): string {
  return value.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

function tagValueForPath(path: string): string {
  return path.split(' / ').map(slug).filter(Boolean).join('/');
}

function seedAlbums(): DemoAlbumRecord[] {
  const names = [
    'Family', 'Vacation', 'Favorites review', 'Summer 2026', 'Winter 2026', 'Birthdays', 'Pets', 'Landscapes', 'Portraits',
    'Weekend trips', 'Road trips', 'Food & restaurants', 'Friends', 'Work events', 'Screenshots', 'Receipts', 'Architecture',
    'Nature walks', 'Concerts', 'Sports', 'Kids', 'Holidays', 'Home projects', 'To print', 'Photo book candidates',
  ];
  return names.slice(0, ALBUM_COUNT).map((name, index) => ({
    id: uuidFor(910000 + index),
    album_name: name,
    description: index % 4 === 0 ? `Demo collection for ${name.toLowerCase()}` : '',
    album_thumbnail_asset_id: null,
    asset_count: 0,
    immich_created_at: `2026-0${(index % 8) + 1}-01T00:00:00.000Z`,
    immich_updated_at: '2026-09-01T00:00:00.000Z',
    synced_at: SYNCED_AT,
  }));
}

function seedTags(): DemoTagRecord[] {
  const groups: Array<[string, string[]]> = [
    ['People', ['Family', 'Friends', 'Kids', 'Parents', 'Grandparents', 'Siblings', 'Coworkers', 'Guests', 'Self', 'Group']],
    ['Places', ['Home', 'Cottage', 'Beach', 'Mountains', 'City', 'Park', 'Lake', 'Museum', 'Restaurant', 'Airport']],
    ['Events', ['Birthday', 'Holiday', 'Wedding', 'Concert', 'Festival', 'Sports', 'School', 'Work', 'Party', 'Road trip']],
    ['Subjects', ['Pet', 'Food', 'Architecture', 'Nature', 'Flowers', 'Sunset', 'Vehicle', 'Document', 'Screenshot', 'Product']],
    ['Quality', ['Keep', 'Review', 'Best shot', 'Blurry', 'Dark', 'Duplicate candidate', 'Edited', 'HDR', 'Portrait mode', 'Panorama']],
    ['Workflow', ['To print', 'To share', 'To edit', 'To archive', 'To delete', 'Needs metadata', 'Needs location', 'Needs date', 'Needs people', 'Synced']],
    ['Season', ['Spring', 'Summer', 'Autumn', 'Winter', 'January', 'February', 'March', 'April', 'May', 'June']],
    ['Media', ['Photo', 'Video', 'Live photo', 'Slow motion', 'Timelapse', 'RAW', 'JPEG', 'HEIC', 'MP4', 'Scan']],
    ['Theme', ['Vacation', 'Travel', 'Home project', 'Garden', 'Cooking', 'Hiking', 'Cycling', 'Camping', 'Shopping', 'Night out']],
    ['Color', ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Purple', 'Pink', 'Black & white', 'Warm', 'Cool']],
  ];
  const definitions = groups.flatMap(([group, names]) => names.map((name) => {
    const raw = `${group} / ${name}`;
    const path = DEEP_TAG_PATHS[raw] ?? raw;
    return { name: path, value: tagValueForPath(path) };
  }));
  return definitions.slice(0, TAG_COUNT).map((tag, index) => ({
    id: uuidFor(920000 + index),
    tag_name: tag.name,
    tag_value: tag.value,
    color: TAG_COLORS[index % TAG_COLORS.length],
    asset_count: 0,
    synced_at: SYNCED_AT,
  }));
}

const BASE_ALBUMS = seedAlbums();
const BASE_TAGS = seedTags();

function buildAsset(index: number): DemoAssetRecord {
  const isVideo = index % 11 === 0;
  const created = isoFor(index);
  return {
    id: uuidFor(index + 1), owner_id: DEMO_OWNER_ID, library_id: index % 5 === 0 ? DEMO_LIBRARY_ID : null,
    asset_type: isVideo ? 'VIDEO' : 'IMAGE', original_file_name: `${isVideo ? 'VID' : 'IMG'}_${String(index + 1).padStart(4, '0')}.${isVideo ? 'mp4' : 'jpg'}`,
    original_path: `/demo/library/2026/${isVideo ? 'video' : 'photo'}/${index + 1}`,
    original_mime_type: isVideo ? 'video/mp4' : 'image/jpeg', checksum: `demo-checksum-${index + 1}`,
    file_size_bytes: 1_500_000 + index * 4096, width: isVideo ? 1920 : index % 4 === 0 ? 4032 : 3024,
    height: isVideo ? 1080 : index % 4 === 0 ? 3024 : 4032, duration: isVideo ? 12_000 + (index % 40) * 1000 : null,
    file_created_at: created, file_modified_at: created, local_date_time: created, immich_created_at: created, immich_updated_at: created,
    is_favorite: index % 7 === 0, is_archived: index % 13 === 0, is_offline: index % 53 === 0, is_edited: index % 17 === 0,
    has_metadata: index % 29 !== 0, visibility: index % 97 === 0 ? 'hidden' : null, live_photo_video_id: null,
    tags: [], stack: null, synced_at: SYNCED_AT,
  };
}

const baseAssetsById = new Map<string, DemoAssetRecord>(Array.from({ length: TOTAL_DEMO_ASSET_COUNT }, (_, index) => {
  const asset = buildAsset(index);
  return [asset.id, asset] as const;
}));

function initialTrashIds(): Set<string> {
  return new Set(Array.from({ length: INITIAL_TRASH_COUNT }, (_, offset) => uuidFor(INDEXED_ASSET_COUNT + offset + 1)));
}
const BASE_TRASH_IDS = initialTrashIds();

function seedTagMemberships(): DemoTagAssetRecord[] {
  const memberships: DemoTagAssetRecord[] = [];
  const indexedAssets = [...baseAssetsById.values()].filter((asset) => !BASE_TRASH_IDS.has(asset.id));
  indexedAssets.forEach((asset, index) => {
    const count = index % 10 === 0 ? 0 : 1 + (index % 4);
    const tagIndexes = new Set<number>();
    for (let offset = 0; offset < count; offset += 1) tagIndexes.add((index * 7 + offset * 23 + Math.floor(index / 11)) % BASE_TAGS.length);
    for (const tagIndex of tagIndexes) memberships.push({ tag_id: BASE_TAGS[tagIndex].id, asset_id: asset.id });
  });
  return memberships;
}

function seedAlbumMemberships(): DemoAlbumAssetRecord[] {
  const memberships: DemoAlbumAssetRecord[] = [];
  const indexedAssets = [...baseAssetsById.values()].filter((asset) => !BASE_TRASH_IDS.has(asset.id));
  indexedAssets.forEach((asset, index) => {
    const count = index % 8 === 0 ? 0 : index % 5 === 0 ? 2 : 1;
    const albumIndexes = new Set<number>();
    for (let offset = 0; offset < count; offset += 1) albumIndexes.add((index * 5 + offset * 11 + Math.floor(index / 17)) % BASE_ALBUMS.length);
    for (const albumIndex of albumIndexes) memberships.push({ album_id: BASE_ALBUMS[albumIndex].id, asset_id: asset.id });
  });
  return memberships;
}

function seedStacks(): Record<string, DemoAssetStackSnapshot> {
  const stacks: Record<string, DemoAssetStackSnapshot> = {};
  const indexedIds = [...baseAssetsById.values()].filter((asset) => !BASE_TRASH_IDS.has(asset.id)).map((asset) => asset.id);
  let cursor = 5, stackIndex = 0;
  while (cursor < indexedIds.length - 6) {
    const size = 2 + (stackIndex % 5);
    const memberIds = indexedIds.slice(cursor, cursor + size);
    const stack: DemoAssetStackSnapshot = { id: uuidFor(930000 + stackIndex), primaryAssetId: memberIds[stackIndex % memberIds.length], assetCount: memberIds.length, assets: memberIds };
    for (const id of memberIds) stacks[id] = stack;
    stackIndex += 1;
    cursor += size + 17 + (stackIndex % 13);
  }
  return stacks;
}

const BASE_TAG_ASSETS = seedTagMemberships();
const BASE_ALBUM_ASSETS = seedAlbumMemberships();
const BASE_STACKS = seedStacks();

function cloneTag(tag: DemoTagRecord): DemoTagRecord { return { ...tag }; }
function cloneAlbum(album: DemoAlbumRecord): DemoAlbumRecord { return { ...album }; }
function cloneStack(stack: DemoAssetStackSnapshot | null): DemoAssetStackSnapshot | null { return stack ? { ...stack, assets: [...stack.assets] } : null; }
function cloneAsset(asset: DemoAssetRecord): DemoAssetRecord { return { ...asset, tags: asset.tags.map((tag) => ({ ...tag })), stack: cloneStack(asset.stack) }; }
function tagSnapshot(tag: DemoTagRecord): DemoAssetTagSnapshot { return { id: tag.id, name: tag.tag_name, value: tag.tag_value, color: tag.color }; }

function applyRelationships(
  assets: DemoAssetRecord[], albumsSource: DemoAlbumRecord[], tagsSource: DemoTagRecord[], albumAssets: DemoAlbumAssetRecord[], tagAssets: DemoTagAssetRecord[], stacks: Record<string, DemoAssetStackSnapshot | null>,
): { albums: DemoAlbumRecord[]; tags: DemoTagRecord[] } {
  const assetById = new Map(assets.map((asset) => [asset.id, asset]));
  const tagById = new Map(tagsSource.map((tag) => [tag.id, tag]));
  for (const asset of assets) { asset.tags = []; asset.stack = cloneStack(stacks[asset.id] ?? null); }
  for (const membership of tagAssets) {
    const asset = assetById.get(membership.asset_id), tag = tagById.get(membership.tag_id);
    if (asset && tag) asset.tags.push(tagSnapshot(tag));
  }
  const albums = albumsSource.map(cloneAlbum), tags = tagsSource.map(cloneTag);
  for (const album of albums) {
    const memberIds = albumAssets.filter((membership) => membership.album_id === album.id).map((membership) => membership.asset_id);
    album.asset_count = memberIds.length;
    album.album_thumbnail_asset_id = memberIds[0] ?? null;
  }
  for (const tag of tags) tag.asset_count = tagAssets.filter((membership) => membership.tag_id === tag.id).length;
  return { albums, tags };
}

function toTrashApiAsset(asset: DemoAssetRecord): DemoTrashApiAsset {
  return { id: asset.id, type: asset.asset_type, original_file_name: asset.original_file_name, original_mime_type: asset.original_mime_type, width: asset.width, height: asset.height, duration: asset.duration, taken_at: asset.file_created_at, file_modified_at: asset.file_modified_at, is_favorite: asset.is_favorite, is_archived: asset.is_archived, restore_path: asset.original_path };
}

function buildState(
  trashIds: Set<string>, albumsSource: DemoAlbumRecord[] = BASE_ALBUMS, tagsSource: DemoTagRecord[] = BASE_TAGS,
  albumAssets: DemoAlbumAssetRecord[] = BASE_ALBUM_ASSETS, tagAssets: DemoTagAssetRecord[] = BASE_TAG_ASSETS,
  stacks: Record<string, DemoAssetStackSnapshot | null> = BASE_STACKS, trashRelationships: Record<string, DemoTrashRelationshipSnapshot> = {},
) {
  const assets: DemoAssetRecord[] = [], trash_api_items: DemoTrashApiAsset[] = [];
  for (const base of baseAssetsById.values()) {
    const asset = cloneAsset(base);
    if (trashIds.has(asset.id)) trash_api_items.push(toTrashApiAsset(asset)); else assets.push(asset);
  }
  const activeIds = new Set(assets.map((asset) => asset.id));
  const activeAlbumAssets = albumAssets.filter((membership) => activeIds.has(membership.asset_id) && albumsSource.some((album) => album.id === membership.album_id)).map((membership) => ({ ...membership }));
  const activeTagAssets = tagAssets.filter((membership) => activeIds.has(membership.asset_id) && tagsSource.some((tag) => tag.id === membership.tag_id)).map((membership) => ({ ...membership }));
  const activeStacks: Record<string, DemoAssetStackSnapshot | null> = {};
  for (const [assetId, stack] of Object.entries(stacks)) if (activeIds.has(assetId)) activeStacks[assetId] = cloneStack(stack);
  const relationships = applyRelationships(assets, albumsSource, tagsSource, activeAlbumAssets, activeTagAssets, activeStacks);
  return { assets, trash_api_items, album_assets: activeAlbumAssets, tag_assets: activeTagAssets, trash_relationships: { ...trashRelationships }, ...relationships };
}

const initialState = buildState(BASE_TRASH_IDS);
export const demoAssetState = $state({
  assets: initialState.assets,
  trash_api_items: initialState.trash_api_items,
  albums: initialState.albums,
  album_assets: initialState.album_assets,
  tags: initialState.tags,
  tag_assets: initialState.tag_assets,
  trash_relationships: initialState.trash_relationships,
  initialized: false,
  revision: 0,
});

function currentStacks(): Record<string, DemoAssetStackSnapshot | null> {
  const stacks: Record<string, DemoAssetStackSnapshot | null> = {};
  for (const asset of demoAssetState.assets) stacks[asset.id] = cloneStack(asset.stack);
  return stacks;
}

function refreshRelationshipSummaries(): void {
  const relationships = applyRelationships(demoAssetState.assets, demoAssetState.albums, demoAssetState.tags, demoAssetState.album_assets, demoAssetState.tag_assets, currentStacks());
  demoAssetState.albums = relationships.albums;
  demoAssetState.tags = relationships.tags;
}

function persist(): void {
  demoAssetState.revision += 1;
  if (typeof sessionStorage === 'undefined') return;
  const overrides: Record<string, DemoAssetOverride> = {};
  for (const asset of demoAssetState.assets) {
    const base = baseAssetsById.get(asset.id);
    if (base && (asset.is_favorite !== base.is_favorite || asset.is_archived !== base.is_archived)) overrides[asset.id] = { is_favorite: asset.is_favorite, is_archived: asset.is_archived };
  }
  for (const item of demoAssetState.trash_api_items) {
    const base = baseAssetsById.get(item.id);
    if (base && (item.is_favorite !== base.is_favorite || item.is_archived !== base.is_archived)) overrides[item.id] = { is_favorite: item.is_favorite, is_archived: item.is_archived };
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
    version: 4, asset_overrides: overrides, trash_api_ids: demoAssetState.trash_api_items.map((asset) => asset.id),
    albums: demoAssetState.albums, tags: demoAssetState.tags, album_assets: demoAssetState.album_assets, tag_assets: demoAssetState.tag_assets,
    trash_relationships: demoAssetState.trash_relationships, stacks: currentStacks(),
  } satisfies PersistedDemoState));
}

export function initializeDemoAssetState(): void {
  if (demoAssetState.initialized) return;
  demoAssetState.initialized = true;
  if (typeof sessionStorage === 'undefined') return;
  for (const key of LEGACY_STORAGE_KEYS) sessionStorage.removeItem(key);
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY) ?? sessionStorage.getItem(PREVIOUS_STORAGE_KEY);
    if (!raw) return;
    const persisted = JSON.parse(raw) as PersistedDemoState | PersistedDemoStateV3;
    if ((persisted.version !== 4 && persisted.version !== 3) || !Array.isArray(persisted.trash_api_ids)) return;
    const albumsSource = persisted.version === 4 && Array.isArray(persisted.albums) ? persisted.albums : BASE_ALBUMS;
    const tagsSource = persisted.version === 4 && Array.isArray(persisted.tags) ? persisted.tags : BASE_TAGS;
    const rebuilt = buildState(new Set(persisted.trash_api_ids), albumsSource, tagsSource, Array.isArray(persisted.album_assets) ? persisted.album_assets : BASE_ALBUM_ASSETS, Array.isArray(persisted.tag_assets) ? persisted.tag_assets : BASE_TAG_ASSETS, persisted.stacks ?? BASE_STACKS, persisted.version === 4 ? persisted.trash_relationships ?? {} : {});
    for (const asset of rebuilt.assets) { const override = persisted.asset_overrides?.[asset.id]; if (override) { asset.is_favorite = Boolean(override.is_favorite); asset.is_archived = Boolean(override.is_archived); } }
    for (const item of rebuilt.trash_api_items) { const override = persisted.asset_overrides?.[item.id]; if (override) { item.is_favorite = Boolean(override.is_favorite); item.is_archived = Boolean(override.is_archived); } }
    demoAssetState.assets = rebuilt.assets; demoAssetState.trash_api_items = rebuilt.trash_api_items; demoAssetState.albums = rebuilt.albums;
    demoAssetState.album_assets = rebuilt.album_assets; demoAssetState.tags = rebuilt.tags; demoAssetState.tag_assets = rebuilt.tag_assets; demoAssetState.trash_relationships = rebuilt.trash_relationships;
    demoAssetState.revision += 1;
    if (persisted.version === 3) persist();
  } catch { sessionStorage.removeItem(STORAGE_KEY); }
}

export function resetDemoAssetState(): void {
  const rebuilt = buildState(BASE_TRASH_IDS);
  demoAssetState.assets = rebuilt.assets; demoAssetState.trash_api_items = rebuilt.trash_api_items; demoAssetState.albums = rebuilt.albums;
  demoAssetState.album_assets = rebuilt.album_assets; demoAssetState.tags = rebuilt.tags; demoAssetState.tag_assets = rebuilt.tag_assets; demoAssetState.trash_relationships = rebuilt.trash_relationships;
  demoAssetState.revision += 1;
  if (typeof sessionStorage !== 'undefined') { sessionStorage.removeItem(STORAGE_KEY); sessionStorage.removeItem(PREVIOUS_STORAGE_KEY); for (const key of LEGACY_STORAGE_KEYS) sessionStorage.removeItem(key); }
}

export function indexedDemoAssets(): DemoAssetRecord[] { return demoAssetState.assets; }
export function trashApiDemoAssets(): DemoTrashApiAsset[] { return demoAssetState.trash_api_items; }
export function demoAssetById(id: string): DemoAssetRecord | undefined { return demoAssetState.assets.find((asset) => asset.id === id); }
export function selectedDemoAssetIds(selection: AssetSelectionState<string>, matchingIds: readonly string[]): string[] { return selection.allMatchingSelected ? matchingIds.filter((id) => !selection.excludedIds.has(id)) : matchingIds.filter((id) => selection.selectedIds.has(id)); }

function mutateIndexedAssets(ids: readonly string[], mutate: (asset: DemoAssetRecord) => void): void {
  const idSet = new Set(ids);
  for (const asset of demoAssetState.assets) if (idSet.has(asset.id)) mutate(asset);
  persist();
}

export function setDemoAssetsFavorite(ids: readonly string[], favorite: boolean): void { mutateIndexedAssets(ids, (asset) => { asset.is_favorite = favorite; }); }
export function setDemoAssetsArchived(ids: readonly string[], archived: boolean): void { mutateIndexedAssets(ids, (asset) => { asset.is_archived = archived; }); }
export function syncDemoAssets(ids: readonly string[]): void { const now = new Date().toISOString(); mutateIndexedAssets(ids, (asset) => { asset.synced_at = now; }); }

export function createDemoAlbum(name: string, description = ''): DemoAlbumRecord | undefined {
  const trimmed = name.trim(); if (!trimmed) return undefined;
  const now = new Date().toISOString();
  const album: DemoAlbumRecord = { id: newDemoId('album'), album_name: trimmed, description: description.trim(), album_thumbnail_asset_id: null, asset_count: 0, immich_created_at: now, immich_updated_at: now, synced_at: now };
  demoAssetState.albums = [...demoAssetState.albums, album]; persist(); return album;
}

export function updateDemoAlbum(id: string, patch: { name?: string; description?: string }): void {
  const now = new Date().toISOString();
  demoAssetState.albums = demoAssetState.albums.map((album) => album.id === id ? { ...album, album_name: patch.name?.trim() || album.album_name, description: patch.description?.trim() ?? album.description, immich_updated_at: now, synced_at: now } : album);
  persist();
}

export function deleteDemoAlbums(ids: readonly string[]): void {
  const idSet = new Set(ids); demoAssetState.albums = demoAssetState.albums.filter((album) => !idSet.has(album.id));
  demoAssetState.album_assets = demoAssetState.album_assets.filter((membership) => !idSet.has(membership.album_id)); refreshRelationshipSummaries(); persist();
}

export function addDemoAssetsToAlbum(assetIds: readonly string[], albumId: string): void {
  const validAssets = new Set(demoAssetState.assets.map((asset) => asset.id)), existing = new Set(demoAssetState.album_assets.map((membership) => `${membership.album_id}:${membership.asset_id}`));
  const additions = assetIds.filter((id) => validAssets.has(id) && !existing.has(`${albumId}:${id}`)).map((asset_id) => ({ album_id: albumId, asset_id }));
  if (!demoAssetState.albums.some((album) => album.id === albumId) || additions.length === 0) return;
  demoAssetState.album_assets = [...demoAssetState.album_assets, ...additions]; refreshRelationshipSummaries(); persist();
}

export function removeDemoAssetsFromAlbums(assetIds: readonly string[], albumIds?: readonly string[]): void {
  const assetSet = new Set(assetIds), albumSet = albumIds ? new Set(albumIds) : null;
  demoAssetState.album_assets = demoAssetState.album_assets.filter((membership) => !(assetSet.has(membership.asset_id) && (!albumSet || albumSet.has(membership.album_id)))); refreshRelationshipSummaries(); persist();
}

export function createDemoTag(name: string, color: string | null = null, parentPath = ''): DemoTagRecord | undefined {
  const leaf = name.trim(); if (!leaf) return undefined; const path = parentPath.trim() ? `${parentPath.trim()} / ${leaf}` : leaf;
  if (demoAssetState.tags.some((tag) => tag.tag_name.toLocaleLowerCase() === path.toLocaleLowerCase())) return undefined;
  const now = new Date().toISOString(); const tag: DemoTagRecord = { id: newDemoId('tag'), tag_name: path, tag_value: tagValueForPath(path), color, asset_count: 0, synced_at: now };
  demoAssetState.tags = [...demoAssetState.tags, tag]; persist(); return tag;
}

export function updateDemoTag(id: string, patch: { name?: string; color?: string | null; parentPath?: string }): void {
  const target = demoAssetState.tags.find((tag) => tag.id === id); if (!target) return;
  const oldPath = target.tag_name, oldParts = oldPath.split(' / '), leaf = patch.name?.trim() || oldParts.at(-1) || oldPath;
  const currentParent = oldParts.slice(0, -1).join(' / '), parent = patch.parentPath === undefined ? currentParent : patch.parentPath.trim();
  const nextPath = parent ? `${parent} / ${leaf}` : leaf, now = new Date().toISOString();
  demoAssetState.tags = demoAssetState.tags.map((tag) => {
    if (tag.id === id) return { ...tag, tag_name: nextPath, tag_value: tagValueForPath(nextPath), color: patch.color === undefined ? tag.color : patch.color, synced_at: now };
    if (tag.tag_name.startsWith(`${oldPath} / `)) { const moved = `${nextPath}${tag.tag_name.slice(oldPath.length)}`; return { ...tag, tag_name: moved, tag_value: tagValueForPath(moved), synced_at: now }; }
    return tag;
  });
  refreshRelationshipSummaries(); persist();
}

export function deleteDemoTags(ids: readonly string[]): void {
  const roots = demoAssetState.tags.filter((tag) => ids.includes(tag.id)).map((tag) => tag.tag_name);
  const deleting = new Set(demoAssetState.tags.filter((tag) => ids.includes(tag.id) || roots.some((root) => tag.tag_name.startsWith(`${root} / `))).map((tag) => tag.id));
  demoAssetState.tags = demoAssetState.tags.filter((tag) => !deleting.has(tag.id)); demoAssetState.tag_assets = demoAssetState.tag_assets.filter((membership) => !deleting.has(membership.tag_id)); refreshRelationshipSummaries(); persist();
}

export function addDemoTagsToAssets(assetIds: readonly string[], tagIds: readonly string[]): void {
  const validAssets = new Set(demoAssetState.assets.map((asset) => asset.id)), validTags = new Set(demoAssetState.tags.map((tag) => tag.id)), existing = new Set(demoAssetState.tag_assets.map((membership) => `${membership.tag_id}:${membership.asset_id}`));
  const additions: DemoTagAssetRecord[] = [];
  for (const asset_id of assetIds) for (const tag_id of tagIds) if (validAssets.has(asset_id) && validTags.has(tag_id) && !existing.has(`${tag_id}:${asset_id}`)) additions.push({ tag_id, asset_id });
  if (additions.length === 0) return; demoAssetState.tag_assets = [...demoAssetState.tag_assets, ...additions]; refreshRelationshipSummaries(); persist();
}

export function removeDemoTagsFromAssets(assetIds: readonly string[], tagIds?: readonly string[]): void {
  const assetSet = new Set(assetIds), tagSet = tagIds ? new Set(tagIds) : null;
  demoAssetState.tag_assets = demoAssetState.tag_assets.filter((membership) => !(assetSet.has(membership.asset_id) && (!tagSet || tagSet.has(membership.tag_id)))); refreshRelationshipSummaries(); persist();
}

export function stackDemoAssets(ids: readonly string[]): void {
  const valid = [...new Set(ids)].filter((id) => demoAssetState.assets.some((asset) => asset.id === id)); if (valid.length < 2) return;
  removeDemoAssetsFromStacks(valid, false); const stack: DemoAssetStackSnapshot = { id: newDemoId('stack'), primaryAssetId: valid[0], assetCount: valid.length, assets: valid };
  for (const asset of demoAssetState.assets) if (valid.includes(asset.id)) asset.stack = cloneStack(stack); persist();
}

export function setDemoStackPrimary(assetId: string): void {
  const asset = demoAssetById(assetId), stack = asset?.stack; if (!stack) return;
  for (const item of demoAssetState.assets) if (item.stack?.id === stack.id) item.stack = { ...item.stack, primaryAssetId: assetId }; persist();
}

export function removeDemoAssetsFromStacks(ids: readonly string[], persistChange = true): void {
  const idSet = new Set(ids), affectedStackIds = new Set(demoAssetState.assets.filter((asset) => idSet.has(asset.id) && asset.stack).map((asset) => asset.stack!.id));
  for (const stackId of affectedStackIds) {
    const members = demoAssetState.assets.filter((asset) => asset.stack?.id === stackId && !idSet.has(asset.id));
    const primary = members.find((asset) => asset.stack?.primaryAssetId === asset.id)?.id ?? members[0]?.id;
    for (const asset of demoAssetState.assets) {
      if (asset.stack?.id !== stackId) continue;
      if (idSet.has(asset.id) || members.length < 2) asset.stack = null;
      else asset.stack = { ...asset.stack, assets: members.map((member) => member.id), assetCount: members.length, primaryAssetId: primary! };
    }
  }
  if (persistChange) persist();
}

export function removeDemoCompleteStack(assetId: string): void {
  const stackId = demoAssetById(assetId)?.stack?.id; if (!stackId) return;
  for (const asset of demoAssetState.assets) if (asset.stack?.id === stackId) asset.stack = null; persist();
}

export function trashDemoAssets(ids: readonly string[]): void {
  const idSet = new Set(ids), moving = demoAssetState.assets.filter((asset) => idSet.has(asset.id)); if (moving.length === 0) return;
  for (const asset of moving) demoAssetState.trash_relationships[asset.id] = {
    album_ids: demoAssetState.album_assets.filter((membership) => membership.asset_id === asset.id).map((membership) => membership.album_id),
    tag_ids: demoAssetState.tag_assets.filter((membership) => membership.asset_id === asset.id).map((membership) => membership.tag_id),
    stack: cloneStack(asset.stack),
  };
  demoAssetState.assets = demoAssetState.assets.filter((asset) => !idSet.has(asset.id)); demoAssetState.trash_api_items = [...demoAssetState.trash_api_items, ...moving.map(toTrashApiAsset)];
  demoAssetState.album_assets = demoAssetState.album_assets.filter((membership) => !idSet.has(membership.asset_id)); demoAssetState.tag_assets = demoAssetState.tag_assets.filter((membership) => !idSet.has(membership.asset_id));
  refreshRelationshipSummaries(); persist();
}

export function restoreDemoTrashAssets(ids: readonly string[]): void {
  const idSet = new Set(ids), restoring = demoAssetState.trash_api_items.filter((asset) => idSet.has(asset.id)); if (restoring.length === 0) return;
  demoAssetState.trash_api_items = demoAssetState.trash_api_items.filter((asset) => !idSet.has(asset.id)); const existing = new Set(demoAssetState.assets.map((asset) => asset.id));
  for (const item of restoring) {
    if (existing.has(item.id)) continue; const base = baseAssetsById.get(item.id); if (!base) continue;
    const refreshed = cloneAsset(base); refreshed.is_favorite = item.is_favorite; refreshed.is_archived = item.is_archived; refreshed.synced_at = new Date().toISOString();
    const snapshot = demoAssetState.trash_relationships[item.id]; refreshed.stack = cloneStack(snapshot?.stack ?? null); demoAssetState.assets.push(refreshed);
    if (snapshot) {
      demoAssetState.album_assets.push(...snapshot.album_ids.filter((albumId) => demoAssetState.albums.some((album) => album.id === albumId)).map((album_id) => ({ album_id, asset_id: item.id })));
      demoAssetState.tag_assets.push(...snapshot.tag_ids.filter((tagId) => demoAssetState.tags.some((tag) => tag.id === tagId)).map((tag_id) => ({ tag_id, asset_id: item.id })));
      delete demoAssetState.trash_relationships[item.id];
    }
  }
  refreshRelationshipSummaries(); persist();
}
