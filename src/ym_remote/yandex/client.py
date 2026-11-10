from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
import re
import time
from dataclasses import dataclass, replace

from ym_remote.models.music import (
    Album,
    Artist,
    ArtistDetail,
    Cover,
    FamiliarTracks,
    Track,
    TrackPage,
)
from ym_remote.yandex.map import (
    _field,
    album_from_api,
    artist_from_api,
    as_int,
    playlist_from_api,
    track_from_api,
    uri_of,
)

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 45.0
_FAMILIAR_TRACKS_LIMIT = 200
_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_TRAILING_VERSION_RE = re.compile(r"(?:\s*[\(\[][^\)\]]+[\)\]])+\s*$")


def _parse_hex_rgb(value) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _HEX_COLOR_RE.match(value.strip())
    if not match:
        return None
    raw = match.group(1)
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _format_hex_rgb(rgb: tuple[int, int, int]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _extract_ambient_color(artist_obj, all_covers=()) -> str | None:
    derived_sources = [
        _field(artist_obj, "derived_colors", "derivedColors"),
        _field(_field(artist_obj, "cover"), "derived_colors", "derivedColors"),
    ]
    for cov in all_covers or ():
        derived_sources.append(_field(cov, "derived_colors", "derivedColors"))

    for derived in derived_sources:
        if derived is None:
            continue
        avg = _parse_hex_rgb(_field(derived, "average"))
        accent = _parse_hex_rgb(_field(derived, "accent"))
        mini = _parse_hex_rgb(_field(derived, "mini_player", "miniPlayer"))
        if avg is not None:
            secondary = accent or mini
            if max(avg) < 52 and secondary is not None and max(secondary) > max(avg):
                blended = tuple(
                    avg[i] * 0.74 + secondary[i] * 0.26 for i in range(3)
                )
                return _format_hex_rgb(blended)  # type: ignore[arg-type]
            return _format_hex_rgb(avg)
        if accent is not None:
            return _format_hex_rgb(accent)
        if mini is not None:
            return _format_hex_rgb(mini)

    color_sources = [_field(_field(artist_obj, "cover"), "color")]
    for cov in all_covers or ():
        color_sources.append(_field(cov, "color"))
    for raw_color in color_sources:
        parsed = _parse_hex_rgb(raw_color)
        if parsed is not None:
            return _format_hex_rgb(parsed)
    return None


def _strip_title_version(title: str) -> str:
    stripped = _TRAILING_VERSION_RE.sub("", title).strip()
    return stripped or title.strip()


@dataclass(frozen=True)
class _FamiliarState:
    collection_keys: tuple[str | int, ...] = ()
    wave_keys: tuple[str | int, ...] = ()
    collection_tracks: tuple[Track, ...] | None = ()
    wave_tracks: tuple[Track, ...] | None = ()

    @property
    def total(self) -> int:
        unique_ids: set[int] = set()
        extra = 0
        for key in (*self.collection_keys, *self.wave_keys):
            tid, _ = _parse_id_pair(key)
            if tid is not None:
                unique_ids.add(tid)
            else:
                extra += 1
        return len(unique_ids) + extra


def _is_not_found(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name == "NotFoundError":
        return True
    if name == "BadRequestError":
        text = str(exc).lower()
        return "not-found" in text or "not found" in text
    return False


def _parse_id_pair(raw) -> tuple[int | None, int | None]:
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw, None
    if isinstance(raw, str):
        if ":" in raw:
            left, _, right = raw.partition(":")
            return as_int(left.strip()), as_int(right.strip())
        return as_int(raw.strip()), None
    return None, None


def _familiar_blocks(blocks) -> list:
    found = []
    for block in blocks or []:
        if _field(block, "type") == "FAMILIAR_YOU":
            found.append(block)
        data = _field(block, "data")
        for tab in _field(data, "tabs") or []:
            found.extend(_familiar_blocks(_field(tab, "blocks")))
    return found


def _item_track_id(item) -> int | None:
    if isinstance(item, bool):
        return None
    if isinstance(item, (int, str)):
        tid, _ = _parse_id_pair(item)
        return tid
    inner = _field(item, "track") or item
    raw_id = _field(inner, "id", "track_id", "trackId")
    tid, _ = _parse_id_pair(raw_id)
    return tid if tid is not None else as_int(raw_id)


def _extract_section_tracks(node) -> list:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        tracks = node.get("tracks") or node.get("items") or node.get("entities")
        if isinstance(tracks, list):
            return tracks
    return []


def _extract_familiar_sections(payload) -> tuple[list, list, list]:
    if isinstance(payload, list):
        return [], [], payload
    if not isinstance(payload, dict):
        return [], [], []
    for container in (
        payload,
        payload.get("familiar_you"),
        payload.get("familiarYou"),
        payload.get("data"),
        payload.get("result"),
    ):
        if not isinstance(container, dict):
            continue
        col_items: list = []
        col_items.extend(_extract_section_tracks(container.get("collection")))
        for sub_key in ("collection_tracks", "collectionTracks"):
            part = container.get(sub_key)
            if isinstance(part, list):
                col_items.extend(part)

        wave_items: list = []
        for node_key in ("wave", "vibe"):
            wave_items.extend(_extract_section_tracks(container.get(node_key)))
        for sub_key in ("wave_tracks", "waveTracks", "vibe_tracks", "vibeTracks"):
            part = container.get(sub_key)
            if isinstance(part, list):
                wave_items.extend(part)

        if col_items or wave_items:
            return col_items, wave_items, []

        direct = container.get("tracks") or container.get("items") or container.get("entities")
        if isinstance(direct, list) and direct:
            return [], [], direct
    return [], [], []


def _parse_familiar_items(
    items: list, *, exclude_ids: set[int] | None = None
) -> tuple[tuple[str | int, ...], tuple[Track, ...] | None, set[int]]:
    keys: list[str | int] = []
    parsed_tracks: list[Track] = []
    all_have_titles = True
    seen_ids: set[int] = set()
    excluded = exclude_ids or set()

    for item in items:
        if isinstance(item, (int, str)) and not isinstance(item, bool):
            tid, aid = _parse_id_pair(item)
            if tid is None or tid in seen_ids or tid in excluded:
                continue
            seen_ids.add(tid)
            keys.append(f"{tid}:{aid}" if aid is not None else tid)
            all_have_titles = False
            continue
        inner = _field(item, "track") or item
        raw_id = _field(inner, "id", "track_id", "trackId")
        tid, embedded_aid = _parse_id_pair(raw_id)
        if tid is None:
            tid = as_int(raw_id)
        aid = embedded_aid or as_int(_field(item, "album_id", "albumId")) or as_int(
            _field(inner, "album_id", "albumId")
        )
        if tid is None or tid in seen_ids or tid in excluded:
            continue
        seen_ids.add(tid)
        if _field(inner, "title"):
            mapped = track_from_api(
                inner, fallback_album_id=aid, index=len(parsed_tracks)
            )
            effective_aid = mapped.album_id() or aid
            keys.append(f"{tid}:{effective_aid}" if effective_aid is not None else tid)
            parsed_tracks.append(mapped)
        else:
            keys.append(f"{tid}:{aid}" if aid is not None else tid)
            all_have_titles = False

    if not keys:
        return (), (), set()
    tracks_tuple = (
        tuple(parsed_tracks)
        if all_have_titles and len(parsed_tracks) == len(keys)
        else None
    )
    return tuple(keys), tracks_tuple, seen_ids


def _materialize_tracks(
    keys: tuple[str | int, ...],
    fetched_by_id: dict[int, Track],
    *,
    exclude_ids: set[int] | None = None,
) -> tuple[Track, ...]:
    ordered: list[Track] = []
    seen: set[int] = set()
    excluded = exclude_ids or set()
    for key in keys:
        tid, aid = _parse_id_pair(key)
        if tid is None or tid in seen or tid in excluded:
            continue
        track = fetched_by_id.get(tid)
        if track is None:
            continue
        seen.add(tid)
        if track.album_id() is None and aid is not None:
            track = replace(track, albums=(Album(id=aid, title=""),) + track.albums)
        ordered.append(replace(track, playlist_index=len(ordered)))
    return tuple(ordered)


class YandexLibrary:
    """Асинхронный клиент yandex-music. В очередь CDP не входит."""

    def __init__(self, token: str) -> None:
        self.token = token
        self._client = None
        self.ready = False
        self.uid: int | None = None
        self._familiar_cache: dict[int, tuple[float, _FamiliarState]] = {}
        self._likes_ids_cache: tuple[float, tuple[tuple[int, int | None], ...]] | None = None

    async def start(self) -> None:
        if not self.token:
            self.ready = False
            return
        try:
            from yandex_music import ClientAsync

            client = ClientAsync(self.token)
            init = getattr(client, "init", None)
            if init is not None:
                await init()
            self._client = client
            self.uid = self._read_uid(client)
            self.ready = True
        except Exception:
            logger.exception("Yandex Music API client was not created")
            self.ready = False
            self._client = None

    async def close(self) -> None:
        client = self._client
        self._client = None
        self.ready = False
        self._familiar_cache.clear()
        self._likes_ids_cache = None
        if client is None:
            return
        for owner in (getattr(client, "_request", None), getattr(client, "request", None), client):
            if owner is None:
                continue
            for name in ("close", "aclose"):
                closer = getattr(owner, name, None)
                if closer is None:
                    continue
                try:
                    result = closer()
                    if hasattr(result, "__await__"):
                        await result
                    return
                except Exception:
                    logger.debug("api client close failed", exc_info=True)

    async def like_tracks(self, limit: int = 12) -> tuple[tuple[Track, ...], int]:
        client = self._require()
        likes = await client.users_likes_tracks(self.uid)
        shorts = list(getattr(likes, "tracks", None) or [])
        preview = await self._from_shorts(shorts[:limit], indexed=False)
        return preview, len(shorts)

    async def playlists(self):
        client = self._require()
        raw = await client.users_playlists_list(self.uid)
        return tuple(playlist_from_api(item) for item in list(raw or []))

    async def playlist(self, kind: int):
        client = self._require()
        raw = await client.users_playlists(kind, self.uid)
        if isinstance(raw, list):
            if not raw:
                return None
            raw = raw[0]
        if raw is None:
            return None
        shorts = list(getattr(raw, "tracks", None) or [])
        tracks = await self._from_shorts(shorts, indexed=True)
        return playlist_from_api(raw, tracks)

    async def playlist_summary(self, kind: int):
        """Uid, uuid, обложка и полный track_count без загрузки каждого трека."""
        client = self._require()
        raw = await client.users_playlists(kind, self.uid)
        if isinstance(raw, list):
            if not raw:
                return None
            raw = raw[0]
        if raw is None:
            return None
        shorts = list(getattr(raw, "tracks", None) or [])
        summary = playlist_from_api(raw)
        declared = as_int(getattr(raw, "track_count", None))
        count = declared if declared else len(shorts)
        if summary.track_count != count:
            summary = replace(summary, track_count=count)
        return summary

    async def first_album_id(self, track_id: int) -> int | None:
        client = self._require()
        found = await client.tracks([track_id])
        if not found:
            return None
        return track_from_api(found[0]).album_id()

    async def artist_detail(self, artist_id: int) -> ArtistDetail | None:
        client = self._require()
        brief_res, familiar_res = await asyncio.gather(
            client.artists_brief_info(artist_id),
            self._artist_familiar_state(artist_id),
            return_exceptions=True,
        )
        if isinstance(brief_res, BaseException):
            if _is_not_found(brief_res):
                return None
            raise brief_res
        brief = brief_res
        if brief is None:
            return None
        artist_obj = getattr(brief, "artist", None)
        if artist_obj is None:
            return None
        if getattr(artist_obj, "error", None) and not getattr(artist_obj, "name", None):
            return None

        all_covers = list(getattr(brief, "all_covers", None) or [])
        mapped_artist = artist_from_api(artist_obj, fallback_covers=all_covers)
        if mapped_artist.cover is None:
            bg = uri_of(getattr(brief, "background_image_url", None))
            if bg:
                mapped_artist = replace(mapped_artist, cover=Cover(bg))

        resolved_id = mapped_artist.id if mapped_artist.id is not None else artist_id
        raw_popular = list(
            getattr(brief, "popular_tracks", None)
            or getattr(artist_obj, "popular_tracks", None)
            or []
        )
        popular_tracks = tuple(
            track_from_api(item, index=index)
            for index, item in enumerate(raw_popular[:12])
        )

        if isinstance(familiar_res, BaseException):
            logger.debug("familiar lookup failed for artist %s", artist_id, exc_info=familiar_res)
            familiar_state = _FamiliarState()
        else:
            familiar_state = familiar_res
            if familiar_state.total == 0 and raw_popular:
                matched = await self._intersect_likes_with_popular(artist_id, raw_popular)
                if matched:
                    familiar_state = _FamiliarState(
                        collection_keys=matched,
                        wave_keys=(),
                        collection_tracks=None,
                        wave_tracks=(),
                    )

        counts = getattr(artist_obj, "counts", None)
        direct_albums_count = as_int(_field(counts, "direct_albums")) or 0
        raw_albums = list(getattr(brief, "albums", None) or [])
        if not raw_albums and direct_albums_count > 0 and hasattr(client, "artists_direct_albums"):
            try:
                direct = await client.artists_direct_albums(
                    artist_id, page=0, page_size=30, sort_by="year"
                )
                raw_albums = list(getattr(direct, "albums", None) or [])
            except Exception:
                logger.debug("direct albums lookup failed for %s", artist_id, exc_info=True)

        albums: list[Album] = []
        singles: list[Album] = []
        seen_albums: set[int] = set()
        fallback_artist_tuple = (
            (Artist(name=mapped_artist.name, id=resolved_id, cover=mapped_artist.cover),)
            if mapped_artist.name
            else ()
        )
        for raw_album in raw_albums:
            mapped_album = album_from_api(raw_album)
            if mapped_album.id is None or mapped_album.id in seen_albums:
                continue
            seen_albums.add(mapped_album.id)
            if not mapped_album.artists and fallback_artist_tuple:
                mapped_album = replace(mapped_album, artists=fallback_artist_tuple)
            if mapped_album.album_type == "single":
                singles.append(mapped_album)
            else:
                albums.append(mapped_album)

        total_tracks = as_int(_field(counts, "tracks"))
        if not total_tracks:
            total_tracks = len(popular_tracks)
        total_albums = direct_albums_count if direct_albums_count > 0 else (len(albums) + len(singles))

        ambient_color = _extract_ambient_color(artist_obj, all_covers)
        return ArtistDetail(
            id=resolved_id,
            name=mapped_artist.name,
            cover=mapped_artist.cover,
            ambient_color=ambient_color,
            total_tracks=total_tracks,
            total_albums=total_albums,
            popular_tracks=popular_tracks,
            familiar_total=familiar_state.total,
            albums=tuple(albums),
            singles=tuple(singles),
        )

    async def artist_tracks(
        self, artist_id: int, page: int = 0, page_size: int = 50
    ) -> TrackPage:
        client = self._require()
        page = max(0, int(page))
        page_size = max(1, min(100, int(page_size)))
        try:
            raw = await client.artists_tracks(artist_id, page=page, page_size=page_size)
        except Exception as exc:
            if _is_not_found(exc):
                return TrackPage(tracks=(), page=page, page_size=page_size, total=0, has_more=False)
            raise
        if raw is None:
            return TrackPage(tracks=(), page=page, page_size=page_size, total=0, has_more=False)
        items = list(getattr(raw, "tracks", None) or [])
        offset = page * page_size
        tracks = tuple(
            track_from_api(item, index=offset + index)
            for index, item in enumerate(items)
        )
        pager = getattr(raw, "pager", None)
        pager_total = as_int(_field(pager, "total")) if pager is not None else None
        if pager_total is not None:
            total = pager_total
            has_more = offset + len(tracks) < total
        else:
            total = offset + len(tracks)
            has_more = len(tracks) >= page_size
        return TrackPage(
            tracks=tracks,
            page=page,
            page_size=page_size,
            total=total,
            has_more=has_more,
        )

    async def artist_familiar(self, artist_id: int) -> FamiliarTracks:
        client = self._require()
        state = await self._artist_familiar_state(artist_id)
        col_tracks = state.collection_tracks
        wave_tracks = state.wave_tracks

        missing_keys: list[str | int] = []
        if col_tracks is None:
            missing_keys.extend(state.collection_keys)
        if wave_tracks is None:
            missing_keys.extend(state.wave_keys)

        if missing_keys:
            fetched_by_id: dict[int, Track] = {}
            for start in range(0, len(missing_keys), 100):
                chunk = missing_keys[start : start + 100]
                raw_tracks = await client.tracks(chunk)
                for raw_track in raw_tracks or ():
                    mapped = track_from_api(raw_track)
                    if mapped.id is not None and mapped.id not in fetched_by_id:
                        fetched_by_id[mapped.id] = mapped

            if col_tracks is None:
                col_tracks = _materialize_tracks(state.collection_keys, fetched_by_id)
            if wave_tracks is None:
                wave_tracks = _materialize_tracks(state.wave_keys, fetched_by_id)

            resolved_state = _FamiliarState(
                collection_keys=state.collection_keys,
                wave_keys=state.wave_keys,
                collection_tracks=col_tracks,
                wave_tracks=wave_tracks,
            )
            self._familiar_cache[artist_id] = (time.monotonic() + _CACHE_TTL_SEC, resolved_state)

        return FamiliarTracks(
            collection=col_tracks or (),
            wave=wave_tracks or (),
        )

    async def artist_familiar_tracks(self, artist_id: int) -> tuple[Track, ...]:
        familiar = await self.artist_familiar(artist_id)
        return tuple(
            replace(track, playlist_index=index)
            for index, track in enumerate(familiar.all_tracks())
        )

    async def album_with_tracks(self, album_id: int) -> Album | None:
        client = self._require()
        try:
            raw = await client.albums_with_tracks(album_id)
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise
        if raw is None:
            return None
        if getattr(raw, "error", None) and not getattr(raw, "title", None):
            return None
        return album_from_api(raw)

    async def artists_by_ids(self, artist_ids: Sequence[int]) -> tuple[Artist, ...]:
        client = self._require()
        clean_ids: list[int] = []
        seen: set[int] = set()
        for raw_id in artist_ids:
            aid = as_int(raw_id)
            if aid is None or aid <= 0 or aid in seen:
                continue
            seen.add(aid)
            clean_ids.append(aid)
            if len(clean_ids) >= 50:
                break
        if not clean_ids or not hasattr(client, "artists"):
            return ()
        try:
            raw_artists = await client.artists(clean_ids)
        except Exception as exc:
            if _is_not_found(exc):
                return ()
            raise
        by_id: dict[int, Artist] = {}
        for raw in raw_artists or ():
            mapped = artist_from_api(raw)
            if mapped.id is not None and mapped.name and mapped.id not in by_id:
                by_id[mapped.id] = mapped
        return tuple(by_id[aid] for aid in clean_ids if aid in by_id)

    async def _hydrate_missing_artist_covers(
        self, artists: tuple[Artist, ...]
    ) -> tuple[Artist, ...]:
        missing_ids = [
            artist.id
            for artist in artists
            if artist.id is not None and artist.id > 0 and artist.cover is None
        ]
        if not missing_ids:
            return artists
        try:
            fetched = await self.artists_by_ids(missing_ids)
        except Exception:
            logger.debug("artist cover hydration failed for %s", missing_ids, exc_info=True)
            return artists
        cover_by_id = {
            item.id: item.cover
            for item in fetched
            if item.id is not None and item.cover is not None
        }
        if not cover_by_id:
            return artists
        return tuple(
            replace(artist, cover=cover_by_id[artist.id])
            if artist.id in cover_by_id and artist.cover is None
            else artist
            for artist in artists
        )

    async def track_artists(self, track_id: int) -> tuple[Artist, ...]:
        client = self._require()
        try:
            found = await client.tracks([track_id])
        except Exception as exc:
            if _is_not_found(exc):
                return ()
            raise
        if not found:
            return ()
        artists = track_from_api(found[0]).artists
        return await self._hydrate_missing_artist_covers(artists)

    async def search_artists(self, query: str, limit: int = 6) -> tuple[Artist, ...]:
        client = self._require()
        cleaned = (query or "").strip()
        if not cleaned:
            return ()
        res = await client.search(cleaned, type_="all")
        if res is None:
            return ()
        candidates = []
        best = getattr(res, "best", None)
        if best is not None and _field(best, "type") == "artist":
            best_result = _field(best, "result")
            if best_result is not None:
                candidates.append(best_result)
        artists_block = getattr(res, "artists", None)
        for item in _field(artists_block, "results") or []:
            candidates.append(item)

        found: list[Artist] = []
        seen: set[int] = set()
        for raw in candidates:
            artist = artist_from_api(raw)
            if artist.id is None or not artist.name or artist.id in seen:
                continue
            seen.add(artist.id)
            found.append(artist)
            if len(found) >= limit:
                break
        return tuple(found)

    async def _fill_missing_artist_parts(
        self, existing: tuple[Artist, ...], parts: list[str]
    ) -> tuple[Artist, ...]:
        if len(parts) <= 1:
            return existing
        resolved = list(existing)
        seen_ids = {a.id for a in resolved if a.id is not None}
        for part in parts:
            part_cf = part.casefold()
            already_present = any(
                part_cf == a.name.strip().casefold()
                or part_cf in a.name.casefold()
                or a.name.casefold() in part_cf
                for a in resolved
            )
            if already_present:
                continue
            part_hits = await self.search_artists(part, limit=3)
            chosen = next(
                (a for a in part_hits if a.name.strip().casefold() == part_cf),
                part_hits[0] if part_hits else None,
            )
            if chosen is not None and chosen.id is not None and chosen.id not in seen_ids:
                seen_ids.add(chosen.id)
                resolved.append(chosen)
        return tuple(resolved)

    async def resolve_artists(self, title: str, artist_line: str) -> tuple[Artist, ...]:
        client = self._require()
        clean_title = (title or "").strip()
        clean_artist = (artist_line or "").strip()
        if not clean_title and not clean_artist:
            return ()

        parts = [part.strip() for part in clean_artist.split(",") if part.strip()]

        if clean_title:
            search_query = f"{clean_artist} {clean_title}".strip()
            res = await client.search(search_query, type_="all")
            if res is not None:
                raw_tracks = []
                best = getattr(res, "best", None)
                if best is not None and _field(best, "type") == "track":
                    best_track = _field(best, "result")
                    if best_track is not None:
                        raw_tracks.append(best_track)
                tracks_block = getattr(res, "tracks", None)
                for item in _field(tracks_block, "results") or []:
                    raw_tracks.append(item)

                candidates: list[tuple[Track, str]] = []
                for item in raw_tracks:
                    mapped = track_from_api(item)
                    raw_ver = _field(item, "version")
                    ver_str = raw_ver.strip() if isinstance(raw_ver, str) and raw_ver.strip() else ""
                    with_ver = f"{mapped.title.strip()} ({ver_str})" if ver_str else mapped.title.strip()
                    candidates.append((mapped, with_ver))

                wanted_title = clean_title.casefold()
                stripped_wanted = _strip_title_version(clean_title).casefold()
                wanted_artist = clean_artist.casefold()

                def _exact_title(track: Track, with_ver: str) -> bool:
                    base = track.title.strip().casefold()
                    return base == wanted_title or with_ver.casefold() == wanted_title

                def _loose_title(track: Track, _with_ver: str) -> bool:
                    base_stripped = _strip_title_version(track.title).casefold()
                    return bool(stripped_wanted) and base_stripped == stripped_wanted

                for matcher in (_exact_title, _loose_title):
                    for track, with_ver in candidates:
                        if not matcher(track, with_ver):
                            continue
                        valid = tuple(a for a in track.artists if a.id is not None and a.name)
                        if not valid:
                            continue
                        if not wanted_artist or any(
                            a.name.casefold() in wanted_artist or wanted_artist in a.name.casefold()
                            for a in valid
                        ):
                            completed = await self._fill_missing_artist_parts(valid, parts)
                            return await self._hydrate_missing_artist_covers(completed)

                    for track, with_ver in candidates:
                        if not matcher(track, with_ver):
                            continue
                        valid = tuple(a for a in track.artists if a.id is not None and a.name)
                        if valid:
                            completed = await self._fill_missing_artist_parts(valid, parts)
                            return await self._hydrate_missing_artist_covers(completed)

        if not clean_artist:
            return ()

        direct = await self.search_artists(clean_artist, limit=6)
        wanted_artist = clean_artist.casefold()
        for candidate in direct:
            if candidate.name.strip().casefold() == wanted_artist:
                return await self._hydrate_missing_artist_covers((candidate,))

        if len(parts) > 1:
            resolved = await self._fill_missing_artist_parts((), parts)
            if resolved:
                return await self._hydrate_missing_artist_covers(resolved)

        fallback = direct[:1] if direct else ()
        return await self._hydrate_missing_artist_covers(fallback)

    async def _artist_familiar_state(self, artist_id: int) -> _FamiliarState:
        now = time.monotonic()
        cached = self._familiar_cache.get(artist_id)
        if cached is not None and now < cached[0]:
            return cached[1]

        state = await self._familiar_from_api(artist_id)
        if state.total == 0:
            like_keys = await self._familiar_from_likes(artist_id)
            if like_keys:
                state = _FamiliarState(
                    collection_keys=like_keys,
                    wave_keys=(),
                    collection_tracks=None,
                    wave_tracks=(),
                )

        self._familiar_cache[artist_id] = (time.monotonic() + _CACHE_TTL_SEC, state)
        return state

    async def _state_from_payload(self, payload) -> _FamiliarState:
        col_raw, wave_raw, flat_raw = _extract_familiar_sections(payload)
        if not col_raw and not wave_raw and flat_raw:
            liked_pairs = await self._liked_id_pairs()
            liked_ids = {tid for tid, _ in liked_pairs}
            for item in flat_raw:
                tid = _item_track_id(item)
                if tid is not None and tid in liked_ids:
                    col_raw.append(item)
                else:
                    wave_raw.append(item)
        if not col_raw and not wave_raw:
            return _FamiliarState()

        col_keys, col_tracks, _ = _parse_familiar_items(col_raw)
        wave_keys, wave_tracks, _ = _parse_familiar_items(wave_raw)
        return _FamiliarState(
            collection_keys=col_keys,
            wave_keys=wave_keys,
            collection_tracks=col_tracks,
            wave_tracks=wave_tracks,
        )

    async def _familiar_from_api(self, artist_id: int) -> _FamiliarState:
        client = self._require()
        req = getattr(client, "_request", None) or getattr(client, "request", None)
        base_url = getattr(client, "base_url", "https://api.music.yandex.net").rstrip("/")

        direct_returned_dict = False
        direct_url = (
            f"{base_url}/artists/{artist_id}/familiar-you"
            f"?waveTracksLimit={_FAMILIAR_TRACKS_LIMIT}&collectionTracksLimit={_FAMILIAR_TRACKS_LIMIT}"
        )
        if req is not None:
            try:
                direct_payload = await req.get(direct_url)
                if isinstance(direct_payload, dict):
                    direct_returned_dict = True
                state = await self._state_from_payload(direct_payload)
                if state.total > 0:
                    return state
            except Exception:
                logger.debug("direct familiar-you fetch failed for %s", artist_id, exc_info=True)

        if not hasattr(client, "artists_skeleton") or req is None:
            return _FamiliarState()
        try:
            skeleton = await client.artists_skeleton(artist_id, "web-artist-default")
        except Exception:
            logger.debug("artists_skeleton failed for %s", artist_id, exc_info=True)
            return _FamiliarState()
        if skeleton is None:
            return _FamiliarState()

        blocks = _familiar_blocks(_field(skeleton, "blocks"))
        for block in blocks:
            data = _field(block, "data")
            source = _field(data, "source")
            uri = _field(source, "uri")
            if not isinstance(uri, str) or not uri:
                continue
            if direct_returned_dict and "/familiar-you/info" in uri:
                continue
            url = uri if uri.startswith("http") else f"{base_url}/{uri.lstrip('/')}"
            if url == direct_url:
                continue
            try:
                payload = await req.get(url)
            except Exception:
                logger.debug("familiar uri fetch failed: %s", url, exc_info=True)
                continue
            state = await self._state_from_payload(payload)
            if state.total > 0:
                return state
        return _FamiliarState()

    async def _liked_id_pairs(self) -> tuple[tuple[int, int | None], ...]:
        now = time.monotonic()
        if self._likes_ids_cache is not None and now < self._likes_ids_cache[0]:
            return self._likes_ids_cache[1]
        client = self._require()
        try:
            likes = await client.users_likes_tracks(self.uid)
        except Exception:
            logger.debug("users_likes_tracks failed in familiar fallback", exc_info=True)
            return ()
        shorts = list(getattr(likes, "tracks", None) or [])
        pairs: list[tuple[int, int | None]] = []
        seen: set[int] = set()
        for short in shorts:
            raw_id = _field(short, "id")
            tid, embedded_aid = _parse_id_pair(raw_id)
            if tid is None:
                tid = as_int(raw_id)
            if tid is None or tid in seen:
                continue
            seen.add(tid)
            aid = as_int(_field(short, "album_id", "albumId")) or embedded_aid
            pairs.append((tid, aid))
        result = tuple(pairs)
        self._likes_ids_cache = (time.monotonic() + _CACHE_TTL_SEC, result)
        return result

    async def _familiar_from_likes(self, artist_id: int) -> tuple[str | int, ...]:
        client = self._require()
        liked_pairs = await self._liked_id_pairs()
        if not liked_pairs:
            return ()
        artist_ids: set[int] = set()
        if hasattr(client, "artists_track_ids"):
            try:
                raw_ids = await client.artists_track_ids(artist_id, page=0, page_size=300)
                for raw_id in raw_ids or []:
                    tid, _ = _parse_id_pair(raw_id)
                    if tid is None:
                        tid = as_int(raw_id)
                    if tid is not None:
                        artist_ids.add(tid)
            except Exception:
                logger.debug("artists_track_ids failed for %s", artist_id, exc_info=True)
        if not artist_ids:
            return ()
        matched: list[str | int] = []
        for tid, aid in liked_pairs:
            if tid in artist_ids:
                matched.append(f"{tid}:{aid}" if aid is not None else tid)
        return tuple(matched)

    async def _intersect_likes_with_popular(
        self, artist_id: int, raw_popular: list
    ) -> tuple[str | int, ...]:
        liked_pairs = await self._liked_id_pairs()
        if not liked_pairs:
            return ()
        popular_ids: set[int] = set()
        for item in raw_popular:
            tid, _ = _parse_id_pair(_field(item, "id"))
            if tid is None:
                tid = as_int(_field(item, "id"))
            if tid is not None:
                popular_ids.add(tid)
        if not popular_ids:
            return ()
        matched: list[str | int] = [
            f"{tid}:{aid}" if aid is not None else tid
            for tid, aid in liked_pairs
            if tid in popular_ids
        ]
        if matched:
            self._familiar_cache[artist_id] = (
                time.monotonic() + _CACHE_TTL_SEC,
                _FamiliarState(
                    collection_keys=tuple(matched),
                    wave_keys=(),
                    collection_tracks=None,
                    wave_tracks=(),
                ),
            )
        return tuple(matched)

    async def _from_shorts(self, shorts, *, indexed: bool) -> tuple[Track, ...]:
        client = self._require()
        tracks: list[Track] = []
        for index, short in enumerate(shorts):
            position_album = as_int(getattr(short, "album_id", None))
            track_obj = getattr(short, "track", None)
            track_id = as_int(getattr(short, "id", None))
            if track_obj is None and hasattr(short, "fetch_track_async"):
                try:
                    track_obj = await short.fetch_track_async()
                except Exception:
                    track_obj = None
            if track_obj is None and track_id is not None:
                key = f"{track_id}:{position_album}" if position_album else track_id
                try:
                    fetched = await client.tracks([key])
                except Exception:
                    fetched = None
                track_obj = fetched[0] if fetched else None
            if track_obj is None:
                continue
            tracks.append(
                track_from_api(
                    track_obj,
                    fallback_album_id=position_album,
                    index=index if indexed else None,
                )
            )
        return tuple(tracks)

    def _require(self):
        if not self.ready or self._client is None:
            raise RuntimeError("API-клиент не инициализирован")
        return self._client

    @staticmethod
    def _read_uid(client) -> int | None:
        for source in (
            getattr(client, "me", None),
            getattr(client, "account_status", None),
        ):
            account = getattr(source, "account", None)
            uid = as_int(getattr(account, "uid", None))
            if uid is not None:
                return uid
        return as_int(getattr(client, "account_uid", None))
