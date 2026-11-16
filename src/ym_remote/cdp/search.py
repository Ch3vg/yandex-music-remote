from __future__ import annotations

from dataclasses import dataclass

from ym_remote.cdp.adapter import CdpAdapter
from ym_remote.cdp.scripts import search_script
from ym_remote.models.music import Album, Artist, Cover, Track


@dataclass(frozen=True)
class SearchHit:
    tracks: tuple[Track, ...]
    error_code: str | None = None
    artists: tuple[Artist, ...] = ()


class SearchCdpAdapter(CdpAdapter):
    async def search(self, query: str) -> SearchHit:
        async def work() -> SearchHit:
            raw = await self.evaluate(search_script(query), timeout=30)
            return tracks_from_search(raw)

        return await self.session.run(work)


def _parse_track_artists(item: dict) -> tuple[Artist, ...]:
    refs = item.get("artist_refs")
    if isinstance(refs, list):
        parsed: list[Artist] = []
        seen: set[tuple[int | None, str]] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            name = str(ref.get("name") or "").strip()
            if not name:
                continue
            aid = _int(ref.get("id"))
            key = (aid, name)
            if key in seen:
                continue
            seen.add(key)
            parsed.append(Artist(name=name, id=aid))
        if parsed:
            return tuple(parsed)
    names = item.get("artists") or []
    if isinstance(names, str):
        names = [names]
    return tuple(Artist(str(name).strip()) for name in names if str(name).strip())


def _parse_artist_cards(payload: dict) -> tuple[Artist, ...]:
    cards: list[Artist] = []
    seen: set[int] = set()
    for raw in payload.get("artist_cards") or []:
        if not isinstance(raw, dict):
            continue
        artist_id = _int(raw.get("id"))
        name = str(raw.get("name") or "").strip()
        if artist_id is None or not name or artist_id in seen:
            continue
        seen.add(artist_id)
        cover = raw.get("cover") or None
        cards.append(
            Artist(
                name=name,
                id=artist_id,
                cover=Cover(str(cover)) if cover else None,
            )
        )
        if len(cards) >= 6:
            break
    return tuple(cards)


def tracks_from_search(payload) -> SearchHit:
    if not isinstance(payload, dict):
        return SearchHit((), "parse")
    if not payload.get("ok"):
        code = payload.get("code") or "parse"
        if code not in {"no_button", "no_page", "no_input", "parse"}:
            code = "parse"
        return SearchHit((), code)
    tracks: list[Track] = []
    for item in payload.get("tracks") or []:
        if not isinstance(item, dict):
            continue
        track_id = _int(item.get("track_id"))
        title = str(item.get("title") or "").strip()
        if track_id is None or not title:
            continue
        artists = _parse_track_artists(item)
        album_id = _int(item.get("album_id"))
        cover = item.get("cover") or None
        tracks.append(
            Track(
                id=track_id,
                title=title,
                artists=artists,
                albums=(Album(album_id, ""),) if album_id is not None else (),
                cover=Cover(str(cover)) if cover else None,
            )
        )
        if len(tracks) >= 15:
            break
    return SearchHit(tuple(tracks), artists=_parse_artist_cards(payload))


def _int(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
