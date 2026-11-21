"""Селекторы и ссылки плеера сверяются с открытой Яндекс Музыкой.

Без CDP на 9222 живые проверки пропускаются. Контракт селекторов при этом
остаётся в коде скриптов и проверяется всегда.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from ym_remote.cdp.scripts import read_bar_script
from ym_remote.cdp.session import CdpSession, CdpUnavailable

_SCRIPTS = Path(__file__).resolve().parents[2] / "src" / "ym_remote" / "cdp" / "scripts.py"

# Узлы, без которых большой плеер «Моей волны» не отдаёт трек.
VIBE_REQUIRED = (
    "VIBE_PLAYERBAR",
    "VIBE_PLAYERBAR_TRACK_NAME",
    "VIBE_DYNAMIC_ARTISTS",
    "SEPARATED_ARTIST_TITLE",
    "VIBE_ALBUM_COVER",
    "CHANGE_VOLUME_SLIDER",
    "LIKE_BUTTON",
    "NEXT_TRACK_BUTTON",
    "PREVIOUS_TRACK_BUTTON",
    "TIMECODE_TIME_START",
    "TIMECODE_TIME_END",
)

# Узлы нижнего бара, когда приложение ещё рисует PLAYERBAR_DESKTOP.
DESKTOP_REQUIRED = (
    "PLAYERBAR_DESKTOP",
    "TRACK_TITLE",
    "SEPARATED_ARTIST_TITLE",
    "PLAYERBAR_DESKTOP_COVER_CONTAINER",
    "TIMECODE_SLIDER",
    "CHANGE_VOLUME_SLIDER",
    "LIKE_BUTTON",
    "NEXT_TRACK_BUTTON",
    "PREVIOUS_TRACK_BUTTON",
)
DESKTOP_PREFIXES = ("SHUFFLE_BUTTON", "REPEAT_BUTTON")

_ALBUM_ID = re.compile(r"(?:albumId=|/album/)(\d+)")
_ARTIST_ID = re.compile(r"(?:artistId=|/artist/)(\d+)")
_COVER_STEM = re.compile(r"/([^/]+)/\d+x\d+(?:[^/]*)?$")


def test_player_selectors_are_still_used_by_cdp_scripts():
    source = _SCRIPTS.read_text(encoding="utf-8")
    missing = [item for item in (*VIBE_REQUIRED, *DESKTOP_REQUIRED, *DESKTOP_PREFIXES) if item not in source]
    assert missing == []


@pytest.fixture
async def music_page():
    port = int(os.environ.get("CDP_PORT", "9222"))
    session = CdpSession(port)
    try:
        await session.evaluate("1", timeout=2)
    except CdpUnavailable:
        await session.stop()
        pytest.skip(f"Яндекс Музыка с CDP на порту {port} не запущена")
    try:
        yield session
    finally:
        await session.stop()


def _probe(ids: tuple[str, ...]) -> str:
    listed = ",".join(repr(item) for item in ids)
    return f"""(() => {{
      const ids = [{listed}];
      const meta = navigator.mediaSession && navigator.mediaSession.metadata;
      const vibe = document.querySelector('[data-test-id="VIBE_PLAYERBAR"]');
      const desktop = document.querySelector('[data-test-id="PLAYERBAR_DESKTOP"]');
      const cover = document.querySelector('[data-test-id="VIBE_ALBUM_COVER"] img');
      const album = document.querySelector('[data-test-id="VIBE_ALBUM_COVER"] a');
      return {{
        present: ids.filter((id) => document.querySelector('[data-test-id="' + id + '"]')),
        prefixes: ids.filter((id) => [...document.querySelectorAll("[data-test-id]")].some((el) => (el.getAttribute("data-test-id") || "").startsWith(id))),
        vibe: !!vibe,
        desktop: !!desktop,
        playing: !!(vibe || desktop),
        cover: cover ? (cover.currentSrc || cover.getAttribute("src") || "") : "",
        albumHref: album ? (album.href || album.getAttribute("href") || "") : "",
        meta: meta ? {{
          title: meta.title || "",
          artist: meta.artist || "",
          art: (meta.artwork || []).map((item) => item.src || "")
        }} : null
      }};
    }})()"""


def _stem(url: str) -> str:
    match = _COVER_STEM.search(url or "")
    return match.group(1) if match else ""


async def test_open_player_selectors_and_links_match_the_track(music_page: CdpSession):
    probe = await music_page.evaluate(
        _probe((*VIBE_REQUIRED, *DESKTOP_REQUIRED, *DESKTOP_PREFIXES)),
        timeout=8,
    )
    assert isinstance(probe, dict)
    if not probe.get("playing"):
        pytest.fail("на странице нет ни VIBE_PLAYERBAR, ни PLAYERBAR_DESKTOP")

    present = set(probe.get("present") or [])
    if probe.get("vibe"):
        missing = [item for item in VIBE_REQUIRED if item not in present]
        assert missing == [], f"в большом плеере пропали селекторы: {missing}"
    if probe.get("desktop"):
        missing = [item for item in DESKTOP_REQUIRED if item not in present]
        assert missing == [], f"в нижнем баре пропали селекторы: {missing}"
        prefixes = set(probe.get("prefixes") or [])
        missing_prefixes = [item for item in DESKTOP_PREFIXES if item not in prefixes]
        assert missing_prefixes == [], f"в нижнем баре пропали кнопки: {missing_prefixes}"

    raw = await music_page.evaluate(read_bar_script(), timeout=8)
    assert isinstance(raw, dict)
    title = str(raw.get("title") or "").strip()
    artists = [str(name).strip() for name in (raw.get("artists") or []) if str(name).strip()]
    assert title
    assert artists
    assert title != title + title

    meta = probe.get("meta") or {}
    if meta.get("title"):
        assert title == meta["title"]
    if meta.get("artist"):
        assert ", ".join(artists) == meta["artist"]

    cover = str(raw.get("cover_url") or "")
    assert cover.startswith("https://")
    if probe.get("vibe"):
        assert _stem(cover) and _stem(cover) == _stem(str(probe.get("cover") or ""))
        artwork = [_stem(url) for url in (meta.get("art") or []) if _stem(url)]
        if artwork:
            assert _stem(cover) in artwork

    album_href = str(raw.get("album_href") or "")
    if album_href or probe.get("albumHref"):
        assert _ALBUM_ID.search(album_href), album_href
    if probe.get("vibe") and probe.get("albumHref") and album_href:
        assert _ALBUM_ID.search(album_href).group(1) == _ALBUM_ID.search(str(probe["albumHref"])).group(1)

    artist_href = str(raw.get("artist_href") or "")
    refs = raw.get("artist_refs") or []
    if artist_href:
        found = _ARTIST_ID.search(artist_href)
        assert found, artist_href
        linked = [ref for ref in refs if isinstance(ref, dict) and ref.get("id") is not None]
        if linked:
            assert int(found.group(1)) == int(linked[0]["id"])
    assert [ref.get("name") for ref in refs if isinstance(ref, dict)] == artists

    position = raw.get("position_sec")
    duration = raw.get("duration_sec")
    assert isinstance(position, (int, float)) and isinstance(duration, (int, float))
    assert 0 <= position <= duration
    assert isinstance(raw.get("volume"), int)
