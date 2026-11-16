import { fetchJson } from '../api/http';
import type { ArtistRef, CatalogTrack } from '../api/types';

export type ResolvedArtist = {
  id: number;
  name: string;
  cover_url?: string | null;
};

export type ArtistChipItem = {
  id: number | null;
  name: string;
  cover_url: string | null;
};

const hydratedArtistsCache = new Map<string, ArtistRef[]>();
const artistByIdCache = new Map<number, ArtistRef>();

export function parseArtistIdFromHref(href: string | null | undefined): number | null {
  if (!href) return null;
  const queryMatch = /[?&]artistId=(\d+)/i.exec(href);
  if (queryMatch) {
    const n = Number(queryMatch[1]);
    if (Number.isFinite(n) && n > 0) return n;
  }
  const pathMatch = /\/artist\/(\d+)(?:[/?#]|$)/i.exec(href);
  if (pathMatch) {
    const n = Number(pathMatch[1]);
    if (Number.isFinite(n) && n > 0) return n;
  }
  return null;
}

function positiveId(value: number | null | undefined): number | null {
  if (value == null) return null;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function rememberArtistCover(id: number | null, name: string, coverUrl: string | null | undefined): string | null {
  if (id != null && coverUrl) {
    artistByIdCache.set(id, { id, name: name || 'Исполнитель', cover_url: coverUrl });
    return coverUrl;
  }
  if (id != null) {
    return artistByIdCache.get(id)?.cover_url ?? null;
  }
  return coverUrl ?? null;
}

export function extractValidArtists(refs: ArtistRef[] | undefined): ResolvedArtist[] {
  if (!refs || refs.length === 0) return [];
  const seen = new Set<number>();
  const result: ResolvedArtist[] = [];
  for (const item of refs) {
    const id = positiveId(item.id);
    if (id == null || seen.has(id)) continue;
    seen.add(id);
    const cleanName = item.name.trim() || 'Исполнитель';
    result.push({
      id,
      name: cleanName,
      cover_url: rememberArtistCover(id, cleanName, item.cover_url),
    });
  }
  return result;
}

function allHaveNumericIds(refs: ArtistRef[] | undefined): boolean {
  return Boolean(
    refs
      && refs.length > 0
      && refs.every((item) => positiveId(item.id) != null),
  );
}

export function buildInitialArtistChips(track: CatalogTrack | null): ArtistChipItem[] {
  if (!track) return [];
  const fromRefs: ArtistChipItem[] = [];
  if (track.artists && track.artists.length > 0) {
    const seen = new Set<string>();
    for (const ref of track.artists) {
      const name = (ref.name || '').trim();
      const id = positiveId(ref.id);
      if (!name && id == null) continue;
      const key = id != null ? `id:${id}` : `name:${name.toLowerCase()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const cleanName = name || 'Исполнитель';
      fromRefs.push({
        id,
        name: cleanName,
        cover_url: rememberArtistCover(id, cleanName, ref.cover_url),
      });
    }
    if (fromRefs.length > 0) return fromRefs;
  }

  const rawLine = (track.artist || '').trim();
  if (!rawLine || rawLine === '—') return [];
  const seenNames = new Set<string>();
  const split: ArtistChipItem[] = [];
  for (const part of rawLine.split(',')) {
    const name = part.trim();
    if (!name) continue;
    const key = name.toLowerCase();
    if (seenNames.has(key)) continue;
    seenNames.add(key);
    split.push({ id: null, name, cover_url: null });
  }
  return split;
}

function mergeArtistChips(initial: ArtistChipItem[], fetched: ArtistRef[]): ArtistChipItem[] {
  const cleanedFetched: ArtistChipItem[] = [];
  const seen = new Set<string>();
  for (const item of fetched) {
    const id = positiveId(item.id);
    const name = (item.name || '').trim();
    if (!name && id == null) continue;
    const key = id != null ? `id:${id}` : `name:${name.toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const cleanName = name || 'Исполнитель';
    cleanedFetched.push({
      id,
      name: cleanName,
      cover_url: rememberArtistCover(id, cleanName, item.cover_url),
    });
  }
  if (cleanedFetched.length === 0) return initial;
  if (initial.length === 0) return cleanedFetched;

  const matchedInitialIndices = new Set<number>();
  const merged = cleanedFetched.map((item) => {
    const matchIdx = initial.findIndex(
      (orig) =>
        (orig.id != null && item.id != null && orig.id === item.id)
        || orig.name.toLowerCase() === item.name.toLowerCase(),
    );
    const match = matchIdx >= 0 ? initial[matchIdx] : undefined;
    if (matchIdx >= 0) matchedInitialIndices.add(matchIdx);
    return {
      id: item.id ?? match?.id ?? null,
      name: item.name || match?.name || 'Исполнитель',
      cover_url: item.cover_url || match?.cover_url || null,
    };
  });

  for (let i = 0; i < initial.length; i += 1) {
    if (!matchedInitialIndices.has(i)) {
      merged.push(initial[i]);
    }
  }
  return merged;
}

function cacheKeyForTrack(options: {
  trackId?: number | null;
  title?: string;
  artist?: string;
}): string {
  const tid = positiveId(options.trackId);
  if (tid != null) return `tid:${tid}`;
  const t = (options.title || '').trim().toLowerCase();
  const a = (options.artist || '').trim().toLowerCase();
  return t || a ? `qa:${t}|${a}` : '';
}

export async function fetchArtistsByIds(ids: number[]): Promise<ArtistRef[]> {
  const uniqueIds: number[] = [];
  const seen = new Set<number>();
  for (const raw of ids) {
    const id = positiveId(raw);
    if (id == null || seen.has(id)) continue;
    seen.add(id);
    uniqueIds.push(id);
  }
  if (uniqueIds.length === 0) return [];

  const missing = uniqueIds.filter((id) => {
    const cached = artistByIdCache.get(id);
    return !cached || !cached.cover_url;
  });

  if (missing.length > 0) {
    try {
      const res = await fetchJson<{ artists: ArtistRef[] }>(
        `/api/library/artists?ids=${missing.join(',')}`,
        'Не удалось загрузить исполнителей',
      );
      if (Array.isArray(res.artists)) {
        for (const item of res.artists) {
          const id = positiveId(item.id);
          if (id != null && item.name) {
            artistByIdCache.set(id, {
              id,
              name: item.name.trim() || 'Исполнитель',
              cover_url: item.cover_url ?? null,
            });
          }
        }
      }
    } catch {
      // Ignore network failure during avatar hydration
    }
  }

  const results: ArtistRef[] = [];
  for (const id of uniqueIds) {
    const cached = artistByIdCache.get(id);
    if (cached) results.push(cached);
  }
  return results;
}

async function backfillCoversByIds(refs: ArtistRef[]): Promise<ArtistRef[]> {
  const missingIds: number[] = [];
  for (const ref of refs) {
    const id = positiveId(ref.id);
    if (id != null && !ref.cover_url) {
      missingIds.push(id);
    }
  }
  if (missingIds.length === 0) return refs;
  const fetched = await fetchArtistsByIds(missingIds);
  if (fetched.length === 0) return refs;
  const coverMap = new Map<number, string>();
  for (const item of fetched) {
    const id = positiveId(item.id);
    if (id != null && item.cover_url) {
      coverMap.set(id, item.cover_url);
    }
  }
  if (coverMap.size === 0) return refs;
  return refs.map((ref) => {
    const id = positiveId(ref.id);
    const cover = id != null ? coverMap.get(id) : undefined;
    return cover && !ref.cover_url ? { ...ref, cover_url: cover } : ref;
  });
}

function hasCompleteCovers(refs: ArtistRef[]): boolean {
  return (
    refs.length > 0
    && refs.every((item) => positiveId(item.id) != null && Boolean(item.cover_url))
  );
}

export async function fetchHydratedArtistRefs(options: {
  trackId?: number | null;
  title?: string;
  artist?: string;
}): Promise<ArtistRef[]> {
  const key = cacheKeyForTrack(options);
  if (key && hydratedArtistsCache.has(key)) {
    const cached = hydratedArtistsCache.get(key) ?? [];
    if (hasCompleteCovers(cached)) {
      return cached;
    }
  }

  const tid = positiveId(options.trackId);
  if (tid != null) {
    try {
      const res = await fetchJson<{ artists: ArtistRef[] }>(
        `/api/library/track/${tid}/artists`,
        'Не удалось определить исполнителя',
      );
      if (Array.isArray(res.artists) && res.artists.length > 0) {
        const enriched = await backfillCoversByIds(res.artists);
        if (key && hasCompleteCovers(enriched)) {
          hydratedArtistsCache.set(key, enriched);
        }
        return enriched;
      }
    } catch {
      // Fall through to resolve-artist
    }
  }

  const title = (options.title ?? '').trim();
  const artist = (options.artist ?? '').trim();
  if (title || artist) {
    try {
      const res = await fetchJson<{ artists: ArtistRef[] }>(
        `/api/library/resolve-artist?title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}`,
        'Не удалось определить исполнителя',
      );
      if (Array.isArray(res.artists) && res.artists.length > 0) {
        const enriched = await backfillCoversByIds(res.artists);
        if (key && hasCompleteCovers(enriched)) {
          hydratedArtistsCache.set(key, enriched);
        }
        return enriched;
      }
    } catch {
      // Ignore network failure during background hydration
    }
  }

  return [];
}

export async function hydrateArtistChipsForTrack(
  track: CatalogTrack,
  initial: ArtistChipItem[],
): Promise<ArtistChipItem[]> {
  const allHaveIds = initial.length > 0 && initial.every((chip) => chip.id != null && chip.id > 0);
  if (allHaveIds) {
    const missingCoverIds = initial
      .filter((chip) => chip.id != null && !chip.cover_url)
      .map((chip) => chip.id as number);
    if (missingCoverIds.length === 0) return initial;
    const byIds = await fetchArtistsByIds(missingCoverIds);
    const coverById = new Map<number, ArtistRef>();
    for (const item of byIds) {
      const id = positiveId(item.id);
      if (id != null) coverById.set(id, item);
    }
    return initial.map((chip) => {
      const found = chip.id != null ? coverById.get(chip.id) : undefined;
      if (!found) return chip;
      return {
        id: chip.id,
        name: chip.name || found.name || 'Исполнитель',
        cover_url: chip.cover_url || found.cover_url || null,
      };
    });
  }

  const fetched = await fetchHydratedArtistRefs({
    trackId: track.id,
    title: track.title,
    artist: track.artist,
  });
  return mergeArtistChips(initial, fetched);
}

export async function resolveArtistChipClick(
  chip: ArtistChipItem,
  track: CatalogTrack,
): Promise<ResolvedArtist | null> {
  if (chip.id != null && chip.id > 0) {
    return { id: chip.id, name: chip.name, cover_url: chip.cover_url };
  }

  const refs = await fetchHydratedArtistRefs({
    trackId: track.id,
    title: track.title,
    artist: track.artist,
  });
  const valid = extractValidArtists(refs);
  const wanted = chip.name.trim().toLowerCase();
  const exact = valid.find((item) => item.name.toLowerCase() === wanted);
  if (exact) return exact;
  const partialMatch = valid.find(
    (item) =>
      wanted.length > 0
      && (item.name.toLowerCase().includes(wanted) || wanted.includes(item.name.toLowerCase())),
  );
  if (partialMatch) return partialMatch;

  if (chip.name.trim()) {
    try {
      const res = await fetchJson<{ artists: ArtistRef[] }>(
        `/api/library/resolve-artist?title=&artist=${encodeURIComponent(chip.name.trim())}`,
        'Не удалось определить исполнителя',
      );
      const byName = extractValidArtists(res.artists);
      if (byName.length > 0) return byName[0];
    } catch {
      // Ignore fallback error
    }
  }

  return valid[0] ?? null;
}

export async function resolveArtistsForTrack(options: {
  artists?: ArtistRef[];
  trackId?: number | null;
  title?: string;
  artist?: string;
}): Promise<ResolvedArtist[]> {
  if (allHaveNumericIds(options.artists)) {
    return extractValidArtists(options.artists);
  }

  const partial = extractValidArtists(options.artists);
  const fetched = await fetchHydratedArtistRefs({
    trackId: options.trackId,
    title: options.title,
    artist: options.artist,
  });
  const validFetched = extractValidArtists(fetched);
  if (validFetched.length > 0) return validFetched;

  return partial;
}

export async function resolveArtistsForPlayer(options: {
  artists: ArtistRef[];
  artistHref: string | null;
  title: string;
  artist: string;
}): Promise<ResolvedArtist[]> {
  const cleanTitle = options.title === '—' ? '' : options.title.trim();
  const cleanArtist = options.artist === '—' ? '' : options.artist.trim();

  if (allHaveNumericIds(options.artists)) {
    return extractValidArtists(options.artists);
  }

  const hrefId = parseArtistIdFromHref(options.artistHref);
  if (options.artists.length <= 1 && hrefId != null) {
    return [
      {
        id: hrefId,
        name: options.artists[0]?.name?.trim() || cleanArtist || 'Исполнитель',
        cover_url: options.artists[0]?.cover_url ?? null,
      },
    ];
  }

  const partial = extractValidArtists(options.artists);
  if (partial.length === 0 && hrefId != null) {
    partial.push({
      id: hrefId,
      name: cleanArtist || 'Исполнитель',
    });
  }

  if (cleanTitle || cleanArtist) {
    const fetched = await fetchHydratedArtistRefs({
      title: cleanTitle,
      artist: cleanArtist,
    });
    const fromSearch = extractValidArtists(fetched);
    if (fromSearch.length > 0) return fromSearch;
  }

  return partial;
}
