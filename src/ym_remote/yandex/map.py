from __future__ import annotations

import re

from ym_remote.models.music import Album, Artist, Cover, Playlist, Track

_ALBUM_IN_COVER = re.compile(r"\.a\.(\d+)-")


def as_int(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def _call(value):
    if callable(value):
        try:
            return value()
        except Exception:
            return None
    return value


def uri_of(obj) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, str) and obj:
        return obj
    for name in ("uri", "cover_uri", "og_image", "dir"):
        value = _call(getattr(obj, name, None))
        if isinstance(value, str) and value:
            return value
    return None


def _field(obj, *names):
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return None
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _album_id_from_uri(source) -> int | None:
    if not isinstance(source, str):
        return None
    match = _ALBUM_IN_COVER.search(source)
    return int(match.group(1)) if match else None


def _track_identity(track) -> tuple[int | None, int | None]:
    raw = _field(track, "id")
    if isinstance(raw, str) and ":" in raw:
        left, _, right = raw.partition(":")
        return as_int(left), as_int(right)
    return as_int(raw), as_int(_field(track, "album_id", "albumId"))


def track_from_api(track, *, fallback_album_id: int | None = None, index: int | None = None) -> Track:
    artists = []
    cover_sources: list[str] = []
    for artist in _field(track, "artists") or []:
        name = _text(_field(artist, "name"))
        artist_cover = uri_of(_field(artist, "cover")) or uri_of(artist)
        if artist_cover:
            cover_sources.append(artist_cover)
        if name:
            artists.append(Artist(name=name, id=as_int(_field(artist, "id"))))
    albums = []
    for album in _field(track, "albums") or []:
        if isinstance(album, (int, str)) and not isinstance(album, bool):
            album_id = as_int(album)
            title = ""
            cover_source = None
        else:
            album_id = as_int(_field(album, "id", "album_id", "albumId"))
            title = _text(_field(album, "title"))
            cover_source = uri_of(_field(album, "cover_uri", "cover")) or uri_of(album)
        if cover_source:
            cover_sources.append(cover_source)
        albums.append(
            Album(
                id=album_id,
                title=title,
                cover=Cover(cover_source) if cover_source else None,
            )
        )
    track_id, embedded_album = _track_identity(track)
    if all(album.id is None for album in albums):
        recovered = fallback_album_id if fallback_album_id is not None else embedded_album
        if recovered is None:
            for source in cover_sources:
                recovered = _album_id_from_uri(source)
                if recovered is not None:
                    break
            if recovered is None:
                recovered = _album_id_from_uri(uri_of(_field(track, "cover_uri", "og_image", "cover")))
        if recovered is not None:
            albums.insert(0, Album(id=recovered, title=""))
    cover_uri = uri_of(_field(track, "cover_uri", "og_image", "cover"))
    if cover_uri is None:
        for album in albums:
            if album.cover and album.cover.source:
                cover_uri = album.cover.source
                break
    return Track(
        id=track_id,
        title=_text(_field(track, "title")),
        artists=tuple(artists),
        albums=tuple(albums),
        cover=Cover(cover_uri) if cover_uri else None,
        playlist_index=index,
    )


def playlist_from_api(playlist, tracks: tuple[Track, ...] = ()) -> Playlist:
    cover_obj = getattr(playlist, "cover", None)
    cover_uri = uri_of(cover_obj) or uri_of(getattr(playlist, "og_image", None))
    uuid = getattr(playlist, "playlist_uuid", None) or getattr(playlist, "uuid", None)
    if not isinstance(uuid, str) or not uuid:
        uuid = None
    count = as_int(getattr(playlist, "track_count", None))
    if count is None:
        count = len(tracks)
    return Playlist(
        kind=as_int(getattr(playlist, "kind", None)),
        uid=as_int(getattr(playlist, "uid", None)),
        uuid=uuid,
        title=_text(getattr(playlist, "title", None)),
        track_count=count,
        cover=Cover(cover_uri) if cover_uri else None,
        tracks=tracks,
    )
