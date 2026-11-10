from __future__ import annotations

from dataclasses import replace

from ym_remote.cdp.search import SearchCdpAdapter
from ym_remote.cdp.session import CdpError, CdpUnavailable
from ym_remote.models.errors import RemoteError
from ym_remote.models.music import Album, Track
from ym_remote.services.gate import HeavyGate
from ym_remote.services.library import LibraryService
from ym_remote.services.texts import SEARCH_CODES, SEARCH_PARSE, SEARCH_UNAVAILABLE


class SearchService:
    def __init__(
        self,
        adapter: SearchCdpAdapter,
        gate: HeavyGate,
        library: LibraryService | None = None,
    ) -> None:
        self.adapter = adapter
        self.gate = gate
        self.library = library

    async def search(self, query: str) -> tuple[Track, ...]:
        query = (query or "").strip()
        if not query:
            return ()
        async with self.gate.hold():
            try:
                hit = await self.adapter.search(query)
            except (CdpUnavailable, OSError, ConnectionError) as exc:
                raise RemoteError(SEARCH_UNAVAILABLE, 503) from exc
            except (CdpError, TimeoutError) as exc:
                raise RemoteError(SEARCH_PARSE, 503) from exc
        if hit.error_code:
            raise RemoteError(SEARCH_CODES.get(hit.error_code, SEARCH_PARSE), 503)
        return await self._with_albums(hit.tracks)

    async def _with_albums(self, tracks: tuple[Track, ...]) -> tuple[Track, ...]:
        if self.library is None:
            return tracks
        filled: list[Track] = []
        for track in tracks:
            if track.id is None or track.album_id() is not None:
                filled.append(track)
                continue
            album_id = await self.library.album_id_for(track.id)
            if album_id is None:
                filled.append(track)
                continue
            filled.append(replace(track, albums=(Album(album_id, ""),) + track.albums))
        return tuple(filled)
