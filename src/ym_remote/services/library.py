from __future__ import annotations

from collections.abc import Sequence
import logging
from dataclasses import dataclass, replace

from ym_remote.models.errors import RemoteError
from ym_remote.models.music import (
    Album,
    Artist,
    ArtistDetail,
    FamiliarTracks,
    Playlist,
    Track,
    TrackPage,
)
from ym_remote.services.texts import (
    ALBUM_NOT_FOUND,
    API_NOT_READY,
    ARTIST_NOT_FOUND,
    LIBRARY_FAILED,
    PLAYLIST_NOT_FOUND,
)
from ym_remote.yandex.client import YandexLibrary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LibraryHome:
    likes: Playlist
    tracks: tuple[Track, ...]
    playlists: tuple[Playlist, ...]


def full_likes_count(reported: int, preview: int, total: int) -> int:
    """Полный размер плейлиста. Длина превью главной не подменяет счётчик."""
    if reported > preview:
        return reported
    if total > reported:
        return total
    return reported


class LibraryService:
    def __init__(self, catalog: YandexLibrary) -> None:
        self.catalog = catalog

    async def home(self) -> LibraryHome:
        self._ready()
        try:
            tracks, total = await self.catalog.like_tracks(limit=12)
            playlists = await self.catalog.playlists()
            listed = next((playlist for playlist in playlists if playlist.is_likes), None)
            kind = listed.kind if listed is not None and listed.kind is not None else 3
            summary = None
            try:
                summary = await self.catalog.playlist_summary(kind)
            except Exception:
                logger.debug("likes playlist refresh failed", exc_info=True)
            if summary is not None:
                likes = summary
            elif listed is not None:
                likes = listed
            else:
                likes = Playlist(
                    kind=3,
                    uid=self.catalog.uid,
                    uuid=None,
                    title="Мне нравится",
                    track_count=0,
                    cover=None,
                    tracks=(),
                )
            count = full_likes_count(likes.track_count, len(tracks), total)
            if count != likes.track_count or not likes.title:
                likes = replace(
                    likes,
                    title=likes.title or "Мне нравится",
                    track_count=count,
                )
            others = tuple(playlist for playlist in playlists if playlist.title and not playlist.is_likes)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("library home failed")
            raise RemoteError(LIBRARY_FAILED, 500) from exc
        if likes.title != "Мне нравится" and likes.kind == 3:
            likes = Playlist(
                kind=likes.kind,
                uid=likes.uid,
                uuid=likes.uuid,
                title=likes.title or "Мне нравится",
                track_count=likes.track_count,
                cover=likes.cover,
                tracks=likes.tracks,
            )
        return LibraryHome(likes=likes, tracks=tracks, playlists=others)

    async def playlist(self, kind: int) -> Playlist:
        self._ready()
        try:
            playlist = await self.catalog.playlist(kind)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("playlist %s failed", kind)
            raise RemoteError(LIBRARY_FAILED, 500) from exc
        if playlist is None:
            raise RemoteError(PLAYLIST_NOT_FOUND, 500)
        return playlist

    async def artist(self, artist_id: int) -> ArtistDetail:
        self._ready()
        try:
            detail = await self.catalog.artist_detail(artist_id)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("artist %s failed", artist_id)
            raise RemoteError(LIBRARY_FAILED, 500) from exc
        if detail is None:
            raise RemoteError(ARTIST_NOT_FOUND, 404)
        return detail

    async def artist_tracks(
        self, artist_id: int, page: int = 0, page_size: int = 50
    ) -> TrackPage:
        self._ready()
        try:
            return await self.catalog.artist_tracks(artist_id, page=page, page_size=page_size)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("artist tracks %s failed", artist_id)
            raise RemoteError(LIBRARY_FAILED, 500) from exc

    async def artist_familiar(self, artist_id: int) -> FamiliarTracks:
        self._ready()
        try:
            return await self.catalog.artist_familiar(artist_id)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("artist familiar %s failed", artist_id)
            raise RemoteError(LIBRARY_FAILED, 500) from exc

    async def album(self, album_id: int) -> Album:
        self._ready()
        try:
            album = await self.catalog.album_with_tracks(album_id)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("album %s failed", album_id)
            raise RemoteError(LIBRARY_FAILED, 500) from exc
        if album is None:
            raise RemoteError(ALBUM_NOT_FOUND, 404)
        return album

    async def artists_by_ids(self, artist_ids: Sequence[int]) -> tuple[Artist, ...]:
        self._ready()
        if not artist_ids:
            return ()
        try:
            return await self.catalog.artists_by_ids(artist_ids)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("artists by ids failed for %s", artist_ids)
            raise RemoteError(LIBRARY_FAILED, 500) from exc

    async def track_artists(self, track_id: int) -> tuple[Artist, ...]:
        self._ready()
        try:
            return await self.catalog.track_artists(track_id)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("track artists %s failed", track_id)
            raise RemoteError(LIBRARY_FAILED, 500) from exc

    async def resolve_artists(self, title: str, artist: str) -> tuple[Artist, ...]:
        self._ready()
        try:
            return await self.catalog.resolve_artists(title, artist)
        except RemoteError:
            raise
        except Exception as exc:
            logger.exception("resolve artists failed for %r / %r", title, artist)
            raise RemoteError(LIBRARY_FAILED, 500) from exc

    async def search_artists(self, query: str, limit: int = 6) -> tuple[Artist, ...] | None:
        if not self.catalog.ready:
            return None
        try:
            return await self.catalog.search_artists(query, limit=limit)
        except Exception:
            logger.debug("artist search failed for %r", query, exc_info=True)
            return None

    async def album_id_for(self, track_id: int) -> int | None:
        if not self.catalog.ready:
            return None
        try:
            return await self.catalog.first_album_id(track_id)
        except Exception:
            logger.debug("album lookup failed for %s", track_id, exc_info=True)
            return None

    def _ready(self) -> None:
        if not self.catalog.ready:
            raise RemoteError(API_NOT_READY, 503)
