from __future__ import annotations

from ym_remote.models.playback import QueueItem, QueueView
from ym_remote.schemas.catalog import ArtistRefWire


def _item(item: QueueItem, *, current: bool = False) -> dict:
    cover = item.track.cover.source if item.track.cover else None
    payload = {
        "title": item.track.title,
        "artist": item.track.artist_line(),
        "artists": [ArtistRefWire.from_artist(a).model_dump() for a in item.track.artists],
        "cover": cover or None,
        "track_id": item.track.id,
        "album_id": item.track.album_id(),
        "is_playing": item.is_playing,
    }
    if current:
        payload["is_current"] = True
    return payload


def queue_message(view: QueueView) -> dict:
    return {
        "type": "queue",
        "before": [_item(item) for item in view.before],
        "current": _item(view.current, current=True) if view.current else None,
        "after": [_item(item) for item in view.after],
        "before_title": view.before_title or "Предыдущая очередь",
        "after_title": view.after_title or "Далее в очереди",
        "now_meta": {
            "subtitle": view.now_meta.subtitle,
            "source": view.now_meta.source,
        },
    }
