from __future__ import annotations

from ym_remote.cdp.adapter import CdpAdapter
from ym_remote.cdp.scripts import queue_script
from ym_remote.models.music import Album, Artist, Cover, Track
from ym_remote.models.playback import NowMeta, QueueItem, QueueView


class QueueCdpAdapter(CdpAdapter):
    async def read_queue(self) -> QueueView:
        async def work() -> QueueView:
            raw = await self.evaluate(queue_script("read"), timeout=8)
            return queue_from_raw(raw)

        return await self.session.run(work)

    async def play_track(self, track_id: int) -> tuple[bool, QueueView]:
        async def work() -> tuple[bool, QueueView]:
            raw = await self.evaluate(queue_script("play", track_id), timeout=15)
            if not isinstance(raw, dict) or not raw.get("ok"):
                return False, QueueView.empty()
            return True, queue_from_raw(raw)

        return await self.session.run(work)


def queue_from_raw(raw) -> QueueView:
    if not isinstance(raw, dict):
        return QueueView.empty()
    current_raw = raw.get("current")
    after_title = str(raw.get("after_title") or "").strip() or "Далее в очереди"
    meta = raw.get("now_meta") if isinstance(raw.get("now_meta"), dict) else {}
    return QueueView(
        before=tuple(_item(item) for item in raw.get("before") or [] if isinstance(item, dict)),
        current=_item(current_raw, current=True) if isinstance(current_raw, dict) else None,
        after=tuple(_item(item) for item in raw.get("after") or [] if isinstance(item, dict)),
        before_title="Предыдущая очередь",
        after_title=after_title,
        now_meta=NowMeta(
            subtitle=str(meta.get("subtitle") or "").strip(),
            source=str(meta.get("source") or "").strip(),
        ),
    )


def _item(raw: dict, *, current: bool = False) -> QueueItem:
    names = raw.get("artists") or []
    if isinstance(names, str):
        names = [part.strip() for part in names.split(",") if part.strip()]
    artists = tuple(Artist(str(name).strip()) for name in names if str(name).strip())
    album_id = raw.get("album_id") if isinstance(raw.get("album_id"), int) else None
    track_id = raw.get("track_id") if isinstance(raw.get("track_id"), int) else None
    cover = raw.get("cover") or None
    track = Track(
        id=track_id,
        title=str(raw.get("title") or ""),
        artists=artists,
        albums=(Album(album_id, ""),) if album_id is not None else (),
        cover=Cover(str(cover)) if cover else None,
    )
    return QueueItem(track=track, is_playing=bool(raw.get("is_playing")), is_current=current)
