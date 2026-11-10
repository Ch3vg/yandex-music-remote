from __future__ import annotations

import asyncio
from dataclasses import replace

from ym_remote.cdp.session import CdpError, CdpUnavailable
from ym_remote.cdp.transport import TransportCdpAdapter
from ym_remote.models.errors import RemoteError
from ym_remote.models.requests import PlayRequest
from ym_remote.services.gate import HeavyGate
from ym_remote.services.library import LibraryService
from ym_remote.services.texts import (
    ADD_QUEUE_FAILED,
    LIKE_FAILED,
    MENU_UNAVAILABLE,
    NAVIGATE_FAILED,
    NO_ALBUM,
    PLAYLIST_ACTION_FAILED,
    PLAY_DESKTOP_FAILED,
    PLAY_FAILED,
    REPEAT_BUTTON_MISSING,
    REPEAT_FAILED,
    SEEK_FAILED,
    SHUFFLE_FAILED,
    TRACK_ACTION_FAILED,
    VOLUME_FAILED,
    queue_notice,
)

_PLAY_OK = {"playing", "started"}
_CDP_FAILURES = (CdpUnavailable, CdpError, OSError, ConnectionError)


class TransportService:
    """Политика пульта: плейлист, затем страница трека. Адаптер порядок не выбирает."""

    def __init__(
        self,
        adapter: TransportCdpAdapter,
        library: LibraryService | None,
        gate: HeavyGate,
        *,
        retry_pause: float = 0.8,
    ) -> None:
        self.adapter = adapter
        self.library = library
        self.gate = gate
        self.retry_pause = retry_pause

    async def play_pause(self) -> bool:
        try:
            return await self.adapter.play_pause()
        except _CDP_FAILURES:
            return False

    async def next_track(self) -> bool:
        try:
            return await self.adapter.next_track()
        except _CDP_FAILURES:
            return False

    async def previous_track(self) -> bool:
        try:
            return await self.adapter.previous_track()
        except _CDP_FAILURES:
            return False

    async def set_volume(self, value: float) -> None:
        clipped = max(0, min(100, int(round(value))))
        try:
            ok = await self.adapter.set_volume(clipped)
        except _CDP_FAILURES as exc:
            raise RemoteError(VOLUME_FAILED) from exc
        if not ok:
            raise RemoteError(VOLUME_FAILED)

    async def seek(self, position_sec: int) -> None:
        if position_sec < 0:
            position_sec = 0
        try:
            ok = await self.adapter.seek(position_sec)
        except _CDP_FAILURES as exc:
            raise RemoteError(SEEK_FAILED) from exc
        if not ok:
            raise RemoteError(SEEK_FAILED)

    async def set_shuffle(self, on: bool) -> None:
        try:
            ok = await self.adapter.set_shuffle(bool(on))
        except _CDP_FAILURES as exc:
            raise RemoteError(SHUFFLE_FAILED) from exc
        if not ok:
            raise RemoteError(SHUFFLE_FAILED)

    async def cycle_repeat(self) -> None:
        try:
            code = await self.adapter.cycle_repeat()
        except _CDP_FAILURES as exc:
            raise RemoteError(REPEAT_FAILED) from exc
        if code == "missing":
            raise RemoteError(REPEAT_BUTTON_MISSING)
        if code != "ok":
            raise RemoteError(REPEAT_FAILED)

    async def set_repeat(self, mode: str) -> bool:
        if mode not in {"off", "queue", "one"}:
            return False
        try:
            code = await self.adapter.set_repeat(mode)
        except _CDP_FAILURES as exc:
            raise RemoteError(REPEAT_FAILED) from exc
        if code == "missing":
            raise RemoteError(REPEAT_BUTTON_MISSING)
        if code != "ok":
            raise RemoteError(REPEAT_FAILED)
        return True

    async def react(self, kind: str) -> bool | None:
        if kind not in {"like", "dislike"}:
            return None
        try:
            ok = await self.adapter.react(kind)
        except _CDP_FAILURES as exc:
            raise RemoteError(LIKE_FAILED) from exc
        if not ok:
            raise RemoteError(LIKE_FAILED)
        return True

    async def navigate(self, target: str) -> bool | None:
        if target not in {"artist", "album"}:
            return None
        try:
            ok = await self.adapter.navigate(target)
        except _CDP_FAILURES as exc:
            raise RemoteError(NAVIGATE_FAILED) from exc
        if not ok:
            raise RemoteError(NAVIGATE_FAILED)
        return True

    async def play_now(self, request: PlayRequest) -> None:
        request = await self._with_album(request)
        async with self.gate.hold():
            try:
                if request.playlist_uuid:
                    code = await self.adapter.play_playlist_row(
                        playlist_uuid=request.playlist_uuid,
                        track_id=request.track_id,
                        album_id=request.album_id,
                        index=request.playlist_track_index,
                    )
                    if code in _PLAY_OK:
                        return
                if request.album_id is None:
                    if request.playlist_uuid:
                        raise RemoteError(PLAY_FAILED)
                    raise RemoteError(NO_ALBUM.format(track_id=request.track_id))
                for attempt in range(3):
                    code = await self.adapter.play_track_page(request.track_id, request.album_id)
                    if code in _PLAY_OK:
                        return
                    if attempt < 2:
                        await asyncio.sleep(self.retry_pause)
            except RemoteError:
                raise
            except (CdpUnavailable, OSError, ConnectionError) as exc:
                raise RemoteError(PLAY_DESKTOP_FAILED) from exc
            except CdpError as exc:
                raise RemoteError(PLAY_FAILED) from exc
        raise RemoteError(PLAY_FAILED)

    async def play_next(self, request: PlayRequest) -> str:
        return await self._menu(request, end=False)

    async def add_to_queue(self, request: PlayRequest) -> str:
        return await self._menu(request, end=True)

    async def _menu(self, request: PlayRequest, *, end: bool) -> str:
        request = await self._with_album(request)
        action = "end" if end else "next"
        code = "fail"
        async with self.gate.hold():
            try:
                if request.playlist_uuid:
                    code = await self.adapter.menu_playlist_row(
                        playlist_uuid=request.playlist_uuid,
                        track_id=request.track_id,
                        album_id=request.album_id,
                        index=request.playlist_track_index,
                        action=action,
                    )
                    if code == "ok":
                        return queue_notice(request.artist, request.title, end=end)
                    if code == "no_menu":
                        raise RemoteError(MENU_UNAVAILABLE)
                    raise RemoteError(PLAYLIST_ACTION_FAILED)
                if request.album_id is None:
                    raise RemoteError(NO_ALBUM.format(track_id=request.track_id))
                for attempt in range(3):
                    code = await self.adapter.menu_track_page(request.track_id, request.album_id, action)
                    if code == "ok":
                        return queue_notice(request.artist, request.title, end=end)
                    if attempt < 2:
                        await asyncio.sleep(self.retry_pause)
            except RemoteError:
                raise
            except (CdpUnavailable, CdpError, OSError, ConnectionError) as exc:
                if end:
                    raise RemoteError(ADD_QUEUE_FAILED) from exc
                raise RemoteError(TRACK_ACTION_FAILED) from exc
        if code == "no_menu":
            raise RemoteError(MENU_UNAVAILABLE)
        if end:
            raise RemoteError(ADD_QUEUE_FAILED)
        if request.playlist_uuid:
            raise RemoteError(PLAYLIST_ACTION_FAILED)
        raise RemoteError(TRACK_ACTION_FAILED)

    async def _with_album(self, request: PlayRequest) -> PlayRequest:
        if request.album_id is not None or self.library is None:
            return request
        album_id = await self.library.album_id_for(request.track_id)
        if album_id is None:
            return request
        return replace(request, album_id=album_id)
