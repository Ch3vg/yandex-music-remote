from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

from ym_remote.cdp.adapter import CdpAdapter
from ym_remote.cdp.scripts import search_script
from ym_remote.cdp.wave_art import split_wave_art
from ym_remote.models.music import Album, Artist, Cover, Track


@dataclass(frozen=True)
class PromoCard:
    title: str
    subtitle: str = ""
    cover_url: str | None = None
    background: str | None = None


@dataclass(frozen=True)
class SearchHit:
    tracks: tuple[Track, ...]
    error_code: str | None = None
    artists: tuple[Artist, ...] = ()
    waves: tuple[PromoCard, ...] = ()
    lumen: PromoCard | None = None


class SearchCdpAdapter(CdpAdapter):
    async def search(self, query: str) -> SearchHit:
        async def work() -> SearchHit:
            raw = await self.evaluate(search_script(query), timeout=30)
            return tracks_from_search(raw)

        return await self.session.run(work)


def _parse_track_artists(item: dict) -> tuple[Artist, ...]:
    refs = item.get("artist_refs")
    if isinstance(refs, list):
        parsed: list[Artist] = []
        seen: set[tuple[int | None, str]] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            name = str(ref.get("name") or "").strip()
            if not name:
                continue
            aid = _int(ref.get("id"))
            key = (aid, name)
            if key in seen:
                continue
            seen.add(key)
            parsed.append(Artist(name=name, id=aid))
        if parsed:
            return tuple(parsed)
    names = item.get("artists") or []
    if isinstance(names, str):
        names = [names]
    return tuple(Artist(str(name).strip()) for name in names if str(name).strip())


def _parse_artist_cards(payload: dict) -> tuple[Artist, ...]:
    cards: list[Artist] = []
    seen: set[int] = set()
    for raw in payload.get("artist_cards") or []:
        if not isinstance(raw, dict):
            continue
        artist_id = _int(raw.get("id"))
        name = str(raw.get("name") or "").strip()
        if artist_id is None or not name or artist_id in seen:
            continue
        seen.add(artist_id)
        cover = raw.get("cover") or None
        cards.append(
            Artist(
                name=name,
                id=artist_id,
                cover=Cover(str(cover)) if cover else None,
            )
        )
        if len(cards) >= 6:
            break
    return tuple(cards)


def tracks_from_search(payload) -> SearchHit:
    if not isinstance(payload, dict):
        return SearchHit((), "parse")
    if not payload.get("ok"):
        code = payload.get("code") or "parse"
        if code not in {"no_button", "no_page", "no_input", "parse"}:
            code = "parse"
        return SearchHit((), code)
    tracks: list[Track] = []
    for item in payload.get("tracks") or []:
        if not isinstance(item, dict):
            continue
        track_id = _int(item.get("track_id"))
        title = str(item.get("title") or "").strip()
        if track_id is None or not title:
            continue
        artists = _parse_track_artists(item)
        album_id = _int(item.get("album_id"))
        cover = item.get("cover") or None
        tracks.append(
            Track(
                id=track_id,
                title=title,
                artists=artists,
                albums=(Album(album_id, ""),) if album_id is not None else (),
                cover=Cover(str(cover)) if cover else None,
            )
        )
        if len(tracks) >= 15:
            break
    waves, lumen = _parse_promos(payload)
    return SearchHit(tuple(tracks), artists=_parse_artist_cards(payload), waves=waves, lumen=lumen)


def _promo_card(raw, *, fallback_title: str) -> PromoCard | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip() or fallback_title
    if not title:
        return None
    subtitle = str(raw.get("subtitle") or "").strip()
    cover, background = split_wave_art(raw.get("cover") or raw.get("cover_url"))
    if background is None:
        extra_cover, background = split_wave_art(raw.get("background"))
        cover = cover or extra_cover
    return PromoCard(title=title, subtitle=subtitle, cover_url=cover, background=background)


def _own_title(title: str) -> bool:
    return title.strip().casefold() not in {"", "моя волна"}


def _parse_promos(payload: dict) -> tuple[tuple[PromoCard, ...], PromoCard | None]:
    waves: list[PromoCard] = []
    for raw in payload.get("waves") or []:
        card = _promo_card(raw, fallback_title="")
        if card is None or not _own_title(str(raw.get("title") or "")):
            continue
        if card.subtitle.casefold().count("моя волна") > 1:
            continue
        waves.append(card)
        if len(waves) >= 20:
            break
    lumen_raw = payload.get("lumen")
    lumen = _promo_card(lumen_raw, fallback_title="") if isinstance(lumen_raw, dict) else None
    if lumen is not None and not _own_title(str(lumen_raw.get("title") or "")):
        lumen = None
    return tuple(waves), lumen


class _MarkupNode:
    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag
        self.test_id = attrs.get("data-test-id", "")
        self.src = attrs.get("src", "")
        self.style = attrs.get("style", "")
        self.children: list[_MarkupNode | str] = []


class _MarkupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _MarkupNode("root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _MarkupNode(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"img", "br", "hr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        if len(self.stack) > 1 and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def _flat_text(node: _MarkupNode) -> str:
    chunks: list[str] = []

    def walk(item: _MarkupNode | str) -> None:
        if isinstance(item, str):
            chunks.append(item)
            return
        for child in item.children:
            walk(child)

    walk(node)
    return " ".join("".join(chunks).split())


def _wave_mentions(text: str) -> int:
    folded = text.casefold()
    count = 0
    start = 0
    needle = "моя волна"
    while True:
        at = folded.find(needle, start)
        if at < 0:
            return count
        count += 1
        start = at + len(needle)


def _split_promo(text: str) -> tuple[str, str]:
    folded = text.casefold()
    markers = (
        "я так чувствую",
        "моя волна по настроению",
        "моя волна от люмена",
        "моя волна",
    )
    cut = -1
    for marker in markers:
        at = folded.find(marker)
        if at >= 0 and (cut < 0 or at < cut):
            cut = at
    if cut <= 0:
        return text.strip(), ""
    return text[:cut].strip(), text[cut:].strip()


def _is_lumen_node(node: _MarkupNode, text: str) -> bool:
    if "LUMEN" in node.test_id.upper():
        return True
    return "люмен" in text.casefold()


def _card_parts(node: _MarkupNode) -> tuple[str, str] | None:
    text = _flat_text(node)
    if _wave_mentions(text) != 1:
        return None
    title, subtitle = _split_promo(text)
    if not subtitle or not title or title.casefold() == "моя волна":
        return None
    return title, subtitle


def _has_tighter_card(node: _MarkupNode) -> bool:
    for child in node.children:
        if isinstance(child, str):
            continue
        if _card_parts(child) is not None or _has_tighter_card(child):
            return True
    return False


def _art_of(node: _MarkupNode) -> tuple[str | None, str | None]:
    if node.tag == "img" and node.src:
        cover, _background = split_wave_art(node.src)
        if cover:
            return cover, None
    css: str | None = None
    for child in node.children:
        if isinstance(child, str):
            continue
        cover, background = _art_of(child)
        if cover:
            return cover, None
        if background and css is None:
            css = background
    if node.style:
        cover, background = split_wave_art(node.style)
        if cover:
            return cover, None
        css = css or background
    return None, css


def _find_test_id(node: _MarkupNode, test_id: str) -> _MarkupNode | None:
    if node.test_id == test_id:
        return node
    for child in node.children:
        if isinstance(child, str):
            continue
        found = _find_test_id(child, test_id)
        if found is not None:
            return found
    return None


def _card_from_entity(node: _MarkupNode) -> PromoCard | None:
    title_node = _find_test_id(node, "ENTITY_CARD_ENTITY_META_TITLE")
    if title_node is None:
        return None
    title = _flat_text(title_node).strip()
    if not _own_title(title):
        return None
    subtitle_node = _find_test_id(node, "ENTITY_CARD_ENTITY_META_DESCRIPTION")
    subtitle = _flat_text(subtitle_node).strip() if subtitle_node is not None else ""
    cover, background = _art_of(node)
    return PromoCard(title=title, subtitle=subtitle, cover_url=cover, background=background)


def promos_from_markup(markup: str) -> tuple[tuple[PromoCard, ...], PromoCard | None]:
    """Лист SEARCH_VIBE_CARD / QUERY_TO_VIBE_BLOCK. Заголовок и подпись — отдельные узлы."""
    parser = _MarkupParser()
    parser.feed(markup)
    waves: list[PromoCard] = []
    lumen: PromoCard | None = None

    def visit(node: _MarkupNode) -> None:
        nonlocal lumen
        if node.test_id == "QUERY_TO_VIBE_BLOCK":
            card = _card_from_entity(node)
            if card is not None and lumen is None:
                lumen = card
            return
        if node.test_id == "SEARCH_VIBE_CARD":
            card = _card_from_entity(node)
            if card is not None and "люмен" not in card.subtitle.casefold() and len(waves) < 20:
                waves.append(card)
            return
        for child in node.children:
            if not isinstance(child, str):
                visit(child)

    visit(parser.root)
    return tuple(waves), lumen


def _int(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
