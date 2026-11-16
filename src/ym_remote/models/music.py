from __future__ import annotations

import re
from dataclasses import dataclass

_SIZE_SUFFIX = re.compile(r"/\d+x\d+$")


def ensure_https(url: str) -> str:
    if url.startswith("https://") or url.startswith("http://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return "https://" + url


def join_artists(names: tuple[str, ...]) -> str:
    seen: list[str] = []
    for name in names:
        cleaned = name.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.append(cleaned)
    return ", ".join(seen)


@dataclass(frozen=True)
class Cover:
    """Исходный адрес обложки. Размеры для списка и HQ считаются от него."""

    source: str | None

    def list_url(self) -> str | None:
        if not self.source:
            return None
        return ensure_https(self.source).replace("%%", "200x200")

    def hq_url(self) -> str | None:
        listed = self.list_url()
        if not listed:
            return None
        return _SIZE_SUFFIX.sub("/1000x1000", listed)


@dataclass(frozen=True)
class Artist:
    name: str
    id: int | None = None
    cover: Cover | None = None


@dataclass(frozen=True)
class Album:
    id: int | None
    title: str
    cover: Cover | None = None
    year: int | None = None
    album_type: str | None = None
    version: str | None = None
    track_count: int = 0
    artists: tuple[Artist, ...] = ()
    tracks: tuple[Track, ...] = ()

    def artist_line(self) -> str:
        return join_artists(tuple(artist.name for artist in self.artists))


@dataclass(frozen=True)
class Track:
    id: int | None
    title: str
    artists: tuple[Artist, ...] = ()
    albums: tuple[Album, ...] = ()
    cover: Cover | None = None
    playlist_index: int | None = None

    def artist_line(self) -> str:
        return join_artists(tuple(artist.name for artist in self.artists))

    def album_id(self) -> int | None:
        for album in self.albums:
            if album.id is not None:
                return album.id
        return None

    def change_key(self) -> str:
        """Ключ смены трека на пульте. На провод уходит строковым track_id."""
        return f"{self.artist_line()}|{self.title}"


@dataclass(frozen=True)
class Playlist:
    kind: int | None
    uid: int | None
    uuid: str | None
    title: str
    track_count: int
    cover: Cover | None = None
    tracks: tuple[Track, ...] = ()

    @property
    def is_likes(self) -> bool:
        return self.title == "Мне нравится" or self.kind == 3


@dataclass(frozen=True)
class ArtistDetail:
    id: int
    name: str
    cover: Cover | None = None
    ambient_color: str | None = None
    total_tracks: int = 0
    total_albums: int = 0
    popular_tracks: tuple[Track, ...] = ()
    familiar_total: int = 0
    albums: tuple[Album, ...] = ()
    singles: tuple[Album, ...] = ()


@dataclass(frozen=True)
class FamiliarTracks:
    collection: tuple[Track, ...] = ()
    wave: tuple[Track, ...] = ()

    @property
    def total(self) -> int:
        return len(self.all_tracks())

    def all_tracks(self) -> tuple[Track, ...]:
        ordered: list[Track] = []
        seen: set[int] = set()
        for track in (*self.collection, *self.wave):
            if track.id is not None:
                if track.id in seen:
                    continue
                seen.add(track.id)
            ordered.append(track)
        return tuple(ordered)


@dataclass(frozen=True)
class TrackPage:
    tracks: tuple[Track, ...] = ()
    page: int = 0
    page_size: int = 50
    total: int = 0
    has_more: bool = False


@dataclass(frozen=True)
class SearchView:
    artists: tuple[Artist, ...] = ()
    tracks: tuple[Track, ...] = ()

