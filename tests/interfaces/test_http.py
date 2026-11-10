from pathlib import Path

from fastapi.testclient import TestClient

from ym_remote.interfaces.factory import create_app
from ym_remote.interfaces.http.images import render_icon
from ym_remote.interfaces.settings import Settings
from ym_remote.services.texts import API_NOT_READY


def _app():
    root = Path(__file__).resolve().parents[2]
    settings = Settings(token="test-token", local_ip=None, port=8001, cdp_port=9222, root=root)
    return create_app(settings, discovered=["192.168.1.10", "10.0.0.5"], background=False)


def test_network_manifest_open_and_icons():
    with TestClient(_app()) as client:
        _assert_public_routes(client)


def _assert_public_routes(client: TestClient) -> None:
    info = client.get("/network-info")
    assert info.status_code == 200
    assert info.json() == {
        "chosen": "192.168.1.10",
        "port": 8001,
        "all": ["192.168.1.10", "10.0.0.5"],
        "url": "http://192.168.1.10:8001/",
    }
    manifest = client.get("/manifest.webmanifest")
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    body = manifest.json()
    assert body["name"] == "YM Remote"
    assert body["start_url"] == "/?source=pwa"
    assert body["icons"][1]["purpose"] == "any maskable"
    opened = client.get("/open")
    assert "Открыть пульт" in opened.text
    assert "location.replace('/')" in opened.text
    worker = client.get("/sw.js")
    assert worker.headers["cache-control"] == "no-cache"
    assert worker.headers["service-worker-allowed"] == "/"
    assert "skipWaiting" in worker.text
    assert "notificationclick" in worker.text
    assert "shade_command" in worker.text
    icon = client.get("/icon-192.png")
    assert icon.status_code == 200
    assert icon.content.startswith(b"\x89PNG")
    home = client.get("/api/library/home")
    assert home.status_code == 503
    assert home.json()["detail"] == API_NOT_READY


def test_qr_replaces_a_foreign_ip(monkeypatch):
    seen: dict[str, str] = {}

    def fake_qr(url: str) -> bytes:
        seen["url"] = url
        return b"\x89PNG\r\n\x1a\n"

    monkeypatch.setattr("ym_remote.interfaces.http.routes.render_qr", fake_qr)
    with TestClient(_app()) as client:
        response = client.get("/qr", params={"ip": "8.8.8.8"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert seen["url"] == "http://192.168.1.10:8001/"
        allowed = client.get("/qr", params={"ip": "10.0.0.5"})
        assert allowed.status_code == 200
        assert seen["url"] == "http://10.0.0.5:8001/"


def test_icon_has_the_specified_play_mark():
    from PIL import Image
    import io

    image = Image.open(io.BytesIO(render_icon(180)))
    assert image.size == (180, 180)
    assert image.getpixel((0, 0)) == (0, 0, 0)
    yellow = image.getpixel((45, 45))
    assert yellow[0] > 200 and yellow[1] > 150


def test_ws_keeps_connection_alive_on_cdp_errors_and_invalid_numbers():
    from ym_remote.cdp.session import CdpUnavailable
    from ym_remote.services.texts import LIKE_FAILED, SEEK_FAILED, VOLUME_FAILED

    app = _app()

    class BrokenAdapter:
        async def play_pause(self) -> bool:
            raise CdpUnavailable("нет CDP")

        async def set_volume(self, value: int) -> bool:
            raise CdpUnavailable("нет CDP")

        async def seek(self, position_sec: int) -> bool:
            raise CdpUnavailable("нет CDP")

        async def react(self, kind: str) -> bool:
            raise CdpUnavailable("нет CDP")

    app.state.services.transport.adapter = BrokenAdapter()

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"command": "play_pause"})
            ws.send_json({"command": "set_volume", "value": "NaN"})
            assert ws.receive_json() == {"type": "error", "message": VOLUME_FAILED}

            ws.send_json({"command": "set_volume", "value": True})
            assert ws.receive_json() == {"type": "error", "message": VOLUME_FAILED}

            ws.send_json({"command": "set_volume", "value": 45})
            assert ws.receive_json() == {"type": "error", "message": VOLUME_FAILED}

            ws.send_json({"command": "seek", "position_sec": 30})
            assert ws.receive_json() == {"type": "error", "message": SEEK_FAILED}

            ws.send_json({"command": "track_reaction", "kind": "like"})
            assert ws.receive_json() == {"type": "error", "message": LIKE_FAILED}


def test_artist_album_and_api_search_http_routes_and_ws_commands():
    from ym_remote.models.errors import RemoteError
    from ym_remote.models.music import (
        Album,
        Artist,
        ArtistDetail,
        Cover,
        FamiliarTracks,
        SearchView,
        Track,
        TrackPage,
    )
    from ym_remote.services.texts import (
        ALBUM_NOT_FOUND,
        ALBUM_PLAY_FAILED,
        ARTIST_NOT_FOUND,
        ARTIST_PLAY_FAILED,
    )

    app = _app()
    artist_ref = Artist(name="Radiohead", id=36800, cover=Cover("cdn.example/rh/%%"))
    sample_track = Track(
        id=10,
        title="Creep",
        artists=(artist_ref,),
        albums=(Album(id=100, title="Pablo Honey"),),
        cover=Cover("cdn.example/ph/%%"),
    )
    wave_track = Track(
        id=11,
        title="Karma Police",
        artists=(artist_ref,),
        albums=(Album(id=101, title="OK Computer"),),
        cover=Cover("cdn.example/ok/%%"),
    )

    class FakeLibrarySvc:
        async def artist(self, artist_id: int):
            if artist_id == 404:
                raise RemoteError(ARTIST_NOT_FOUND, 404)
            return ArtistDetail(
                id=artist_id,
                name="Radiohead",
                cover=Cover("cdn.example/rh/%%"),
                ambient_color="#5bbdd6",
                total_tracks=50,
                total_albums=2,
                popular_tracks=(sample_track,),
                familiar_total=4,
                albums=(Album(id=100, title="Pablo Honey", year=1993, track_count=12),),
                singles=(Album(id=101, title="Creep Single", year=1992, album_type="single"),),
            )

        async def artist_tracks(self, artist_id: int, page: int = 0, page_size: int = 50):
            return TrackPage(
                tracks=(sample_track,),
                page=page,
                page_size=page_size,
                total=30,
                has_more=True,
            )

        async def artist_familiar(self, artist_id: int):
            return FamiliarTracks(collection=(sample_track,), wave=(wave_track,))

        async def album(self, album_id: int):
            if album_id == 404:
                raise RemoteError(ALBUM_NOT_FOUND, 404)
            return Album(
                id=album_id,
                title="Pablo Honey",
                year=1993,
                track_count=12,
                artists=(artist_ref,),
                tracks=(sample_track,),
                cover=Cover("cdn.example/ph/%%"),
            )

        async def track_artists(self, track_id: int):
            return (artist_ref,)

        async def artists_by_ids(self, artist_ids):
            return tuple(artist_ref for aid in artist_ids if aid == 36800)

        async def resolve_artists(self, title: str, artist: str):
            return (artist_ref,)

    class FakeSearchSvc:
        async def search_all(self, query: str):
            return SearchView(artists=(artist_ref,), tracks=(sample_track,))

        async def search(self, query: str):
            return (sample_track,)

    ws_calls: list[tuple] = []

    class FakeTransportSvc:
        async def play_artist(self, artist_id: int) -> None:
            ws_calls.append(("play_artist", artist_id))

        async def play_album(self, album_id: int) -> None:
            ws_calls.append(("play_album", album_id))

        async def play_now(self, request) -> None:
            ws_calls.append(("play_now", request.track_id, request.artist_id, request.context_album_id))

    class NoopMonitor:
        async def command_tick(self, websocket, delay: float) -> None:
            ws_calls.append(("tick", delay))

    app.state.services.library = FakeLibrarySvc()
    app.state.services.search = FakeSearchSvc()
    app.state.handler.transport = FakeTransportSvc()
    app.state.handler.monitor = NoopMonitor()

    with TestClient(app) as client:
        res_search = client.get("/api/search", params={"q": "Radiohead"})
        assert res_search.status_code == 200
        body_search = res_search.json()
        assert body_search["artists"][0]["id"] == 36800
        assert body_search["tracks"][0]["id"] == 10
        assert body_search["tracks"][0]["artists"] == [
            {"id": 36800, "name": "Radiohead", "cover_url": "https://cdn.example/rh/200x200"}
        ]

        res_artist = client.get("/api/library/artist/36800")
        assert res_artist.status_code == 200
        body_artist = res_artist.json()
        assert body_artist["name"] == "Radiohead"
        assert body_artist["ambient_color"] == "#5bbdd6"
        assert body_artist["familiar_total"] == 4
        assert len(body_artist["albums"]) == 1
        assert len(body_artist["singles"]) == 1
        assert client.get("/api/library/artist/404").status_code == 404

        res_tracks = client.get("/api/library/artist/36800/tracks", params={"page": 1, "page_size": 20})
        assert res_tracks.status_code == 200
        assert res_tracks.json()["page"] == 1
        assert res_tracks.json()["page_size"] == 20
        assert res_tracks.json()["has_more"] is True

        res_familiar = client.get("/api/library/artist/36800/familiar")
        assert res_familiar.status_code == 200
        body_familiar = res_familiar.json()
        assert [t["id"] for t in body_familiar["collection_tracks"]] == [10]
        assert [t["id"] for t in body_familiar["wave_tracks"]] == [11]
        assert [t["id"] for t in body_familiar["tracks"]] == [10, 11]

        res_album = client.get("/api/library/album/100")
        assert res_album.status_code == 200
        assert res_album.json()["title"] == "Pablo Honey"
        assert res_album.json()["artists"] == [
            {"id": 36800, "name": "Radiohead", "cover_url": "https://cdn.example/rh/200x200"}
        ]
        assert client.get("/api/library/album/404").status_code == 404

        res_ta = client.get("/api/library/track/10/artists")
        assert res_ta.status_code == 200
        assert res_ta.json() == {
            "artists": [
                {"id": 36800, "name": "Radiohead", "cover_url": "https://cdn.example/rh/200x200"}
            ]
        }

        res_by_ids = client.get("/api/library/artists", params={"ids": "36800, 36800, bad, -2"})
        assert res_by_ids.status_code == 200
        assert res_by_ids.json() == {
            "artists": [
                {"id": 36800, "name": "Radiohead", "cover_url": "https://cdn.example/rh/200x200"}
            ]
        }

        res_resolve = client.get(
            "/api/library/resolve-artist",
            params={"title": "Creep", "artist": "Radiohead"},
        )
        assert res_resolve.status_code == 200
        assert res_resolve.json() == {
            "artists": [
                {"id": 36800, "name": "Radiohead", "cover_url": "https://cdn.example/rh/200x200"}
            ]
        }

        with client.websocket_connect("/ws") as ws:
            ws.send_json({"command": "play_artist", "artist_id": 0})
            assert ws.receive_json() == {"type": "error", "message": ARTIST_PLAY_FAILED}

            ws.send_json({"command": "play_album", "album_id": True})
            assert ws.receive_json() == {"type": "error", "message": ALBUM_PLAY_FAILED}

            ws.send_json({"command": "play_artist", "artist_id": 36800})
            ws.send_json({"command": "play_album", "album_id": 100})
            ws.send_json(
                {
                    "command": "play_now",
                    "track_id": 10,
                    "artist_id": 36800,
                    "artist_mode": "popular",
                }
            )
            ws.send_json({"command": "play_artist", "artist_id": -5})
            assert ws.receive_json() == {"type": "error", "message": ARTIST_PLAY_FAILED}

    assert ("play_artist", 36800) in ws_calls
    assert ("play_album", 100) in ws_calls
    assert ("play_now", 10, 36800, None) in ws_calls
