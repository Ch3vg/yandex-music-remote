from __future__ import annotations

from ym_remote.cdp.adapter import CdpAdapter
from ym_remote.cdp.scripts import (
    album_play_script,
    album_row_script,
    artist_play_script,
    artist_row_script,
    cycle_repeat_script,
    navigate_script,
    next_script,
    play_pause_script,
    playlist_script,
    previous_script,
    reaction_script,
    seek_script,
    set_repeat_script,
    shuffle_script,
    track_page_script,
    volume_script,
)


class TransportCdpAdapter(CdpAdapter):
    """Умеет включить строку плейлиста, артиста, альбома и страницу трека. Порядок попыток выбирает сервис."""

    async def play_pause(self) -> bool:
        return await self._bool(play_pause_script())

    async def next_track(self) -> bool:
        return await self._bool(next_script())

    async def previous_track(self) -> bool:
        return await self._bool(previous_script(), timeout=5)

    async def set_volume(self, value: int) -> bool:
        return await self._bool(volume_script(value))

    async def seek(self, position_sec: int) -> bool:
        return await self._bool(seek_script(position_sec))

    async def set_shuffle(self, on: bool) -> bool:
        return await self._bool(shuffle_script(on))

    async def cycle_repeat(self) -> str:
        return await self._code(cycle_repeat_script())

    async def set_repeat(self, mode: str) -> str:
        return await self._code(set_repeat_script(mode), timeout=8)

    async def react(self, kind: str) -> bool:
        return await self._bool(reaction_script(kind))

    async def navigate(self, target: str) -> bool:
        return await self._bool(navigate_script(target))

    async def play_artist(self, artist_id: int) -> str:
        expression = artist_play_script(artist_id)
        return await self._code(expression, timeout=35)

    async def play_album(self, album_id: int) -> str:
        expression = album_play_script(album_id)
        return await self._code(expression, timeout=35)

    async def play_playlist_row(
        self,
        *,
        playlist_uuid: str,
        track_id: int,
        album_id: int | None,
        index: int | None,
    ) -> str:
        expression = playlist_script(playlist_uuid, track_id, album_id, index, "play")
        return await self._code(expression, timeout=35)

    async def play_artist_row(
        self,
        *,
        artist_id: int,
        mode: str | None,
        track_id: int,
        album_id: int | None,
        index: int | None,
    ) -> str:
        expression = artist_row_script(artist_id, mode, track_id, album_id, index, "play")
        return await self._code(expression, timeout=35)

    async def play_album_row(
        self,
        *,
        album_id: int,
        track_id: int,
        index: int | None,
    ) -> str:
        expression = album_row_script(album_id, track_id, index, "play")
        return await self._code(expression, timeout=35)

    async def play_track_page(self, track_id: int, album_id: int | None) -> str:
        expression = track_page_script(track_id, album_id, "play")
        return await self._code(expression, timeout=35)

    async def menu_playlist_row(
        self,
        *,
        playlist_uuid: str,
        track_id: int,
        album_id: int | None,
        index: int | None,
        action: str,
    ) -> str:
        expression = playlist_script(playlist_uuid, track_id, album_id, index, action)
        return await self._code(expression, timeout=35)

    async def menu_artist_row(
        self,
        *,
        artist_id: int,
        mode: str | None,
        track_id: int,
        album_id: int | None,
        index: int | None,
        action: str,
    ) -> str:
        expression = artist_row_script(artist_id, mode, track_id, album_id, index, action)
        return await self._code(expression, timeout=35)

    async def menu_album_row(
        self,
        *,
        album_id: int,
        track_id: int,
        index: int | None,
        action: str,
    ) -> str:
        expression = album_row_script(album_id, track_id, index, action)
        return await self._code(expression, timeout=35)

    async def menu_track_page(self, track_id: int, album_id: int | None, action: str) -> str:
        expression = track_page_script(track_id, album_id, action)
        return await self._code(expression, timeout=35)

    async def _bool(self, expression: str, timeout: float = 3) -> bool:
        async def work() -> bool:
            return bool(await self.evaluate(expression, timeout=timeout))

        return await self.session.run(work)

    async def _code(self, expression: str, timeout: float = 3) -> str:
        async def work() -> str:
            result = await self.evaluate(expression, timeout=timeout)
            return result if isinstance(result, str) else "fail"

        return await self.session.run(work)
