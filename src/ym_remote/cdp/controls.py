"""Правила снимка кнопок плеера. Тот же смысл, что у ymLikeActive в scripts.py."""

from __future__ import annotations

ROOT_ORDER = ("FULLSCREEN_PLAYER_MODAL", "PLAYERBAR_DESKTOP", "VIBE_PLAYERBAR", "document")


def like_active(
    test_id: str | None,
    aria_pressed: str | None = None,
    aria_checked: str | None = None,
) -> bool:
    ident = test_id or ""
    if not ident.startswith("LIKE_BUTTON"):
        return False
    if "_ON" in ident or "_ACTIVE" in ident or "_LIKED" in ident:
        return True
    return aria_pressed == "true" or aria_checked == "true"


def shuffle_active(test_id: str | None, aria_pressed: str | None = None) -> bool:
    ident = test_id or ""
    if not ident.startswith("SHUFFLE_BUTTON"):
        return False
    return ident.endswith("_ON") or aria_pressed == "true"


def repeat_mode_from_id(test_id: str | None) -> str:
    if test_id == "REPEAT_BUTTON_REPEAT_ONE":
        return "one"
    if test_id == "REPEAT_BUTTON_REPEAT_CONTEXT":
        return "queue"
    return "off"


def first_like(buttons: list[dict]) -> bool:
    """Первая видимая кнопка с префиксом LIKE_BUTTON в порядке корней плеера.

    Строки треков пропускаются: их сердечко не относится к бару.
    """

    rank = {name: index for index, name in enumerate(ROOT_ORDER)}
    ordered = sorted(buttons, key=lambda item: rank.get(str(item.get("root")), len(ROOT_ORDER)))
    for item in ordered:
        if not item.get("visible", True):
            continue
        if item.get("in_track_row"):
            continue
        ident = str(item.get("id") or "")
        if not ident.startswith("LIKE_BUTTON"):
            continue
        return like_active(ident, item.get("aria_pressed"), item.get("aria_checked"))
    return False
