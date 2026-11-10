from __future__ import annotations

from ym_remote.cdp.bar import playback_from_raw
from ym_remote.cdp.queue import queue_from_raw
from ym_remote.cdp.scripts import (
    HELPERS,
    album_play_script,
    album_row_script,
    artist_play_script,
    artist_row_script,
    queue_script,
    read_bar_script,
    search_script,
)
from ym_remote.cdp.transport import TransportCdpAdapter


class _RecordingSession:
    def __init__(self, result="playing"):
        self.runs = 0
        self.expressions: list[str] = []
        self.result = result

    async def run(self, work):
        self.runs += 1
        return await work()

    async def evaluate(self, expression: str, timeout: float = 3.0):
        self.expressions.append(expression)
        return self.result


def test_helpers_and_read_bar_extract_artist_refs_after_ym_in_app_go():
    assert HELPERS.index("async function ymInAppGo") < HELPERS.index("function ymArtistIdFromHref")
    assert HELPERS.index("function ymArtistIdFromHref") < HELPERS.index("function ymReadArtistRefs")
    assert 'searchParams.get("artistId")' in HELPERS
    assert 'SEPARATED_ARTIST_TITLE' in HELPERS

    bar = read_bar_script()
    assert "ymReadArtistRefs(artistRoot)" in bar
    assert "artist_refs: artistRefs" in bar
    assert "music-application://" not in bar

    queue = queue_script("read")
    assert "ymReadArtistRefs(row)" in queue
    assert "artist_refs: artistRefs" in queue
    assert "music-application://" not in queue

    search = search_script("Radiohead")
    assert "ymReadArtistRefs(card)" in search
    assert "artist_cards: artistCards" in search
    assert "ymArtistIdFromHref" in search
    assert "music-application://" not in search


def test_bar_and_queue_parsers_preserve_numeric_artist_ids_and_href_fallback():
    pb = playback_from_raw(
        {
            "title": "Song",
            "artists": ["A", "B"],
            "artist_refs": [{"id": 10, "name": "A"}, {"id": "20", "name": "B"}],
            "is_playing": True,
            "artist_href": "/artist?artistId=10",
        }
    )
    assert pb is not None
    assert [(a.id, a.name) for a in pb.artists] == [(10, "A"), (20, "B")]

    pb_href = playback_from_raw(
        {
            "title": "Solo",
            "artists": ["Radiohead"],
            "artist_refs": [],
            "is_playing": False,
            "artist_href": "https://music.yandex.ru/artist/36800",
        }
    )
    assert pb_href is not None
    assert [(a.id, a.name) for a in pb_href.artists] == [(36800, "Radiohead")]

    q_view = queue_from_raw(
        {
            "ok": True,
            "current": {
                "title": "Creep",
                "artists": ["Radiohead"],
                "artist_refs": [{"id": 36800, "name": "Radiohead"}],
                "track_id": 10,
                "album_id": 100,
                "is_playing": True,
            },
            "after": [],
            "before": [],
        }
    )
    assert q_view.current is not None
    assert [(a.id, a.name) for a in q_view.current.track.artists] == [(36800, "Radiohead")]


def test_artist_and_album_play_scripts_avoid_hardcoded_protocol_and_trailers():
    artist_js = artist_play_script(36800)
    assert "music-application://" not in artist_js
    assert '"/artist?artistId="' in artist_js
    assert "String(36800)" in artist_js
    assert "function queueOpen()" in artist_js
    assert "ARTIST_PAGE" in artist_js
    assert "ENTITY_HEADER" in artist_js
    assert "TRAILER" in artist_js
    assert "ymTransportPlaying()" in artist_js

    album_js = album_play_script(9001)
    assert "music-application://" not in album_js
    assert '"/album?albumId="' in album_js
    assert "String(9001)" in album_js
    assert "function queueOpen()" in album_js
    assert "ALBUM_PAGE" in album_js
    assert "TRAILER" in album_js
    assert "ymTransportPlaying()" in album_js


def test_artist_and_album_row_scripts_cover_modes_and_menu_actions():
    for mode, expected_path in (
        ("popular", '"/artist?artistId="'),
        ("tracks", '"/artist/tracks?artistId="'),
        ("familiar", '"/artist/familiar?artistId="'),
        ("familiar_collection", '"&tab=collection"'),
        ("familiar_wave", '"&tab=vibe"'),
    ):
        js = artist_row_script(36800, mode, 10, 100, 3, "play")
        assert "music-application://" not in js
        assert expected_path in js
        assert "numericId(anchor) !== wanted" in js
        assert "function queueOpen()" in js

    col_js = artist_row_script(36800, "familiar_collection", 10, 100, 0, "play")
    assert "FAMILIAR_YOU_SCROLLABLE_CONTENT_COLLECTION" in col_js
    assert "FAMILIAR_YOU_SECTION_ALBUM" in col_js

    wave_js = artist_row_script(36800, "familiar_wave", 10, 100, 1, "play")
    assert "FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE" in wave_js
    assert 'url.searchParams.get("tab") === "vibe"' in wave_js

    artist_next = artist_row_script(36800, "tracks", 10, 100, 3, "next")
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in artist_next
    assert "history.back()" in artist_next
    assert 'return "no_menu"' in artist_next

    album_play = album_row_script(9001, 10, 2, "play")
    assert "music-application://" not in album_play
    assert '"/album?albumId="' in album_play
    assert "TRACK_ALBUM" in album_play

    album_end = album_row_script(9001, 10, 2, "end")
    assert "TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON" in album_end
    assert "TRACK_CONTEXT_MENU_ADD_TO_QUEUE" in album_end
    assert "history.back()" in album_end
    assert "music-application://" not in album_end


async def test_transport_cdp_adapter_runs_artist_and_album_commands_in_transaction_queue():
    session = _RecordingSession("playing")
    adapter = TransportCdpAdapter(session)

    assert await adapter.play_artist(36800) == "playing"
    assert await adapter.play_album(9001) == "playing"
    assert (
        await adapter.play_artist_row(
            artist_id=36800, mode="popular", track_id=10, album_id=100, index=0
        )
        == "playing"
    )
    assert await adapter.play_album_row(album_id=9001, track_id=10, index=0) == "playing"

    session.result = "ok"
    assert (
        await adapter.menu_artist_row(
            artist_id=36800, mode="familiar", track_id=10, album_id=100, index=1, action="next"
        )
        == "ok"
    )
    assert (
        await adapter.menu_album_row(album_id=9001, track_id=10, index=1, action="end")
        == "ok"
    )

    assert session.runs == 6
    assert all("music-application://" not in expr for expr in session.expressions)
