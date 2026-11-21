from __future__ import annotations

from ym_remote.models.requests import WaveRequest

WAVE_SOURCES = frozenset({"personal", "current", "track", "artist", "album", "playlist", "lumen"})
PROMPT_LIMIT = 300


class EmptyLumenPrompt(Exception):
    """Пустой текст Люмена — это ошибка сокету, не молчаливый сброс."""


def _positive_id(raw) -> int | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def _optional_positive_id(message: dict, key: str) -> int | None | bool:
    """None — поля нет. False — поле есть, но id не годится."""
    if key not in message or message.get(key) is None:
        return None
    parsed = _positive_id(message.get(key))
    if parsed is None:
        return False
    return parsed


def _card_target(message: dict) -> tuple[str | None, int | None] | bool:
    """None-поля — цель не задана. False — цель задана криво, команду отбрасываем."""
    title = None
    if "card_title" in message and message.get("card_title") is not None:
        raw = message.get("card_title")
        if not isinstance(raw, str):
            return False
        title = raw.strip() or None
    index = None
    if "card_index" in message and message.get("card_index") is not None:
        raw_index = message.get("card_index")
        if isinstance(raw_index, bool):
            return False
        try:
            index = int(raw_index)
        except (TypeError, ValueError, OverflowError):
            return False
        if index < 0:
            return False
    return title, index


def parse_start_wave(message: dict) -> WaveRequest | None:
    """None — команду молча отбрасываем. EmptyLumenPrompt — пустой prompt Люмена."""
    source = message.get("source")
    if not isinstance(source, str) or source not in WAVE_SOURCES:
        return None
    if source == "current":
        return WaveRequest(source=source)
    if source == "personal":
        target = _card_target(message)
        if target is False:
            return None
        title, index = target
        return WaveRequest(source=source, card_title=title, card_index=index)
    if source == "track":
        track_id = _positive_id(message.get("track_id"))
        album_id = _positive_id(message.get("album_id"))
        if track_id is None or album_id is None:
            return None
        return WaveRequest(source=source, track_id=track_id, album_id=album_id)
    if source == "artist":
        artist_id = _positive_id(message.get("artist_id"))
        if artist_id is None:
            return None
        return WaveRequest(source=source, artist_id=artist_id)
    if source == "album":
        album_id = _positive_id(message.get("album_id"))
        if album_id is None:
            return None
        return WaveRequest(source=source, album_id=album_id)
    if source == "playlist":
        raw_uuid = message.get("playlist_uuid")
        if not isinstance(raw_uuid, str) or not raw_uuid.strip():
            return None
        kind = _optional_positive_id(message, "playlist_kind")
        uid = _optional_positive_id(message, "playlist_uid")
        if kind is False or uid is False:
            return None
        return WaveRequest(
            source=source,
            playlist_uuid=raw_uuid.strip(),
            playlist_kind=kind if isinstance(kind, int) else None,
            playlist_uid=uid if isinstance(uid, int) else None,
        )
    raw_prompt = message.get("prompt")
    if not isinstance(raw_prompt, str):
        return None
    prompt = raw_prompt.strip()
    if not prompt:
        raise EmptyLumenPrompt
    return WaveRequest(source="lumen", prompt=prompt[:PROMPT_LIMIT])
