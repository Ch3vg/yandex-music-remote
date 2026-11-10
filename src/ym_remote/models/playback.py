from __future__ import annotations

from dataclasses import dataclass, field

from ym_remote.models.music import Artist, Track


@dataclass(frozen=True)
class Playback:
    """Снимок бара. Позиция не входит в кортеж now_playing."""

    title: str
    artist: str
    is_playing: bool
    cover_url: str | None
    cover_url_hq: str | None
    volume: int | None
    artist_href: str | None
    album_href: str | None
    position_sec: float | None
    duration_sec: float | None
    repeat_mode: str
    shuffle: bool
    liked: bool
    queue_name: str
    artists: tuple[Artist, ...] = ()

    def track_key(self) -> str:
        return f"{self.artist}|{self.title}"

    def now_playing_tuple(
        self,
    ) -> tuple[str, bool, int | None, str | None, str, bool]:
        return (
            self.track_key(),
            self.is_playing,
            self.volume,
            self.cover_url,
            self.repeat_mode,
            self.shuffle,
        )


@dataclass(frozen=True)
class NowMeta:
    subtitle: str = ""
    source: str = ""


@dataclass(frozen=True)
class QueueItem:
    track: Track
    is_playing: bool
    is_current: bool = False


@dataclass(frozen=True)
class QueueView:
    before: tuple[QueueItem, ...] = ()
    current: QueueItem | None = None
    after: tuple[QueueItem, ...] = ()
    before_title: str = "Предыдущая очередь"
    after_title: str = "Далее в очереди"
    now_meta: NowMeta = field(default_factory=NowMeta)

    @staticmethod
    def empty() -> QueueView:
        return QueueView()
