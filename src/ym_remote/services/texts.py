"""Тексты, которые доходят до пульта."""

SEARCH_UNAVAILABLE = "Поиск недоступен — нет связи с Яндекс Музыкой"
SEARCH_PARSE = "Не удалось разобрать результаты поиска"
SEARCH_BUTTON = "Кнопка «Поиск» в сайдбаре не найдена"
SEARCH_PAGE = "Страница поиска не открылась"
SEARCH_INPUT = "Поле поиска не найдено"
PLAYLIST_NOT_FOUND = "Плейлист не найден"
ARTIST_NOT_FOUND = "Исполнитель не найден"
ALBUM_NOT_FOUND = "Альбом не найден"
API_NOT_READY = "API-клиент не инициализирован"
LIBRARY_FAILED = "Не удалось загрузить библиотеку"
PLAY_FAILED = "Не удалось включить трек"
ARTIST_PLAY_FAILED = "Не удалось запустить исполнителя"
ALBUM_PLAY_FAILED = "Не удалось запустить альбом"
ADD_QUEUE_FAILED = "Не удалось добавить в очередь"
VOLUME_FAILED = "Не удалось изменить громкость"
SEEK_FAILED = "Не удалось перемотать трек"
SHUFFLE_FAILED = "Не удалось переключить перемешивание"
REPEAT_BUTTON_MISSING = "Кнопка повтора не найдена в приложении"
REPEAT_FAILED = "Не удалось переключить повтор"
NAVIGATE_FAILED = "Не удалось открыть карточку в приложении"
LIKE_FAILED = "Лайк недоступен — откройте полноэкранный плеер на ПК"
MENU_UNAVAILABLE = "Пункт меню недоступен. Запустите воспроизведение в приложении и попробуйте снова."
TRACK_ACTION_FAILED = "Не удалось выполнить действие с треком"
PLAYLIST_ACTION_FAILED = "Не удалось выполнить действие в плейлисте (трек не найден в списке или меню недоступно)"
NO_ALBUM = "У трека {track_id} нет альбома — откройте плейлист в приложении и включите трек оттуда"
PLAY_DESKTOP_FAILED = "Не удалось включить трек в приложении на ПК"

SEARCH_CODES = {
    "no_button": SEARCH_BUTTON,
    "no_page": SEARCH_PAGE,
    "no_input": SEARCH_INPUT,
    "parse": SEARCH_PARSE,
    "unavailable": SEARCH_UNAVAILABLE,
}


def queue_track_failed(track_id: int) -> str:
    return f"Не удалось включить трек из очереди ({track_id})"


def queue_notice(artist: str, title: str, *, end: bool) -> str:
    suffix = "в конец очереди" if end else "играть следующим"
    artist = (artist or "").strip()
    title = (title or "").strip()
    if artist and title:
        middle = f"{artist} — {title}"
    elif artist or title:
        middle = artist or title
    else:
        middle = ""
    if middle:
        return f"Трек {middle} — {suffix}"
    return f"Трек  — {suffix}"
