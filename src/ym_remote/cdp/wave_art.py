"""Фон карточки волны: картинка или CSS, без blob и пустых url."""

from __future__ import annotations

import re
import time

from ym_remote.cdp.scripts import wave_background_script
from ym_remote.cdp.session import CdpError, CdpSession, CdpUnavailable

DATA_URL_LIMIT = 24_000
_URL = re.compile(r"""url\(\s*(['"]?)([^)'"]*)\1\s*\)""", re.IGNORECASE)
_MISS_TTL = 15.0


def _usable_url(raw: str) -> str | None:
    url = raw.strip().strip("\"'")
    if not url or any(char.isspace() for char in url):
        return None
    lowered = url.lower()
    if lowered.startswith("blob:") or lowered.startswith("url("):
        return None
    if lowered.startswith("data:"):
        if len(url) > DATA_URL_LIMIT or not lowered.startswith("data:image/"):
            return None
        return url
    if any(token in lowered for token in ("gradient(", "rgb(", "hsl(", ";", "background")):
        return None
    if url.startswith("//"):
        return "https:" + url
    return url


def _css_background(text: str) -> str | None:
    cleaned = _URL.sub(lambda match: match.group(0) if _usable_url(match.group(2)) else "", text)
    declared = re.search(r"background(?:-image|-color)?\s*:\s*([^;]+)", cleaned, re.IGNORECASE)
    if declared:
        cleaned = declared.group(1)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;")
    if not cleaned or "blob:" in cleaned.lower() or len(cleaned) > 2000:
        return None
    if re.search(r"""url\(\s*['"]?\s*['"]?\s*\)""", cleaned, re.IGNORECASE):
        return None
    lowered = cleaned.lower()
    if not any(token in lowered for token in ("gradient(", "#", "rgb(", "hsl(")):
        return None
    return cleaned


def split_wave_art(value) -> tuple[str | None, str | None]:
    """Картинка (img или url(...)) либо запасной CSS-фон. blob и пустой url отбрасываются."""
    if isinstance(value, dict):
        cover, _css = split_wave_art(value.get("cover") or value.get("cover_url"))
        _cover, css = split_wave_art(value.get("background") or value.get("background_css") or value.get("css"))
        if cover or _cover:
            return cover or _cover, None
        return None, css
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    for match in _URL.finditer(text):
        url = _usable_url(match.group(2))
        if url:
            return url, None
    bare = _usable_url(text)
    if bare:
        return bare, None
    return None, _css_background(text)


class WaveArtService:
    """Один успешный снимок фона «Моя волна» с главной десктопа."""

    def __init__(self, session: CdpSession) -> None:
        self.session = session
        self._cover: str | None = None
        self._background: str | None = None
        self._ready = False
        self._miss_at = 0.0

    async def snapshot(self) -> tuple[str | None, str | None]:
        if self._ready:
            return self._cover, self._background
        if time.monotonic() - self._miss_at < _MISS_TTL:
            return None, None
        try:
            raw = await self.session.evaluate(wave_background_script(), timeout=3)
        except (CdpUnavailable, CdpError, OSError, ConnectionError, TimeoutError):
            self._miss_at = time.monotonic()
            return None, None
        cover, background = split_wave_art(raw if isinstance(raw, dict) else None)
        if cover or background:
            self._cover = cover
            self._background = background
            self._ready = True
        else:
            self._miss_at = time.monotonic()
        return cover, background
