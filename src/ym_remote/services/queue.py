from __future__ import annotations

from ym_remote.cdp.queue import QueueCdpAdapter
from ym_remote.cdp.session import CdpError, CdpUnavailable
from ym_remote.models.errors import RemoteError
from ym_remote.models.playback import QueueView
from ym_remote.services.gate import HeavyGate
from ym_remote.services.texts import SKIP_FAILED, SKIP_TOO_FAR

MAX_SKIP_STEPS = 40


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

    async def skip(self, steps: int) -> QueueView:
        if steps == 0:
            return await self.show()
        if abs(steps) > MAX_SKIP_STEPS:
            raise RemoteError(SKIP_TOO_FAR)
        async with self.gate.hold():
            try:
                ok, view = await self.adapter.skip(steps)
            except (CdpUnavailable, CdpError, OSError, ConnectionError) as exc:
                raise RemoteError(SKIP_FAILED) from exc
        if not ok:
            raise RemoteError(SKIP_FAILED)
        return view
