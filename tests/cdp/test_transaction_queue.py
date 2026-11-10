import asyncio

from ym_remote.cdp.monitor import MonitorCdpAdapter
from ym_remote.cdp.queue import QueueCdpAdapter
from ym_remote.cdp.scripts import playlist_script, queue_script, search_script, track_page_script
from ym_remote.cdp.search import SearchCdpAdapter
from ym_remote.cdp.session import CdpSession, score_page
from ym_remote.cdp.transport import TransportCdpAdapter
from ym_remote.models.requests import PlayRequest
from ym_remote.services.gate import HeavyGate
from ym_remote.services.texts import NO_ALBUM, PLAYLIST_ACTION_FAILED
from ym_remote.services.transport import TransportService
from ym_remote.models.errors import RemoteError
import pytest


class RecordingSession:
    def __init__(self, result="playing"):
        self.runs = 0
        self.expressions: list[str] = []
        self.result = result

    async def run(self, work):
        self.runs += 1
        return await work()

    async def evaluate(self, expression, timeout=3.0):
        self.expressions.append(expression)
        return self.result


def test_page_score_prefers_the_music_application():
    assert score_page("music-application://desktop/home") > score_page("https://music.yandex.ru/album/track")
    assert score_page("https://passport.yandex.ru/user-id") < 0


def test_track_page_script_navigates_by_id_and_does_not_use_search_cards():
    script = track_page_script(5, 9, "play")
    assert "/album/track?" in script
    assert "String(5)" in script
    assert "String(9)" in script
    assert "music-application://" not in script
    assert "SEARCH_TRACK_CARD" not in script
    assert "PLAY_BUTTON" in script
    assert 'action !== "play"' in script
    menu = track_page_script(5, 9, "next")
    assert "history.back()" in menu
    assert "history.pushState" in menu
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in menu
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT" in menu
    assert 'const action = "next"' in menu
    assert "music-application://" not in menu
    end = track_page_script(5, 9, "end")
    assert "TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON" in end
    assert "TRACK_CONTEXT_MENU_ADD_TO_QUEUE" in end
    assert 'const action = "end"' in end


def test_mid_list_lookup_does_not_fail_before_the_virtual_jump():
    for action in ("play", "next", "end"):
        script = playlist_script("pl-uuid", 72529580, None, 930, action)
        assert "const index = 930" in script
        assert "numericId(anchor) !== wanted" in script
        assert "stored != null ? stored : (index == null ? 0 : index)" in script
        assert "rows[index]" not in script
        assert "children[index]" not in script
        loop = script.split("for (let step = 0; step < 36; step++)", 1)[1].split(
            "async function revealAgain()", 1
        )[0]
        assert loop.index("row = findRow()") < loop.index("getTracksByRange")
        assert loop.index("getTracksByRange") < loop.index("scroller.scrollTop = targetTop")
        assert 'return "fail"' not in loop.split("getTracksByRange", 1)[0]


def test_playlist_script_reopens_before_lookup_and_uses_index_as_hint():
    script = playlist_script("pl-uuid", 15, 3, 40, "play")
    assert script.index("await ymInAppGo(playlistPath())") < script.index("function findRow")
    assert script.index("function findRow") < script.index("row = findRow()")
    assert "getTracksByRange" in script
    assert "totalListHeight" in script
    assert "virtuoso-scroller" in script
    assert "numericId(anchor) !== wanted" in script
    assert "(focus - 2) * height" in script
    assert "const index = 40" in script
    assert "const wanted = Number(trackId)" in script
    assert 'querySelectorAll(\'a[href*="trackId="]\')' not in script
    assert "music-application://" not in script


def test_add_to_queue_script_scrolls_until_track_and_clicks_queue_item():
    script = playlist_script("pl-uuid", 4304908, 3, 930, "end")
    assert script.index("await ymInAppGo(playlistPath())") < script.index("row = findRow()")
    assert script.index("getTracksByRange") < script.index("function menuItem()")
    assert script.index("row = findRow()") < script.index("ymClick(item)")
    assert script.count("row = findRow()") >= 2
    assert "const index = 930" in script
    assert "numericId(anchor) !== wanted" in script
    assert "(focus - 2) * height" in script
    assert 'return "no_menu"' in script
    assert "ymPressEscape()" in script
    item_fn = script.split("function menuItem()", 1)[1].split("function openRowMenu()", 1)[0]
    next_branch, end_branch = item_fn.split('if (action === "next")', 1)[1].split(
        "TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON", 1
    )
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in next_branch
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT" not in end_branch
    assert "TRACK_CONTEXT_MENU_ADD_TO_QUEUE" in end_branch
    assert 'data-test-id*="ADD_TO_QUEUE"' in end_branch
    play_next = playlist_script("pl-uuid", 4304908, 3, 930, "next")
    play_next_item = play_next.split("function menuItem()", 1)[1].split("function openRowMenu()", 1)[0]
    assert 'if (action === "next")' in play_next_item
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in play_next_item
    assert "getTracksByRange" in play_next


def test_playlist_script_closes_queue_panel_and_navigates_with_the_app_router():
    script = playlist_script("pl-uuid", 72529580, None, 930, "next")
    close = script.split("function queueOpen()", 1)[1].split("const wasHere", 1)[0]
    assert "FULLSCREEN_PLAYER_QUEUE_BUTTON" in close
    assert "PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON" in close
    assert "data-test-id" in close and "PLAY_QUEUE" in close
    assert "getBoundingClientRect" in close
    assert "if (queuePanel && ymVisible(queuePanel) && queueButton)" not in close
    assert "ymClick(toggle)" in close
    assert script.index("ymClick(toggle)") < script.index("await ymInAppGo(playlistPath())")
    go = script.split("async function ymInAppGo", 1)[1].split("\nfunction ", 1)[0]
    assert "router.push" in go
    assert go.index("router.push") < go.index("history.pushState")
    pushed = go.split("history.pushState", 1)[1]
    assert "return here() === target && here() !== before" in pushed
    assert "if (!ready)" in script
    assert 'return "fail"' in script


def test_playlist_menu_scopes_click_to_the_requested_row_and_ignores_queue_panel():
    script = playlist_script("pl-uuid", 72529580, None, 930, "next")
    assert script.index('ymById("PLAY_QUEUE")') < script.index("await ymInAppGo(playlistPath())")
    assert "FULLSCREEN_PLAYER_QUEUE_BUTTON" in script
    assert "function queueOpen()" in script
    assert 'closest(\'[data-test-id="PLAY_QUEUE"]' in script
    assert 'closest(\'[data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"]' in script
    assert "rowTrackId(row) !== wanted" in script
    assert script.index("function findRow") < script.index("ymClick(item)")
    click_guard = script.rsplit("ymClick(item)", 1)[0]
    assert "rowTrackId(row) !== wanted" in click_guard
    assert "forbidden(item)" in click_guard
    menu = script.split("function menuItem()", 1)[1].split("function openRowMenu()", 1)[0]
    assert 'ymById("TRACK_CONTEXT_MENU") || document' not in menu
    assert "document" not in menu
    assert "menuForRow()" in menu
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in menu
    assert "PLAY_LAST" not in menu.split('if (action === "next")', 1)[1].split("return found", 1)[0]
    opened = script.split("function openRowMenu()", 1)[1].split("let item = null", 1)[0]
    assert "ymById(id, row)" in opened
    assert "row.contains(found)" in opened
    assert "forbidden(found)" in opened
    assert "PLAY_QUEUE" not in opened
    end = playlist_script("pl-uuid", 72529580, None, 930, "end")
    end_menu = end.split("function menuItem()", 1)[1].split("function openRowMenu()", 1)[0]
    assert "TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON" in end_menu
    assert "menu.contains(found)" in end_menu
    guard, _ = script.rsplit("ymClick(item)", 1)
    assert "rowTrackId(row) !== wanted" in guard[-1200:]
    assert "menuTrack !== wanted" in guard[-1200:]
    assert "ARTIST_FAMILIAR_PAGE" in script
    assert "FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE" in script
    assert "confirmQueue" not in script
    assert 'return "mismatch"' not in script
    assert 'return confirmed ? "ok"' not in script
    clicked = script.split("ymClick(item)", 1)[1]
    assert 'return "ok"' in clicked
    assert 'return "fail"' not in clicked
    assert 'return "no_menu"' not in clicked
    assert 'return "fail"' in script
    assert 'return "no_menu"' in script
    page = track_page_script(72529580, None, "next")
    assert 'ymById("TRACK_CONTEXT_MENU") || document' not in page
    assert 'ymById("TRACK_PAGE") || document' not in page
    assert "outsideTrack(menuButton)" in page
    assert 'searchParams.get("trackId") !== trackId' in page
    assert "PLAY_QUEUE" in page
    assert "ARTIST_FAMILIAR_PAGE" in page


def test_playlist_and_queue_scripts_reopen_by_id():
    playlist = playlist_script("pl-uuid", 15, 3, 4, "play")
    assert "/playlists?playlistUuid=" in playlist
    assert "pl-uuid" in playlist
    assert "String(15)" in playlist
    assert "music-application://" not in playlist
    menu = playlist_script("pl-uuid", 15, 3, 4, "next")
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in menu
    assert "history.back()" in menu
    assert "music-application://" not in menu
    queue = queue_script("play", 77)
    assert "PLAY_QUEUE" in queue
    assert "PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON" in queue
    assert "String(77)" in queue


async def test_play_next_adapter_stays_inside_the_open_page():
    session = RecordingSession("ok")
    adapter = TransportCdpAdapter(session)
    code = await adapter.menu_track_page(5, 9, "next")
    assert code == "ok"
    assert session.runs == 1
    expression = session.expressions[0]
    assert "music-application://" not in expression
    assert "/album/track?" in expression
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in expression
    assert "SEARCH_TRACK_CARD" not in expression


def test_search_script_reads_ids_and_does_not_relaunch():
    script = search_script("Заблудись")
    assert "music-application://" not in script
    assert 'url.searchParams.get("trackId")' in script
    assert 'url.searchParams.get("albumId")' in script
    assert 'parts.indexOf("album")' in script
    assert 'parts.indexOf("track")' in script


async def test_adapter_opens_track_by_id_inside_one_transaction():
    session = RecordingSession()
    adapter = TransportCdpAdapter(session)
    code = await adapter.play_track_page(5, 9)
    assert code == "playing"
    assert session.runs == 1
    assert "album/track" in session.expressions[0]
    assert "String(5)" in session.expressions[0]
    assert "SEARCH_TRACK_CARD" not in session.expressions[0]


def test_subclasses_share_the_session_and_do_not_open_cdp():
    import inspect

    session = CdpSession(9222)
    adapters = [
        SearchCdpAdapter(session),
        TransportCdpAdapter(session),
        QueueCdpAdapter(session),
        MonitorCdpAdapter(session),
    ]
    for adapter in adapters:
        assert adapter.session is session
        source = inspect.getsource(type(adapter))
        assert "create_connection" not in source
        assert "webSocketDebuggerUrl" not in source


async def test_monitor_read_does_not_enter_the_transaction_queue():
    session = RecordingSession(
        {
            "title": "Song",
            "artists": ["A", "A", "B"],
            "is_playing": True,
            "cover_url": "https://cdn/200x200",
            "volume": 10,
            "repeat_mode": "off",
            "shuffle": False,
            "liked": False,
            "queue_name": "",
        }
    )
    playback = await MonitorCdpAdapter(session).read_playback()
    assert session.runs == 0
    assert session.expressions
    assert playback is not None
    assert playback.artist == "A, B"
    assert playback.track_key() == "A, B|Song"


class RecordingAdapter:
    def __init__(self, gate: HeavyGate, playlist_code: str = "fail", menu_code: str = "ok"):
        self.gate = gate
        self.calls: list[tuple] = []
        self.playlist_code = playlist_code
        self.menu_code = menu_code
        self.heavy_during_call = False

    async def play_playlist_row(self, **kwargs):
        self.heavy_during_call = self.gate.active
        self.calls.append(("playlist", kwargs["playlist_uuid"], kwargs["track_id"], kwargs["album_id"]))
        return self.playlist_code

    async def play_track_page(self, track_id, album_id):
        self.heavy_during_call = self.gate.active
        self.calls.append(("track", track_id, album_id))
        return "playing"

    async def menu_playlist_row(self, **kwargs):
        self.heavy_during_call = self.gate.active
        self.calls.append(
            (
                "playlist-menu",
                kwargs["playlist_uuid"],
                kwargs["track_id"],
                kwargs["album_id"],
                kwargs["action"],
                kwargs["index"],
            )
        )
        return self.menu_code

    async def menu_track_page(self, track_id, album_id, action):
        self.calls.append(("menu-track", track_id, album_id, action))
        return "ok"


class AlbumLookup:
    def __init__(self, album_id):
        self.album_id = album_id

    async def album_id_for(self, track_id):
        return self.album_id


async def test_play_now_without_playlist_opens_the_track_page_by_id():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate)
    service = TransportService(adapter, AlbumLookup(99), gate, retry_pause=0)
    await service.play_now(PlayRequest(track_id=5, album_id=None, title="Song", artist="A"))
    assert adapter.calls == [("track", 5, 99)]
    assert adapter.heavy_during_call is True
    assert gate.active is False
    assert all(name != "playlist" for name, *_ in adapter.calls)


async def test_play_now_with_playlist_tries_that_playlist_before_the_track_page():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate, playlist_code="fail")
    service = TransportService(adapter, None, gate, retry_pause=0)
    await service.play_now(
        PlayRequest(
            track_id=5,
            album_id=9,
            title="Song",
            artist="A",
            playlist_uuid="pl-1",
            playlist_track_index=2,
        )
    )
    assert adapter.calls[0] == ("playlist", "pl-1", 5, 9)
    assert adapter.calls[1] == ("track", 5, 9)


async def test_playlist_success_does_not_open_the_track_page():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate, playlist_code="playing")
    service = TransportService(adapter, None, gate, retry_pause=0)
    await service.play_now(PlayRequest(track_id=5, album_id=9, playlist_uuid="pl-1"))
    assert adapter.calls == [("playlist", "pl-1", 5, 9)]


async def test_search_play_without_playlist_resolves_album_before_the_track_page():
    log: list[tuple] = []

    class Lookup:
        async def album_id_for(self, track_id):
            log.append(("album", track_id))
            return 44

    class Adapter(RecordingAdapter):
        async def play_track_page(self, track_id, album_id):
            log.append(("track", track_id, album_id))
            return "playing"

    gate = HeavyGate()
    service = TransportService(Adapter(gate), Lookup(), gate, retry_pause=0)
    await service.play_now(PlayRequest(track_id=8, album_id=None, title="Заблудись", artist="Soltwine"))
    assert log == [("album", 8), ("track", 8, 44)]


async def test_play_next_with_playlist_and_without_album_uses_play_next_menu():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate)
    service = TransportService(adapter, AlbumLookup(None), gate, retry_pause=0)
    notice = await service.play_next(
        PlayRequest(
            track_id=72529580,
            album_id=None,
            title="Fed Up",
            artist="Ghostemane",
            playlist_uuid="pl-1",
            playlist_track_index=930,
        )
    )
    assert adapter.calls == [("playlist-menu", "pl-1", 72529580, None, "next", 930)]
    assert "играть следующим" in notice
    assert "нет альбома" not in notice
    script = playlist_script("pl-1", 72529580, None, 930, "next")
    assert script.index("await ymInAppGo(playlistPath())") < script.index("row = findRow()")
    assert "indexInStore" in script
    assert "numericId(anchor) !== wanted" in script
    item = script.split("function menuItem()", 1)[1].split("function openRowMenu()", 1)[0]
    next_part = item.split('if (action === "next")', 1)[1].split("TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON", 1)[0]
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON" in next_part
    assert "TRACK_CONTEXT_MENU_PLAY_NEXT" in next_part
    assert "PLAY_LAST" not in next_part


async def test_play_next_playlist_failure_without_album_is_not_the_no_album_error():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate, menu_code="fail")
    service = TransportService(adapter, AlbumLookup(None), gate, retry_pause=0)
    with pytest.raises(RemoteError) as caught:
        await service.play_next(
            PlayRequest(
                track_id=72529580,
                album_id=None,
                title="Fed Up",
                artist="Ghostemane",
                playlist_uuid="pl-1",
                playlist_track_index=930,
            )
        )
    assert caught.value.message == PLAYLIST_ACTION_FAILED
    assert caught.value.message != NO_ALBUM.format(track_id=72529580)
    assert adapter.calls == [("playlist-menu", "pl-1", 72529580, None, "next", 930)]


async def test_playlist_menu_failure_does_not_click_the_document_menu():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate, menu_code="fail")
    service = TransportService(adapter, AlbumLookup(3938372), gate, retry_pause=0)
    with pytest.raises(RemoteError) as caught:
        await service.play_next(
            PlayRequest(
                track_id=72529580,
                album_id=None,
                title="Fed Up",
                artist="Ghostemane",
                playlist_uuid="pl-1",
                playlist_track_index=930,
            )
        )
    assert "нет альбома" not in caught.value.message
    assert caught.value.message == PLAYLIST_ACTION_FAILED
    assert [call[0] for call in adapter.calls] == ["playlist-menu"]


async def test_play_next_stays_on_playlist_menu_after_album_lookup():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate)
    service = TransportService(adapter, AlbumLookup(3938372), gate, retry_pause=0)
    notice = await service.play_next(
        PlayRequest(
            track_id=72529580,
            album_id=None,
            title="Fed Up",
            artist="Ghostemane",
            playlist_uuid="pl-1",
            playlist_track_index=106,
        )
    )
    assert "играть следующим" in notice
    assert adapter.calls == [("playlist-menu", "pl-1", 72529580, 3938372, "next", 106)]


async def test_missing_album_does_not_guess_from_the_open_page():
    gate = HeavyGate()
    adapter = RecordingAdapter(gate)
    service = TransportService(adapter, AlbumLookup(None), gate, retry_pause=0)
    with pytest.raises(RemoteError) as caught:
        await service.play_now(PlayRequest(track_id=5, title="Song", artist="A"))
    assert caught.value.message == NO_ALBUM.format(track_id=5)
    assert adapter.calls == []


async def test_two_transactions_run_strictly_one_after_another():
    session = CdpSession(9222)
    await session.start()
    order: list[str] = []

    async def first():
        order.append("a-start")
        await asyncio.sleep(0.05)
        order.append("a-end")
        return "a"

    async def second():
        order.append("b-start")
        await asyncio.sleep(0.01)
        order.append("b-end")
        return "b"

    try:
        first_task = asyncio.create_task(session.run(first))
        await asyncio.sleep(0.01)
        second_task = asyncio.create_task(session.run(second))
        assert await first_task == "a"
        assert await second_task == "b"
        assert order == ["a-start", "a-end", "b-start", "b-end"]
    finally:
        await session.stop()
