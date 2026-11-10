from __future__ import annotations

from dataclasses import dataclass

from ym_remote.cdp.adapter import CdpAdapter
from ym_remote.cdp.scripts import search_script
from ym_remote.models.music import Album, Artist, Cover, Track


@dataclass(frozen=True)
class SearchHit:
    tracks: tuple[Track, ...]
    error_code: str | None = None


class SearchCdpAdapter(CdpAdapter):
    async def search(self, query: str) -> SearchHit:
        async def work() -> SearchHit:
            raw = await self.evaluate(search_script(query), timeout=30)
            return tracks_from_search(raw)

        return await self.session.run(work)


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
        names = item.get("artists") or []
        if isinstance(names, str):
            names = [names]
        artists = tuple(Artist(str(name).strip()) for name in names if str(name).strip())
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
    return SearchHit(tuple(tracks))


def _int(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
