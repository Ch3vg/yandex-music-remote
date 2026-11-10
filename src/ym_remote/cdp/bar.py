from __future__ import annotations

import math

from ym_remote.models.music import Cover, join_artists
from ym_remote.models.playback import Playback


def _finite_float(value) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def playback_from_raw(raw: dict | None) -> Playback | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    artists = raw.get("artists") or []
    if isinstance(artists, str):
        names = tuple(part.strip() for part in artists.split(","))
    else:
        names = tuple(str(name) for name in artists)
    cover_url = raw.get("cover_url") or None
    if cover_url == "":
        cover_url = None
    hq = Cover(cover_url).hq_url() if cover_url else None
    raw_volume = _finite_float(raw.get("volume"))
    volume = max(0, min(100, int(round(raw_volume)))) if raw_volume is not None else None
    repeat = raw.get("repeat_mode") or "off"
    if repeat not in {"off", "queue", "one"}:
        repeat = "off"

    def number(key: str) -> float | None:
        return _finite_float(raw.get(key))

    return Playback(
        title=title,
        artist=join_artists(names),
        is_playing=bool(raw.get("is_playing")),
        cover_url=cover_url,
        cover_url_hq=hq,
        volume=volume,
        artist_href=raw.get("artist_href") or None,
        album_href=raw.get("album_href") or None,
        position_sec=number("position_sec"),
        duration_sec=number("duration_sec"),
        repeat_mode=repeat,
        shuffle=bool(raw.get("shuffle")),
        liked=bool(raw.get("liked")),
        queue_name=str(raw.get("queue_name") or ""),
    )
