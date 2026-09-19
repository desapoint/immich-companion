import type {
  DemoAlbumAssetRecord, DemoAlbumRecord, DemoAssetRecord, DemoAssetStackSnapshot, DemoAssetTagSnapshot, DemoTagAssetRecord, DemoTagRecord, DemoTrashApiAsset, DemoTrashRelationshipSnapshot,
} from "./demoAssetTypes";

export const STORAGE_KEY = 'immichCompanionV2DemoAssetState.v4';
export const PREVIOUS_STORAGE_KEY = 'immichCompanionV2DemoAssetState.v3';
export const LEGACY_STORAGE_KEYS = ['immichCompanionV2DemoAssetState.v1', 'immichCompanionV2DemoAssetState.v2'];
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

export function newDemoId(kind: string): string {
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

export function tagValueForPath(path: string): string {
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

export const BASE_ALBUMS = seedAlbums();
export const BASE_TAGS = seedTags();

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

export const baseAssetsById = new Map<string, DemoAssetRecord>(Array.from({ length: TOTAL_DEMO_ASSET_COUNT }, (_, index) => {
  const asset = buildAsset(index);
  return [asset.id, asset] as const;
}));

function initialTrashIds(): Set<string> {
  return new Set(Array.from({ length: INITIAL_TRASH_COUNT }, (_, offset) => uuidFor(INDEXED_ASSET_COUNT + offset + 1)));
}
export const BASE_TRASH_IDS = initialTrashIds();

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

export const BASE_TAG_ASSETS = seedTagMemberships();
export const BASE_ALBUM_ASSETS = seedAlbumMemberships();
export const BASE_STACKS = seedStacks();

function cloneTag(tag: DemoTagRecord): DemoTagRecord { return { ...tag }; }
function cloneAlbum(album: DemoAlbumRecord): DemoAlbumRecord { return { ...album }; }
export function cloneStack(stack: DemoAssetStackSnapshot | null): DemoAssetStackSnapshot | null { return stack ? { ...stack, assets: [...stack.assets] } : null; }
export function cloneAsset(asset: DemoAssetRecord): DemoAssetRecord { return { ...asset, tags: asset.tags.map((tag) => ({ ...tag })), stack: cloneStack(asset.stack) }; }
function tagSnapshot(tag: DemoTagRecord): DemoAssetTagSnapshot { return { id: tag.id, name: tag.tag_name, value: tag.tag_value, color: tag.color }; }

export function applyRelationships(
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

export function toTrashApiAsset(asset: DemoAssetRecord): DemoTrashApiAsset {
  return { id: asset.id, type: asset.asset_type, original_file_name: asset.original_file_name, original_mime_type: asset.original_mime_type, width: asset.width, height: asset.height, duration: asset.duration, taken_at: asset.file_created_at, file_modified_at: asset.file_modified_at, is_favorite: asset.is_favorite, is_archived: asset.is_archived, restore_path: asset.original_path };
}

export function buildState(
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
