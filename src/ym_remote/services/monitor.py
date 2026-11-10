from __future__ import annotations

import asyncio
import logging

from ym_remote.cdp.monitor import MonitorCdpAdapter
from ym_remote.models.playback import Playback
from ym_remote.schemas.playback import playback_message
from ym_remote.services.gate import HeavyGate

logger = logging.getLogger(__name__)


class MonitorService:
    """Короткий тик 0,4 с и отдельный цикл 2 с. При тяжёлой команде оба спят."""

    def __init__(self, adapter: MonitorCdpAdapter, gate: HeavyGate, hub) -> None:
        self.adapter = adapter
        self.gate = gate
        self.hub = hub
        self.snapshot: Playback | None = None
        self._key = None
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._available = False
        self._reported_down = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._tick_loop(), name="player-tick"),
            asyncio.create_task(self._watch_loop(), name="player-watch"),
        ]

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    def note(self, playback: Playback) -> bool:
        key = playback.now_playing_tuple()
        changed = key != self._key
        self.snapshot = playback
        self.hub.snapshot = playback
        self._key = key
        return changed

    async def command_tick(self, websocket, delay: float) -> None:
        await asyncio.sleep(delay)
        playback = self.snapshot if self.gate.active else await self._safe_read()
        if playback is None:
            playback = self.snapshot
        if playback is None:
            return
        if self.note(playback):
            await self.hub.broadcast(playback_message("now_playing", playback))
        await self.hub.send(websocket, playback_message("player_tick", playback))

    async def bar_available(self) -> bool:
        if self.gate.active:
            return self.snapshot is not None
        playback = await self._safe_read()
        return playback is not None

    async def _tick_loop(self) -> None:
        while self._running:
            try:
                if self.gate.active:
                    await asyncio.sleep(0.4)
                    continue
                playback = await self._safe_read()
                if playback is not None:
                    await self._observe(playback)
                    await self.hub.broadcast(playback_message("player_tick", playback))
                await asyncio.sleep(0.4)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("tick loop failed", exc_info=True)
                await asyncio.sleep(0.4)

    async def _watch_loop(self) -> None:
        misses = 0
        while self._running:
            try:
                if self.gate.active:
                    await asyncio.sleep(0.5)
                    continue
                playback = await self._safe_read()
                if playback is None:
                    misses += 1
                    if misses >= 3 and not self._reported_down:
                        had = self.snapshot is not None
                        self.snapshot = None
                        self._key = None
                        self.hub.snapshot = None
                        self._available = False
                        self._reported_down = True
                        await self.hub.broadcast({"type": "cdp_status", "available": False})
                        if had:
                            await self.hub.broadcast({"type": "stopped"})
                else:
                    misses = 0
                    await self._observe(playback)
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("watch loop failed", exc_info=True)
                await asyncio.sleep(2)

    async def _observe(self, playback: Playback) -> None:
        if not self._available or self._reported_down:
            self._available = True
            self._reported_down = False
            await self.hub.broadcast({"type": "cdp_status", "available": True})
        if self.note(playback):
            await self.hub.broadcast(playback_message("now_playing", playback))

    async def _safe_read(self) -> Playback | None:
        try:
            return await self.adapter.read_playback()
        except Exception:
            logger.debug("bar read failed", exc_info=True)
            return None
