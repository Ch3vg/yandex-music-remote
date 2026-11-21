import pytest

from ym_remote.schemas.wave import EmptyLumenPrompt, parse_start_wave


def test_personal_and_current_need_no_extra_fields():
    personal = parse_start_wave({"command": "start_wave", "source": "personal"})
    current = parse_start_wave({"command": "start_wave", "source": "current", "track_id": "nope"})
    assert personal is not None and personal.source == "personal"
    assert current is not None and current.source == "current" and current.track_id is None


def test_unknown_source_and_bad_ids_are_dropped():
    assert parse_start_wave({"source": "radio"}) is None
    assert parse_start_wave({"source": "track", "track_id": 1}) is None
    assert parse_start_wave({"source": "track", "track_id": 0, "album_id": 2}) is None
    assert parse_start_wave({"source": "track", "track_id": True, "album_id": 2}) is None
    assert parse_start_wave({"source": "artist", "artist_id": "x"}) is None
    assert parse_start_wave({"source": "album"}) is None
    assert parse_start_wave({"source": "playlist", "playlist_uuid": "  "}) is None
    assert parse_start_wave({"source": "playlist", "playlist_uuid": "pl", "playlist_kind": 0}) is None
    assert parse_start_wave({"source": "lumen"}) is None
    assert parse_start_wave({"source": "lumen", "prompt": 5}) is None


def test_playlist_keeps_optional_ids_and_lumen_prompt_is_trimmed():
    playlist = parse_start_wave(
        {"source": "playlist", "playlist_uuid": "  abc  ", "playlist_kind": "3", "playlist_uid": 9}
    )
    assert playlist is not None
    assert playlist.playlist_uuid == "abc"
    assert playlist.playlist_kind == 3
    assert playlist.playlist_uid == 9

    lumen = parse_start_wave({"source": "lumen", "prompt": "  " + ("а" * 400) + "  "})
    assert lumen is not None
    assert lumen.prompt == "а" * 300


def test_personal_can_target_a_search_card():
    aimed = parse_start_wave({"source": "personal", "card_title": "  Бодрое утро  ", "card_index": 1})
    assert aimed is not None
    assert aimed.card_title == "Бодрое утро"
    assert aimed.card_index == 1
    assert parse_start_wave({"source": "personal", "card_index": -1}) is None
    assert parse_start_wave({"source": "personal", "card_title": 3}) is None


def test_empty_lumen_prompt_is_an_error():
    with pytest.raises(EmptyLumenPrompt):
        parse_start_wave({"source": "lumen", "prompt": "   "})
