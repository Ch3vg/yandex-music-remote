from ym_remote.interfaces.ws.handler import ADMIN_REQUIRED, WRONG_PIN, CommandHandler


class Socket:
    pass


class Hub:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, websocket, message: dict) -> None:
        self.sent.append(message)


class Transport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def next_track(self) -> bool:
        self.calls.append("next")
        return False

    async def play_next(self, request) -> str:
        self.calls.append("play_next")
        return "ok"

    async def add_to_queue(self, request) -> str:
        self.calls.append("add_to_queue")
        return "ok"

    async def play_now(self, request) -> None:
        self.calls.append("play_now")

    async def play_album(self, album_id: int) -> None:
        self.calls.append("play_album")

    async def play_artist(self, artist_id: int) -> None:
        self.calls.append("play_artist")

    async def start_wave(self, request) -> None:
        self.calls.append("start_wave")

    async def react(self, kind: str) -> bool:
        self.calls.append("react")
        return False


def _handler(pin: str = "1234") -> tuple[CommandHandler, Transport, Hub]:
    transport = Transport()
    hub = Hub()
    handler = CommandHandler(transport, None, None, hub, pin=pin)
    return handler, transport, hub


TRACK = {"track_id": 1, "album_id": 2, "title": "Трек", "artist": "Исполнитель"}


async def test_guest_is_rejected_on_forbidden_commands_and_allowed_on_queue_edits():
    handler, transport, hub = _handler()
    socket = Socket()
    forbidden = [
        {"command": "play_now", **TRACK},
        {"command": "play", **TRACK},
        {"command": "queue", **TRACK},
        {"command": "play_queue_track", "track_id": 1},
        {"command": "play_album", "album_id": 2},
        {"command": "play_artist", "artist_id": 3},
        {"command": "start_wave", "source": "personal"},
        {"command": "track_reaction", "kind": "like"},
    ]
    for message in forbidden:
        await handler.handle(socket, message)
    assert transport.calls == []
    assert [item["message"] for item in hub.sent] == [ADMIN_REQUIRED] * len(forbidden)

    hub.sent.clear()
    await handler.handle(socket, {"command": "play_next", **TRACK})
    await handler.handle(socket, {"command": "add_to_queue", **TRACK})
    await handler.handle(socket, {"command": "next"})
    assert transport.calls == ["play_next", "add_to_queue", "next"]
    assert all(item.get("message") != ADMIN_REQUIRED for item in hub.sent)


async def test_correct_pin_issues_admin_session_and_wrong_pin_does_not():
    handler, transport, hub = _handler("2468")
    socket = Socket()

    await handler.handle(socket, {"command": "unlock", "pin": "0000"})
    assert hub.sent == [{"type": "error", "message": WRONG_PIN}]
    assert handler.sessions == {}
    assert getattr(socket, "role", None) != "admin"
    await handler.handle(socket, {"command": "play_now", **TRACK})
    assert transport.calls == []

    hub.sent.clear()
    await handler.handle(socket, {"command": "unlock", "pin": "2468"})
    granted = hub.sent[-1]
    assert granted["type"] == "role"
    assert granted["role"] == "admin"
    token = granted["token"]
    assert isinstance(token, str) and token
    assert handler.sessions[token] == "admin"
    assert socket.role == "admin"

    other = Socket()
    hub.sent.clear()
    await handler.handle(other, {"command": "hello", "token": token})
    assert hub.sent == [{"type": "role", "role": "admin"}]
    assert other.role == "admin"

    stranger = Socket()
    hub.sent.clear()
    await handler.handle(stranger, {"command": "hello", "token": "missing"})
    assert hub.sent == [{"type": "role", "role": "guest"}]
    assert stranger.role == "guest"


async def test_empty_pin_cannot_unlock():
    handler, _transport, hub = _handler("")
    socket = Socket()
    await handler.handle(socket, {"command": "unlock", "pin": ""})
    await handler.handle(socket, {"command": "unlock", "pin": "1"})
    assert handler.sessions == {}
    assert [item["message"] for item in hub.sent] == [WRONG_PIN, WRONG_PIN]
    assert getattr(socket, "role", None) != "admin"
