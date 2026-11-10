from __future__ import annotations

from ym_remote.cdp.bar import playback_from_raw
from ym_remote.cdp.adapter import CdpAdapter
from ym_remote.models.playback import Playback


class MonitorCdpAdapter(CdpAdapter):
    """Чтение бара. В очередь транзакций не встаёт."""

    async def read_playback(self) -> Playback | None:
        raw = await self.read_bar()
        return playback_from_raw(raw)
