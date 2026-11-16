from __future__ import annotations

import json
import math

from pydantic import ValidationError

from ym_remote.models.errors import RemoteError
from ym_remote.schemas.play import PlayCommand
from ym_remote.schemas.queue import queue_message
from ym_remote.services.monitor import MonitorService
from ym_remote.services.queue import QueueService
from ym_remote.services.texts import ALBUM_PLAY_FAILED, ARTIST_PLAY_FAILED, PLAY_FAILED
from ym_remote.services.transport import TransportService


def _positive_id(raw) -> int | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


class CommandHandler:
    def __init__(self, transport: TransportService, queue: QueueService, monitor: MonitorService, hub) -> None:
        self.transport = transport
        self.queue = queue
        self.monitor = monitor
        self.hub = hub

    async def handle(self, websocket, message: dict) -> None:
        command = message.get("command")
        if not isinstance(command, str):
            return
        method = getattr(self, f"_cmd_{command}", None)
        if method is None:
            return
        await method(websocket, message)

    async def _cmd_play_pause(self, websocket, message: dict) -> None:
        if await self.transport.play_pause():
            await self.monitor.command_tick(websocket, 0.05)

    async def _cmd_next(self, websocket, message: dict) -> None:
        if await self.transport.next_track():
            await self.monitor.command_tick(websocket, 0.12)

    async def _cmd_prev(self, websocket, message: dict) -> None:
        if await self.transport.previous_track():
            await self.monitor.command_tick(websocket, 0.12)

    async def _cmd_set_volume(self, websocket, message: dict) -> None:
        raw_val = message.get("value")
        if isinstance(raw_val, bool):
            await self._error(websocket, "Не удалось изменить громкость")
            return
        try:
            value = float(raw_val)
        except (TypeError, ValueError, OverflowError):
            await self._error(websocket, "Не удалось изменить громкость")
            return
        if not math.isfinite(value):
            await self._error(websocket, "Не удалось изменить громкость")
            return
        try:
            await self.transport.set_volume(value)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.monitor.command_tick(websocket, 0.06)

    async def _cmd_seek(self, websocket, message: dict) -> None:
        raw_pos = message.get("position_sec")
        if isinstance(raw_pos, bool):
            await self._error(websocket, "Не удалось перемотать трек")
            return
        try:
            position = int(raw_pos)
        except (TypeError, ValueError, OverflowError):
            await self._error(websocket, "Не удалось перемотать трек")
            return
        try:
            await self.transport.seek(position)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.monitor.command_tick(websocket, 0.06)

    async def _cmd_set_shuffle(self, websocket, message: dict) -> None:
        try:
            await self.transport.set_shuffle(bool(message.get("on")))
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.monitor.command_tick(websocket, 0.05)

    async def _cmd_cycle_repeat(self, websocket, message: dict) -> None:
        try:
            await self.transport.cycle_repeat()
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.monitor.command_tick(websocket, 0.08)

    async def _cmd_set_repeat(self, websocket, message: dict) -> None:
        mode = message.get("mode")
        if not isinstance(mode, str):
            return
        try:
            changed = await self.transport.set_repeat(mode)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        if changed:
            await self.monitor.command_tick(websocket, 0.05)

    async def _cmd_track_reaction(self, websocket, message: dict) -> None:
        kind = message.get("kind")
        if not isinstance(kind, str):
            return
        try:
            changed = await self.transport.react(kind)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        if changed:
            await self.monitor.command_tick(websocket, 0.1)

    async def _cmd_navigate(self, websocket, message: dict) -> None:
        target = message.get("target")
        if not isinstance(target, str):
            return
        try:
            await self.transport.navigate(target)
        except RemoteError as exc:
            await self._error(websocket, exc.message)

    async def _cmd_play_artist(self, websocket, message: dict) -> None:
        artist_id = _positive_id(message.get("artist_id"))
        if artist_id is None:
            await self._error(websocket, ARTIST_PLAY_FAILED)
            return
        try:
            await self.transport.play_artist(artist_id)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.monitor.command_tick(websocket, 0.2)

    async def _cmd_play_album(self, websocket, message: dict) -> None:
        album_id = _positive_id(message.get("album_id"))
        if album_id is None:
            await self._error(websocket, ALBUM_PLAY_FAILED)
            return
        try:
            await self.transport.play_album(album_id)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.monitor.command_tick(websocket, 0.2)

    async def _cmd_play_now(self, websocket, message: dict) -> None:
        request = self._play_request(message)
        if request is None:
            await self._error(websocket, PLAY_FAILED)
            return
        try:
            await self.transport.play_now(request)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.monitor.command_tick(websocket, 0.2)

    async def _cmd_play(self, websocket, message: dict) -> None:
        await self._cmd_play_next(websocket, message)

    async def _cmd_queue(self, websocket, message: dict) -> None:
        await self._cmd_play_next(websocket, message)

    async def _cmd_play_next(self, websocket, message: dict) -> None:
        await self._menu(websocket, message, end=False)

    async def _cmd_add_to_queue(self, websocket, message: dict) -> None:
        await self._menu(websocket, message, end=True)

    async def _menu(self, websocket, message: dict, *, end: bool) -> None:
        request = self._play_request(message)
        if request is None:
            await self._error(websocket, "Не удалось выполнить действие с треком")
            return
        try:
            notice = await (self.transport.add_to_queue(request) if end else self.transport.play_next(request))
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.hub.send(websocket, {"type": "notice", "message": notice})

    async def _cmd_show_queue(self, websocket, message: dict) -> None:
        view = await self.queue.show()
        await self.hub.send(websocket, queue_message(view))

    async def _cmd_refresh_queue(self, websocket, message: dict) -> None:
        await self._cmd_show_queue(websocket, message)

    async def _cmd_play_queue_track(self, websocket, message: dict) -> None:
        try:
            track_id = int(message.get("track_id"))
        except (TypeError, ValueError):
            await self._error(websocket, "Не удалось включить трек из очереди")
            return
        album = message.get("album_id")
        try:
            album_id = int(album) if album is not None else None
        except (TypeError, ValueError):
            album_id = None
        try:
            view = await self.queue.play(track_id, album_id)
        except RemoteError as exc:
            await self._error(websocket, exc.message)
            return
        await self.hub.send(websocket, queue_message(view))

    async def _error(self, websocket, text: str) -> None:
        await self.hub.send(websocket, {"type": "error", "message": text})

    @staticmethod
    def _play_request(message: dict):
        try:
            return PlayCommand.model_validate(message).to_request()
        except ValidationError:
            return None


def parse_message(raw: str) -> dict | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
