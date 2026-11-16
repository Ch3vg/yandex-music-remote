from __future__ import annotations

import pytest

from ym_remote.cdp.session import CdpUnavailable
from ym_remote.models.errors import RemoteError
from ym_remote.models.music import Album, Artist, ArtistDetail, Track
from ym_remote.models.requests import PlayRequest
from ym_remote.services.gate import HeavyGate
from ym_remote.services.texts import (
    ALBUM_PLAY_FAILED,
    ARTIST_PLAY_FAILED,
    MENU_UNAVAILABLE,
    PLAY_DESKTOP_FAILED,
)
from ym_remote.services.transport import TransportService


class _TransportAdapter:
    def __init__(
        self,
        gate: HeavyGate,
        *,
        artist_code: str = "playing",
        album_code: str = "playing",
        artist_row_code: str = "playing",
        album_row_code: str = "playing",
        track_code: str = "playing",
        menu_artist_code: str = "ok",
        menu_album_code: str = "ok",
        menu_track_code: str = "ok",
    ):
        self.gate = gate
        self.artist_code = artist_code
        self.album_code = album_code
        self.artist_row_code = artist_row_code
        self.album_row_code = album_row_code
        self.track_code = track_code
        self.menu_artist_code = menu_artist_code
        self.menu_album_code = menu_album_code
        self.menu_track_code = menu_track_code
        self.calls: list[tuple] = []
        self.heavy_flags: list[bool] = []

    async def play_artist(self, artist_id: int) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(("play_artist", artist_id))
        return self.artist_code

    async def play_album(self, album_id: int) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(("play_album", album_id))
        return self.album_code

    async def play_artist_row(self, **kwargs) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(
            (
                "play_artist_row",
                kwargs["artist_id"],
                kwargs["mode"],
                kwargs["track_id"],
                kwargs["album_id"],
                kwargs["index"],
            )
        )
        return self.artist_row_code

    async def play_album_row(self, **kwargs) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(
            ("play_album_row", kwargs["album_id"], kwargs["track_id"], kwargs["index"])
        )
        return self.album_row_code

    async def play_track_page(self, track_id: int, album_id: int | None) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(("play_track_page", track_id, album_id))
        return self.track_code

    async def menu_artist_row(self, **kwargs) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(
            (
                "menu_artist_row",
                kwargs["artist_id"],
                kwargs["mode"],
                kwargs["track_id"],
                kwargs["album_id"],
                kwargs["index"],
                kwargs["action"],
            )
        )
        return self.menu_artist_code

    async def menu_album_row(self, **kwargs) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(
            (
                "menu_album_row",
                kwargs["album_id"],
                kwargs["track_id"],
                kwargs["index"],
                kwargs["action"],
            )
        )
        return self.menu_album_code

    async def menu_track_page(self, track_id: int, album_id: int | None, action: str) -> str:
        self.heavy_flags.append(self.gate.active)
        self.calls.append(("menu_track_page", track_id, album_id, action))
        return self.menu_track_code


class _FakeLibrary:
    def __init__(self, *, popular_tracks=(), album_tracks=(), resolved_album_id=777):
        self.popular_tracks = popular_tracks
        self.album_tracks = album_tracks
        self.resolved_album_id = resolved_album_id

    async def artist(self, artist_id: int):
        return ArtistDetail(
            id=artist_id,
            name="Radiohead",
            popular_tracks=tuple(self.popular_tracks),
        )

    async def album(self, album_id: int):
        return Album(id=album_id, title="OK Computer", tracks=tuple(self.album_tracks))

    async def album_id_for(self, track_id: int):
        return self.resolved_album_id


async def test_play_artist_succeeds_directly_or_falls_back_to_first_popular_track():
    gate = HeavyGate()
    direct = _TransportAdapter(gate, artist_code="playing")
    svc = TransportService(direct, None, gate, retry_pause=0)
    await svc.play_artist(36800)
    assert direct.calls == [("play_artist", 36800)]
    assert direct.heavy_flags == [True]
    assert gate.active is False

    fallback_adapter = _TransportAdapter(gate, artist_code="fail", track_code="started")
    lib = _FakeLibrary(
        popular_tracks=(Track(id=10, title="Creep", artists=(Artist("Radiohead", 36800),)),),
        resolved_album_id=100,
    )
    svc_fallback = TransportService(fallback_adapter, lib, gate, retry_pause=0)
    await svc_fallback.play_artist(36800)
    assert fallback_adapter.calls == [
        ("play_artist", 36800),
        ("play_track_page", 10, 100),
    ]

    failing = _TransportAdapter(gate, artist_code="fail", track_code="fail")
    svc_fail = TransportService(failing, None, gate, retry_pause=0)
    with pytest.raises(RemoteError) as err:
        await svc_fail.play_artist(36800)
    assert err.value.message == ARTIST_PLAY_FAILED


async def test_play_album_succeeds_directly_or_falls_back_to_first_track():
    gate = HeavyGate()
    direct = _TransportAdapter(gate, album_code="playing")
    svc = TransportService(direct, None, gate, retry_pause=0)
    await svc.play_album(500)
    assert direct.calls == [("play_album", 500)]

    fallback_adapter = _TransportAdapter(gate, album_code="fail", track_code="playing")
    lib = _FakeLibrary(album_tracks=(Track(id=55, title="Airbag"),))
    svc_fallback = TransportService(fallback_adapter, lib, gate, retry_pause=0)
    await svc_fallback.play_album(500)
    assert fallback_adapter.calls == [
        ("play_album", 500),
        ("play_track_page", 55, 500),
    ]

    failing = _TransportAdapter(gate, album_code="fail", track_code="fail")
    svc_fail = TransportService(failing, None, gate, retry_pause=0)
    with pytest.raises(RemoteError) as err:
        await svc_fail.play_album(500)
    assert err.value.message == ALBUM_PLAY_FAILED


async def test_play_artist_maps_cdp_unavailable_to_desktop_error():
    class DownAdapter:
        async def play_artist(self, artist_id: int) -> str:
            raise CdpUnavailable("down")

    svc = TransportService(DownAdapter(), None, HeavyGate(), retry_pause=0)
    with pytest.raises(RemoteError) as err:
        await svc.play_artist(1)
    assert err.value.message == PLAY_DESKTOP_FAILED


async def test_play_now_and_play_next_with_artist_and_album_contexts_and_fallback():
    gate = HeavyGate()
    adapter = _TransportAdapter(
        gate,
        artist_row_code="fail",
        album_row_code="fail",
        track_code="playing",
        menu_artist_code="fail",
        menu_album_code="ok",
        menu_track_code="ok",
    )
    lib = _FakeLibrary(resolved_album_id=999)
    svc = TransportService(adapter, lib, gate, retry_pause=0)

    # Artist context -> fails -> falls back to play_track_page with resolved album_id
    await svc.play_now(
        PlayRequest(
            track_id=10,
            album_id=None,
            title="Creep",
            artist="Radiohead",
            artist_id=36800,
            artist_mode="popular",
            playlist_track_index=0,
        )
    )
    assert adapter.calls[:2] == [
        ("play_artist_row", 36800, "popular", 10, 999, 0),
        ("play_track_page", 10, 999),
    ]

    adapter.calls.clear()
    # Album context -> fails -> falls back to play_track_page using context_album_id as album_id
    await svc.play_now(
        PlayRequest(
            track_id=11,
            album_id=None,
            title="Karma Police",
            artist="Radiohead",
            context_album_id=101,
            playlist_track_index=5,
        )
    )
    assert adapter.calls == [
        ("play_album_row", 101, 11, 5),
        ("play_track_page", 11, 101),
    ]

    adapter.calls.clear()
    # play_next on artist context -> fails -> falls back to menu_track_page
    notice = await svc.play_next(
        PlayRequest(
            track_id=12,
            album_id=101,
            title="No Surprises",
            artist="Radiohead",
            artist_id=36800,
            artist_mode="familiar",
            playlist_track_index=2,
        )
    )
    assert "играть следующим" in notice
    assert adapter.calls == [
        ("menu_artist_row", 36800, "familiar", 12, 101, 2, "next"),
        ("menu_track_page", 12, 101, "next"),
    ]

    adapter.calls.clear()
    # add_to_queue on album context -> succeeds directly without track page
    notice_end = await svc.add_to_queue(
        PlayRequest(
            track_id=13,
            title="Lucky",
            artist="Radiohead",
            context_album_id=101,
            playlist_track_index=10,
        )
    )
    assert "в конец очереди" in notice_end
    assert adapter.calls == [("menu_album_row", 101, 13, 10, "end")]

    # no_menu in artist context surfaces MENU_UNAVAILABLE immediately
    no_menu = _TransportAdapter(gate, menu_artist_code="no_menu")
    svc_no_menu = TransportService(no_menu, None, gate, retry_pause=0)
    with pytest.raises(RemoteError) as err:
        await svc_no_menu.play_next(
            PlayRequest(track_id=12, album_id=101, artist_id=36800, artist_mode="tracks")
        )
    assert err.value.message == MENU_UNAVAILABLE
