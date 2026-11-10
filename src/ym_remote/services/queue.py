from __future__ import annotations

from ym_remote.cdp.queue import QueueCdpAdapter
from ym_remote.cdp.session import CdpError, CdpUnavailable
from ym_remote.models.errors import RemoteError
from ym_remote.models.playback import QueueView
from ym_remote.services.gate import HeavyGate
from ym_remote.services.texts import queue_track_failed


class QueueService:
    def __init__(self, adapter: QueueCdpAdapter, gate: HeavyGate) -> None:
        self.adapter = adapter
        self.gate = gate

    async def show(self) -> QueueView:
        async with self.gate.hold():
            try:
                return await self.adapter.read_queue()
            except (CdpUnavailable, CdpError, OSError, ConnectionError):
                return QueueView.empty()

    async def play(self, track_id: int, album_id: int | None = None) -> QueueView:
        del album_id
        async with self.gate.hold():
            try:
                ok, view = await self.adapter.play_track(track_id)
            except (CdpUnavailable, CdpError, OSError, ConnectionError) as exc:
                raise RemoteError(queue_track_failed(track_id)) from exc
        if not ok:
            raise RemoteError(queue_track_failed(track_id))
        return view
