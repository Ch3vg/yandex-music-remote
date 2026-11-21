from ym_remote.cdp.search import promos_from_markup, tracks_from_search
from ym_remote.cdp.wave_art import split_wave_art


def test_split_wave_art_prefers_image_and_drops_blob():
    assert split_wave_art("https://cdn.example/wave.png") == ("https://cdn.example/wave.png", None)
    assert split_wave_art("cdn/w") == ("cdn/w", None)
    assert split_wave_art("url('https://cdn.example/a.png')") == ("https://cdn.example/a.png", None)
    assert split_wave_art("url()") == (None, None)
    assert split_wave_art("blob:https://music.yandex.ru/id") == (None, None)
    assert split_wave_art("url(blob:https://music.yandex.ru/id)") == (None, None)
    small = "data:image/svg+xml," + "a" * 20
    assert split_wave_art(small) == (small, None)
    huge = "data:image/png;base64," + "a" * 30_000
    assert split_wave_art(huge) == (None, None)
    gradient = "linear-gradient(100deg, #ff5cab 0%, #e21878 100%)"
    assert split_wave_art(gradient) == (None, gradient)
    mixed = "url(blob:https://x/1), linear-gradient(90deg, #111 0%, #333 100%)"
    assert split_wave_art(mixed) == (None, "linear-gradient(90deg, #111 0%, #333 100%)")


def test_split_wave_art_reads_cdp_payload():
    assert split_wave_art({"cover": "https://cdn/w.png", "background": "linear-gradient(90deg, #111, #222)"}) == (
        "https://cdn/w.png",
        None,
    )
    assert split_wave_art({"cover": "", "background": "rgb(20, 10, 40)"}) == (None, "rgb(20, 10, 40)")


def test_promos_from_markup_reads_card_background():
    markup = """
    <div>
      <div data-test-id="SEARCH_VIBE_CARD" style="background-image: url(https://cdn.example/wave.jpg)">
        <div data-test-id="ENTITY_CARD_ENTITY_META_TITLE">Этника сальвадорских улиц</div>
        <div data-test-id="ENTITY_CARD_ENTITY_META_DESCRIPTION">Моя волна</div>
      </div>
      <div data-test-id="SEARCH_VIBE_CARD" style="background-image: url(blob:https://music.yandex.ru/1)">
        <div data-test-id="ENTITY_CARD_ENTITY_META_TITLE">Мистический йойк</div>
        <div data-test-id="ENTITY_CARD_ENTITY_META_DESCRIPTION">Моя волна</div>
      </div>
      <div data-test-id="SEARCH_VIBE_CARD" style="background: linear-gradient(90deg, #222 0%, #555 100%)">
        <div data-test-id="ENTITY_CARD_ENTITY_META_TITLE">Данжен-синт</div>
        <div data-test-id="ENTITY_CARD_ENTITY_META_DESCRIPTION">Моя волна</div>
      </div>
    </div>
    """
    waves, lumen = promos_from_markup(markup)
    assert lumen is None
    assert waves[0].cover_url == "https://cdn.example/wave.jpg"
    assert waves[0].background is None
    assert waves[1].cover_url is None
    assert waves[2].background == "linear-gradient(90deg, #222 0%, #555 100%)"


def test_tracks_from_search_sanitizes_wave_background():
    hit = tracks_from_search(
        {
            "ok": True,
            "tracks": [],
            "waves": [
                {"title": "Энергичное", "subtitle": "Моя волна", "cover": "url(blob:https://x/1)", "background": "linear-gradient(90deg, #111, #333)"},
                {"title": "Бодрое утро", "subtitle": "Моя волна", "cover": "https://cdn/w.png"},
            ],
            "lumen": {"title": "JDM phonk", "subtitle": "Моя волна от люмена", "cover": "lumen.png"},
        }
    )
    assert hit.waves[0].cover_url is None
    assert hit.waves[0].background == "linear-gradient(90deg, #111, #333)"
    assert hit.waves[1].cover_url == "https://cdn/w.png"
    assert hit.lumen is not None and hit.lumen.cover_url == "lumen.png"
