import type { AssetRecord, DuplicateGroupRecord, LibraryDataSource, PageResult, TrashAssetRecord } from '../contracts';

const RAW_EXTENSIONS = ['dng', 'nef', 'cr3', 'arw', 'raf'] as const;

function ordinal(id: string): number {
  const tail = id.match(/-([0-9a-f]{12})$/i)?.[1];
  return tail ? Number.parseInt(tail, 16) : 0;
}

function replaceExtension(name: string, extension: string): string {
  return `${name.replace(/\.[^.]+$/, '')}.${extension}`;
}

function profileAsset(asset: AssetRecord): AssetRecord {
  const index = Math.max(0, ordinal(asset.id) - 1);
  if (asset.asset_type === 'VIDEO') {
    const variant = Math.floor(index / 11) % 4;
    if (variant === 1) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mov'), original_mime_type: 'video/quicktime; codecs=hvc1' };
    if (variant === 2) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'webm'), original_mime_type: 'video/webm; codecs=vp9' };
    if (variant === 3) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mkv'), original_mime_type: 'video/x-matroska; codecs=av01' };
    return { ...asset, original_mime_type: 'video/mp4; codecs=avc1.42E01E' };
  }

  if (asset.asset_type === 'IMAGE') {
    if (index % 29 === 7) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'heic'), original_mime_type: 'image/heic' };
    if (index % 31 === 9) {
      const ext = RAW_EXTENSIONS[Math.floor(index / 31) % RAW_EXTENSIONS.length];
      const mime = ext === 'dng' ? 'image/x-adobe-dng' : `image/x-${ext}`;
      return { ...asset, original_file_name: replaceExtension(asset.original_file_name, ext), original_mime_type: mime };
    }
    if (index % 37 === 13) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'avif'), original_mime_type: 'image/avif' };
  }
  return asset;
}

function profileTrash(asset: TrashAssetRecord): TrashAssetRecord {
  const index = Math.max(0, ordinal(asset.id) - 1);
  if (asset.type === 'VIDEO') {
    const variant = Math.floor(index / 11) % 4;
    if (variant === 1) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mov'), original_mime_type: 'video/quicktime; codecs=hvc1' };
    if (variant === 2) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'webm'), original_mime_type: 'video/webm; codecs=vp9' };
    if (variant === 3) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mkv'), original_mime_type: 'video/x-matroska; codecs=av01' };
  } else if (asset.type === 'IMAGE') {
    if (index % 29 === 7) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'heic'), original_mime_type: 'image/heic' };
    if (index % 31 === 9) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'dng'), original_mime_type: 'image/x-adobe-dng' };
  }
  return asset;
}

function profilePage<T>(page: PageResult<T>, map: (item: T) => T): PageResult<T> {
  return { ...page, items: page.items.map(map) };
}

function profileDuplicateGroup(group: DuplicateGroupRecord): DuplicateGroupRecord {
  return { ...group, members: group.members.map((member) => ({ ...member, asset: profileAsset(member.asset) })) };
}

export function withDemoMediaProfiles(source: LibraryDataSource): LibraryDataSource {
  return {
    ...source,
    assets: {
      ...source.assets,
      async getById(id) { const asset = await source.assets.getById(id); return asset ? profileAsset(asset) : undefined; },
      async getMany(ids) { return (await source.assets.getMany(ids)).map(profileAsset); },
      async getTrashById(id) { const asset = await source.assets.getTrashById(id); return asset ? profileTrash(asset) : undefined; },
      async search(query) { return profilePage(await source.assets.search(query), profileAsset); },
      async searchTrash(query) { return profilePage(await source.assets.searchTrash(query), profileTrash); },
    },
    duplicates: {
      ...source.duplicates,
      async search(query) { return profilePage(await source.duplicates.search(query), profileDuplicateGroup); },
    },
  };
}
