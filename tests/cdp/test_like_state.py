import pytest

from ym_remote.cdp.controls import first_like, like_active, repeat_mode_from_id, shuffle_active
from ym_remote.cdp.scripts import HELPERS, reaction_script, read_bar_script, shuffle_script
from ym_remote.models.errors import RemoteError
from ym_remote.services.gate import HeavyGate
from ym_remote.services.texts import LIKE_FAILED, SHUFFLE_FAILED
from ym_remote.services.transport import TransportService


def test_like_active_by_id_suffix():
    assert like_active("LIKE_BUTTON_ON", None, None)
    assert like_active("LIKE_BUTTON_ACTIVE", "false", None)
    assert like_active("LIKE_BUTTON_TRACK_LIKED", None, "false")
    assert not like_active("LIKE_BUTTON", None, None)
    assert not like_active("LIKE_BUTTON_OFF", "false", "false")
    assert not like_active("TRACK_LIKE_BUTTON_ON", None, None)


def test_like_active_by_aria():
    assert like_active("LIKE_BUTTON", "true", None)
    assert like_active("LIKE_BUTTON", "false", "true")
    assert not like_active("LIKE_BUTTON", "false", "false")
    assert not like_active("LIKE_BUTTON", None, None)


def test_player_like_wins_over_an_earlier_track_row():
    buttons = [
        {
            "root": "document",
            "id": "LIKE_BUTTON",
            "aria_pressed": "false",
            "visible": True,
            "in_track_row": True,
        },
        {
            "root": "FULLSCREEN_PLAYER_MODAL",
            "id": "LIKE_BUTTON",
            "aria_pressed": "true",
            "visible": True,
        },
    ]
    assert first_like(buttons) is True


def test_hidden_fullscreen_like_falls_through_to_the_bar():
    buttons = [
        {
            "root": "FULLSCREEN_PLAYER_MODAL",
            "id": "LIKE_BUTTON_ON",
            "visible": False,
        },
        {
            "root": "PLAYERBAR_DESKTOP",
            "id": "LIKE_BUTTON",
            "aria_pressed": "false",
            "visible": True,
        },
    ]
    assert first_like(buttons) is False


def test_shuffle_and_repeat_follow_the_same_attributes():
    assert shuffle_active("SHUFFLE_BUTTON_ON", "false")
    assert shuffle_active("SHUFFLE_BUTTON", "true")
    assert not shuffle_active("SHUFFLE_BUTTON", "false")
    assert repeat_mode_from_id("REPEAT_BUTTON_NO_REPEAT") == "off"
    assert repeat_mode_from_id("REPEAT_BUTTON_REPEAT_CONTEXT") == "queue"
    assert repeat_mode_from_id("REPEAT_BUTTON_REPEAT_ONE") == "one"
    assert repeat_mode_from_id(None) == "off"


def test_playback_flags_come_from_controls_outside_track_rows():
    source = read_bar_script()
    playing = HELPERS.split("function ymTransportPlaying()", 1)[1].split("function ymPressEscape()", 1)[0]
    assert '[data-test-id="PAUSE_BUTTON"]' in playing
    assert 'aria-label="Пауза"' in playing
    assert "ymVisible(button) && !ymInTrackRow(button)" in playing
    assert "if (root === document.body) continue;" in playing
    assert source.split("let isPlaying", 1)[1].startswith(" = ymTransportPlaying()")

    shuffle = source.split("let shuffle = false;", 1)[1].split("const likeButton", 1)[0]
    assert 'ymFindControl("SHUFFLE_BUTTON")' in shuffle
    assert 'id.endsWith("_ON")' in shuffle
    assert 'getAttribute("aria-pressed") === "true"' in shuffle
    finder = HELPERS.split("function ymFindControl(prefix)", 1)[1].split("function ymFindReaction", 1)[0]
    assert "ymInTrackRow(button)" in finder

    repeat_in = HELPERS.split("function ymFindRepeatIn(root)", 1)[1].split("function ymInTrackRow", 1)[0]
    assert 'data-test-id^="REPEAT_BUTTON"' in repeat_in
    assert "!ymInTrackRow(button)" in repeat_in
    repeat_read = source.split('let repeatMode = "off";', 1)[1].split("let shuffle = false;", 1)[0]
    assert "ymFindRepeat()" in repeat_read
    assert 'id === "REPEAT_BUTTON_REPEAT_ONE"' in repeat_read
    assert 'repeatMode = "one"' in repeat_read
    assert 'id === "REPEAT_BUTTON_REPEAT_CONTEXT"' in repeat_read
    assert 'repeatMode = "queue"' in repeat_read
    assert "REPEAT_BUTTON_NO_REPEAT" not in repeat_read
    assert repeat_read.count("repeatMode") == 2


def test_reader_searches_player_roots_and_like_marks():
    source = read_bar_script()
    assert "ymFindControl(\"LIKE_BUTTON\")" in source
    assert "ymLikeActive" in source
    assert "ymTransportPlaying" in source
    assert '[data-test-id*="LIKE_BUTTON"]' not in source
    roots = HELPERS.index("FULLSCREEN_PLAYER_MODAL")
    assert roots < HELPERS.index("PLAYERBAR_DESKTOP") < HELPERS.index("VIBE_PLAYERBAR")
    body = HELPERS[HELPERS.index("function ymLikeActive"):HELPERS.index("function ymFindControl")]
    assert '_ON' in body and "_ACTIVE" in body and "_LIKED" in body
    assert 'pressed === "true"' in body and 'checked === "true"' in body
    assert 'id.startsWith("LIKE_BUTTON")' in body


class _ToggleAdapter:
    def __init__(self, *, changed: bool):
        self.changed = changed
        self.calls: list[tuple] = []

    async def set_shuffle(self, on: bool) -> bool:
        self.calls.append(("shuffle", on))
        return self.changed

    async def react(self, kind: str) -> bool:
        self.calls.append(("react", kind))
        return self.changed


async def test_dislike_and_shuffle_fail_unless_the_desktop_button_changes():
    script = reaction_script("dislike")
    assert 'const kind = "dislike"' in script
    reaction = script.split("function ymFindReaction(kind)", 1)[1].split("function ymControlOn", 1)[0]
    assert "DISLIKE_BUTTON" in reaction
    assert "ymInTrackRow(button)" in reaction
    tail = script.split("const before = ymControlOn(button);", 1)[1]
    between = tail.split("ymClick(button);", 1)[1].split("!== before", 1)[0]
    assert "return true" not in between
    assert "ymControlOn(ymFindReaction(kind)) !== before" in tail
    after = tail.split("!== before", 1)[1]
    assert ") return true;" in after.split("return false;", 1)[0]
    assert "return false;" in after

    turned_on = shuffle_script(True)
    shuffle_body = turned_on.split("function ymShuffleOn", 1)[1]
    assert 'id.endsWith("_ON")' in shuffle_body
    assert 'getAttribute("aria-pressed") === "true"' in shuffle_body
    assert 'ymFindControl("SHUFFLE_BUTTON")' in turned_on
    clicked = turned_on.split("ymClick(button);", 1)[1]
    assert 'ymShuffleOn(ymFindControl("SHUFFLE_BUTTON")) === true' in clicked
    assert clicked.index("=== true") < clicked.index("return false;")
    turned_off = shuffle_script(False)
    assert 'ymShuffleOn(ymFindControl("SHUFFLE_BUTTON")) === false' in turned_off.split("ymClick(button);", 1)[1]

    service = TransportService(_ToggleAdapter(changed=False), None, HeavyGate(), retry_pause=0)
    with pytest.raises(RemoteError) as dislike:
        await service.react("dislike")
    assert dislike.value.message == LIKE_FAILED
    with pytest.raises(RemoteError) as shuffle:
        await service.set_shuffle(True)
    assert shuffle.value.message == SHUFFLE_FAILED

    changed = _ToggleAdapter(changed=True)
    done = TransportService(changed, None, HeavyGate(), retry_pause=0)
    assert await done.react("dislike") is True
    await done.set_shuffle(False)
    assert changed.calls == [("react", "dislike"), ("shuffle", False)]
