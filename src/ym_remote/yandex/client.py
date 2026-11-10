from __future__ import annotations

import logging
from dataclasses import replace

from ym_remote.models.music import Track
from ym_remote.yandex.map import as_int, playlist_from_api, track_from_api

logger = logging.getLogger(__name__)


class YandexLibrary:
    """Асинхронный клиент yandex-music. В очередь CDP не входит."""

    def __init__(self, token: str) -> None:
        self.token = token
        self._client = None
        self.ready = False
        self.uid: int | None = None

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
