"""Точка входа uvicorn: ym_remote.interfaces.asgi:app"""

from ym_remote.interfaces.factory import create_app
from ym_remote.interfaces.settings import Settings

_settings = Settings.from_env()
if not _settings.token:
    raise SystemExit("YANDEX_MUSIC_TOKEN не найден в .env")

app = create_app(_settings)
