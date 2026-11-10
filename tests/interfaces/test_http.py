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
