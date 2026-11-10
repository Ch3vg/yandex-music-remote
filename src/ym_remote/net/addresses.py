"""Выбор локального адреса пульта.

Кандидаты: gethostbyname_ex и UDP-сокет до 8.8.8.8:80.
Отбрасываются 127.*, 169.254.* и 172.16.0.0/12.
Приоритет: 192.168.*, затем 10.*, затем остальные.
LOCAL_IP становится выбранным, даже если его не было среди обнаруженных.
Чужой IP у /qr подменяется выбранным.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass


def _dropped(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if not isinstance(address, ipaddress.IPv4Address):
        return True
    if ip.startswith("127.") or ip.startswith("169.254."):
        return True
    return address in ipaddress.ip_network("172.16.0.0/12")


def _rank(ip: str) -> int:
    if ip.startswith("192.168."):
        return 0
    if ip.startswith("10."):
        return 1
    return 2


def filter_candidates(ips: list[str]) -> list[str]:
    unique: list[str] = []
    for ip in ips:
        if ip in unique or _dropped(ip):
            continue
        unique.append(ip)
    unique.sort(key=_rank)
    return unique


def discover_ips() -> list[str]:
    found: list[str] = []
    try:
        _hostname, _aliases, addresses = socket.gethostbyname_ex(socket.gethostname())
        found.extend(addresses)
    except OSError:
        pass
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        found.append(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()
    return found


@dataclass(frozen=True)
class NetworkChoice:
    chosen: str
    port: int
    all: tuple[str, ...]
    local_ip: str | None
    candidates: tuple[str, ...]

    @property
    def url(self) -> str:
        return f"http://{self.chosen}:{self.port}/"

    def info(self) -> dict:
        return {
            "chosen": self.chosen,
            "port": self.port,
            "all": list(self.all),
            "url": self.url,
        }

    def qr_host(self, requested: str | None) -> str:
        if requested and (requested in self.candidates or (self.local_ip is not None and requested == self.local_ip)):
            return requested
        return self.chosen


def choose_network(
    discovered: list[str],
    *,
    local_ip: str | None,
    port: int,
) -> NetworkChoice:
    candidates = filter_candidates(discovered)
    ordered = list(candidates)
    override = (local_ip or "").strip() or None
    if override:
        if override not in ordered:
            ordered.insert(0, override)
        if ordered[0] != override:
            ordered.remove(override)
            ordered.insert(0, override)
        chosen = override
    elif ordered:
        chosen = ordered[0]
    else:
        chosen = "127.0.0.1"
        ordered = ["127.0.0.1"]
    return NetworkChoice(
        chosen=chosen,
        port=port,
        all=tuple(ordered),
        local_ip=override,
        candidates=tuple(candidates),
    )
