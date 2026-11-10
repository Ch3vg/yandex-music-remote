from __future__ import annotations

import logging

from ym_remote.models.playback import Playback

logger = logging.getLogger(__name__)


class Hub:
    def __init__(self) -> None:
        self._sockets: set = set()
        self.snapshot: Playback | None = None

    async def connect(self, websocket) -> None:
        self._sockets.add(websocket)
        if self.snapshot is not None:
            from ym_remote.schemas.playback import playback_message

            await self.send(websocket, playback_message("now_playing", self.snapshot))

    def disconnect(self, websocket) -> None:
        self._sockets.discard(websocket)

    async def send(self, websocket, payload: dict) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            logger.debug("socket send failed", exc_info=True)
            self._sockets.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        for websocket in list(self._sockets):
            await self.send(websocket, payload)
