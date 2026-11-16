from __future__ import annotations

import math
import re

from ym_remote.models.music import Artist, Cover, join_artists
from ym_remote.models.playback import Playback

_ARTIST_HREF_ID = re.compile(r"(?:artistId=|/artist/)(\d+)")


def _finite_float(value) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _int_id(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _artist_id_from_href(href: str | None) -> int | None:
    if not href or not isinstance(href, str):
        return None
    match = _ARTIST_HREF_ID.search(href)
    return int(match.group(1)) if match else None


def _artists_from_raw(raw: dict, names: tuple[str, ...], artist_href: str | None) -> tuple[Artist, ...]:
    refs = raw.get("artist_refs")
    parsed: list[Artist] = []
    seen: set[tuple[int | None, str]] = set()
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            name = str(ref.get("name") or "").strip()
            if not name:
                continue
            aid = _int_id(ref.get("id"))
            key = (aid, name)
            if key in seen:
                continue
            seen.add(key)
            parsed.append(Artist(name=name, id=aid))
    if parsed:
        return tuple(parsed)
    unique_names: list[str] = []
    for name in names:
        clean = name.strip()
        if clean and clean not in unique_names:
            unique_names.append(clean)
    if len(unique_names) == 1:
        return (Artist(name=unique_names[0], id=_artist_id_from_href(artist_href)),)
    return tuple(Artist(name=name) for name in unique_names)


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
    artist_href = raw.get("artist_href") or None
    artist_objs = _artists_from_raw(raw, names, artist_href)
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
        artist_href=artist_href,
        album_href=raw.get("album_href") or None,
        position_sec=number("position_sec"),
        duration_sec=number("duration_sec"),
        repeat_mode=repeat,
        shuffle=bool(raw.get("shuffle")),
        liked=bool(raw.get("liked")),
        queue_name=str(raw.get("queue_name") or ""),
        artists=artist_objs,
    )
