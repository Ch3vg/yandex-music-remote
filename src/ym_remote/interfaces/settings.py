from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def find_root() -> Path:
    here = Path(__file__).resolve()
    candidate = here.parents[3]
    if (candidate / "pyproject.toml").exists() or (candidate / "application.md").exists():
        return candidate
    return Path.cwd()


def _port(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class Settings:
    token: str
    local_ip: str | None
    port: int
    cdp_port: int
    root: Path

    @classmethod
    def from_env(cls, root: Path | None = None) -> Settings:
        root = root or find_root()
        load_dotenv(root / ".env")
        local = os.environ.get("LOCAL_IP", "").strip() or None
        return cls(
            token=os.environ.get("YANDEX_MUSIC_TOKEN", "").strip(),
            local_ip=local,
            port=_port("PORT", 8001),
            cdp_port=_port("CDP_PORT", 9222),
            root=root,
        )
